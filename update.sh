#!/bin/sh

# Variáveis de ambiente para o banco de dados
# DB_URL="jdbc:postgresql://db:5432/esus"
# DB_URL="jdbc:postgresql://db:5432/esus?ssl=true&sslmode=allow&sslfactory=org.postgresql.ssl.NonValidatingFactory"
# POSTGRES_USER="postgres"
# POSTGRES_PASS="pass"

# Caminhos e URLs
WORKDIR="/var/www/html"
BACKUP_DIR="/backups"
PAGE_URL="https://sisaps.saude.gov.br/esus/"
UPDATE_SCRIPT_PATH="$WORKDIR/update.sh"

# Argumento para escolha do arquivo Docker Compose
DOCKER_COMPOSE_FILE=$1
if [ -z "$DOCKER_COMPOSE_FILE" ]; then
    echo "Erro: É necessário informar o arquivo de configuração Docker Compose como argumento."
    echo "Opções disponíveis: docker-compose.local-db.yml, docker-compose.external-db.yml"
    exit 1
fi

# Data e hora para nomeação do backup
TIMESTAMP=$(date +"%Y%m%d%H%M")
BACKUP_FILE=$BACKUP_DIR/esus_backup_${TIMESTAMP}.backup
LOG_FILE=$BACKUP_DIR/warnings_errors_${TIMESTAMP}.log

# Verifica se o container está rodando
if ! docker compose -f "$DOCKER_COMPOSE_FILE" ps | grep -q "pec"; then
    echo "Erro: O serviço 'pec' não está rodando no arquivo de configuração $DOCKER_COMPOSE_FILE."
    exit 1
fi

# Instala os pacotes necessários no container
echo "Instalando pacotes necessários no container..."
docker compose -f "$DOCKER_COMPOSE_FILE" exec pec sh -c "
    apt-get update && \
    apt-get install -y postgresql-client curl && \
    echo 'Pacotes instalados com sucesso!'
"

# Copia o script de atualização para o container, se não existir
if ! docker compose -f "$DOCKER_COMPOSE_FILE" exec pec [ -f "$UPDATE_SCRIPT_PATH" ]; then
    echo "Copiando o script de atualização para o container..."
    docker compose -f "$DOCKER_COMPOSE_FILE" cp ./update.sh pec:$UPDATE_SCRIPT_PATH
fi

# Executa o script de dentro do container
echo "Executando o script de atualização dentro do container..."
docker compose -f "$DOCKER_COMPOSE_FILE" exec pec sh -c "
    set -e

    # Navega para o diretório de trabalho
    echo 'Navegando para o diretório de trabalho cd $WORKDIR...'
    cd $WORKDIR

    # Remove arquivos .jar existentes
    echo 'Removendo arquivos .jar antigos...'
    rm -f *.jar

    # Captua DB_NAME da URL em DB_URL
    DB_NAME=\$(echo \"\$DB_URL\" | sed -n 's/.*:\/\/.*\/\\([^?]*\\).*/\\1/p')

    # Verifica se DB_NAME foi extraído corretamente
    if [ -z \"\$DB_NAME\" ]; then
        echo 'Erro: Não foi possível capturar o nome do banco de dados a partir de DB_URL.'
        exit 1
    fi

    echo \"Nome do banco de dados capturado: \$DB_NAME\"

    # Busca o link do novo arquivo
    echo 'Buscando o link de download...'
    HTML_CONTENT=\"\$(curl -s '$PAGE_URL')\"
    DOWNLOAD_URL=\"\$(echo \"\$HTML_CONTENT\" | grep -o 'href=\"[^\"]*Linux[^\"]*\"' | sed 's/href=\"//' | sed 's/\"//' | head -1)\"
 
    if [ -z \"\$DOWNLOAD_URL\" ]; then
        echo 'Erro: Link para download não encontrado.'
        exit 1
    fi

    # Completa o link se for relativo
    case \"\$DOWNLOAD_URL\" in
        http*)
            ;;
        *)
            BASE_URL=\$(echo '$PAGE_URL' | sed -n 's#\\(https\\?://[^/]*\\).*#\\1#p')
            DOWNLOAD_URL=\"\$BASE_URL\$DOWNLOAD_URL\"
            ;;
    esac

    # Exibe o link encontrado e baixa o arquivo
    echo \"Link para download encontrado: \$DOWNLOAD_URL\"
    JAR_FILENAME=\$(basename \"\$DOWNLOAD_URL\")
    wget -O \"$WORKDIR/\$JAR_FILENAME\" \"\$DOWNLOAD_URL\"

    # Realiza o backup do banco de dados
    echo 'Realizando backup do banco de dados...'
    env PGPASSWORD=\$POSTGRES_PASS pg_dump -Fc -v -h db -U \$POSTGRES_USER -d \$DB_NAME -f $BACKUP_FILE 2> $LOG_FILE
    echo \"Backup realizado em $BACKUP_FILE\"

    # Filtra apenas warnings e erros no log
    grep -E '(WARNING|ERROR)' $LOG_FILE > $LOG_FILE.filtered && mv $LOG_FILE.filtered $LOG_FILE

    # Removendo arquivo de configuração antigo para permitir instalação sem systemd
    echo 'CAUTION: Removendo arquivo de configuração antigo para permitir instalação sem systemd...'
    if [ -f "/etc/pec.config" ]; then
        cat /etc/pec.config
        rm /etc/pec.config
    fi

    # Atualiza o sistema
    echo 'Atualizando o sistema...'
    # Debugando comando de instalação
    java -jar $WORKDIR/\$JAR_FILENAME -console -url=\$DB_URL -username=\$POSTGRES_USER -password=\$POSTGRES_PASS -continue
"

# Reinicia o container
echo "Reiniciando o container..."
docker compose -f "$DOCKER_COMPOSE_FILE" restart pec

echo "Atualização concluida com sucesso!"