#!/bin/sh

# Variáveis
WORKDIR="/var/www/html"
BACKUP_DIR="/backups"
ENDPOINT_URL="https://n8n.adri.orango.io/webhook/b1b09703-6eff-42cc-a2a2-8affd46debd3"
UPDATE_SCRIPT_PATH="$WORKDIR/update.sh"

# Argumento para escolha do docker-compose
DOCKER_COMPOSE_FILE=$1
if [ -z "$DOCKER_COMPOSE_FILE" ]; then
    echo "Erro: Informe o docker-compose.yml como argumento."
    echo "Exemplo: docker-compose.local-db.yml ou docker-compose.external-db.yml"
    exit 1
fi

# Data e hora para nomeação do backup
TIMESTAMP=$(date +"%Y%m%d%H%M")
BACKUP_FILE="$BACKUP_DIR/esus_backup_${TIMESTAMP}.backup"
LOG_FILE="$BACKUP_DIR/warnings_errors_${TIMESTAMP}.log"

# Verifica se o serviço 'pec' está rodando
if ! docker compose -f "$DOCKER_COMPOSE_FILE" ps | grep -q "pec"; then
    echo "Erro: Serviço 'pec' não está ativo em $DOCKER_COMPOSE_FILE."
    exit 1
fi

# Instala pacotes no container
echo "Instalando pacotes no container..."
docker compose -f "$DOCKER_COMPOSE_FILE" exec pec sh -c "
    apt-get update && apt-get install -y postgresql-client curl jq
"

# Copia script de atualização se necessário
if ! docker compose -f "$DOCKER_COMPOSE_FILE" exec pec [ -f "$UPDATE_SCRIPT_PATH" ]; then
    echo "Copiando o update.sh para o container..."
    docker compose -f "$DOCKER_COMPOSE_FILE" cp ./update.sh pec:$UPDATE_SCRIPT_PATH
fi

# Executa o script de atualização
echo "Executando o update.sh dentro do container..."
docker compose -f "$DOCKER_COMPOSE_FILE" exec pec sh -c "
    set -e

    cd $WORKDIR

    echo 'Removendo arquivos .jar antigos...'
    rm -f *.jar

    # Captura nome do banco da URL
    DB_NAME=\$(echo \"\$DB_URL\" | sed -n 's#.*/\\([^?]*\\).*#\\1#p')
    if [ -z \"\$DB_NAME\" ]; then
        echo 'Erro: Banco de dados não identificado na variável DB_URL.'
        exit 1
    fi
    echo \"Banco de dados: \$DB_NAME\"

    # Buscar novo link de instalação via endpoint
    echo 'Buscando link de download via JSON...'
    JSON_RESPONSE=\$(curl -s \"$ENDPOINT_URL\")
    DOWNLOAD_URL=\$(echo \"\$JSON_RESPONSE\" | jq -r '.link_linux')

    if [ -z \"\$DOWNLOAD_URL\" ] || [ \"\$DOWNLOAD_URL\" = \"null\" ]; then
        echo 'Erro: Link de download não encontrado.'
        exit 1
    fi

    echo \"Link encontrado: \$DOWNLOAD_URL\"
    JAR_FILENAME=\$(basename \"\$DOWNLOAD_URL\")
    wget -O \"$WORKDIR/\$JAR_FILENAME\" \"\$DOWNLOAD_URL\"

    # Backup do banco
    echo 'Realizando backup...'
    env PGPASSWORD=\$POSTGRES_PASS pg_dump -Fc -v -h db -U \$POSTGRES_USER -d \$DB_NAME -f $BACKUP_FILE 2> $LOG_FILE
    echo \"Backup salvo em $BACKUP_FILE\"

    # Filtra apenas warnings e errors
    grep -Ei 'warning|error' $LOG_FILE > ${LOG_FILE}.filtered && mv ${LOG_FILE}.filtered $LOG_FILE

    # Remove /etc/pec.config se existir
    if [ -f \"/etc/pec.config\" ]; then
        echo 'Removendo /etc/pec.config antigo...'
        cat /etc/pec.config
        rm -f /etc/pec.config
    fi

    # Atualiza sistema
    echo 'Rodando atualização via novo JAR...'
    java -jar \"$WORKDIR/\$JAR_FILENAME\" -console -url=\$DB_URL -username=\$POSTGRES_USER -password=\$POSTGRES_PASS -continue
"

# Reinicia container
echo "Reiniciando container pec..."
docker compose -f "$DOCKER_COMPOSE_FILE" restart pec

echo "✅ Atualização concluída com sucesso!"