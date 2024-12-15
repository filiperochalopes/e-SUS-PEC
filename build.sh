#!/bin/bash

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

cache=''
filename=''
dumpfile=''
https_domain=''
use_external_db=false
production=false

# Adicionando --help ao build.sh
if [ "$1" = "--help" ]; then
    echo "
    Script para instalação do PEC
    
    Uso: build.sh [-f <nome do arquivo ou URL>] [-d <dump de banco de dados>] [-h <domínio HTTPS>] [-c] [-p] [-e]

    -f {nome do arquivo ou URL} para especificar o arquivo jar a ser utilizado, caso não fornecido, será buscado o último
    -c para utilizar o cache quando estiver rodando build das imagens docker e
    -d para redirecionar a um dump de banco de dados,
    -h para determinar o domínio HTTPS a ser utilizado para gerar o certificado,
    -p para utilizar a instalação em ambiente de produção,
    -e para utilizar banco de dados externo especificado em .env
    
    "
    exit 0
fi

while getopts "d:f:h:cpe" flag; do
    case "${flag}" in
        f) filename=${OPTARG};;
        d) dumpfile=${OPTARG};;
        h) https_domain=${OPTARG};;
        c) cache='--no-cache';;
        p) production=true;;
        e) use_external_db=true;;
        \?)
        echo "${RED}Opção(ões) inválida(s) adicionada(s), apenas

            -f {nome do arquivo ou URL} para especificar o arquivo jar a ser utilizado,
            -c para utilizar o cache quando estiver rodando build das imagens docker e
            -d para redirecionar a um dump de banco de dados,
            -h para determinar o domínio HTTPS a ser utilizado para gerar o certificado,
            -p para utilizar a instalação em ambiente de produção,
            -e para utilizar banco de dados externo

            são consideradas válidas${NC}"
        exit 1
        ;;
    esac
done

# Aumentando o tempo de timeout para não para a instalação
export COMPOSE_HTTP_TIMEOUT=8000

# Carrega variáveis de ambiente
echo "Usando dados de .env"
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
    if [ -z "$filename" ]; then
        filename=$FILENAME
    fi
    if [ -z "$https_domain" ]; then
        https_domain=$HTTPS_DOMAIN
    fi
    if [ -z "$dumpfile" ]; then
        dumpfile=$DUMPFILE
    fi
    echo "Arquivo .env carregado com sucesso."
else
    echo "${RED}Arquivo .env não encontrado.${NC}"
    exit 1
fi

# Verifica se a variável filename existe
if [ -z "$filename" ]; then
    echo "${RED}Arquivo de instalação não foi definido.${NC}"
    echo "${GREEN}Buscando link de instalação na página do PEC...${NC}"
    # URL da página onde está o link
    PAGE_URL="https://sisaps.saude.gov.br/esus/"

    # Captura o conteúdo da página
    HTML_CONTENT=$(curl -s "$PAGE_URL")

    # Extrai o link do arquivo de download para Linux
    # Modifique o padrão se necessário, baseado no conteúdo real da página
    DOWNLOAD_URL=$(echo "$HTML_CONTENT" | grep -o 'href="[^"]*Linux[^"]*' | sed 's/href="//' | head -1)

    # Verifica se encontrou o link
    if [ -z "$DOWNLOAD_URL" ]; then
    echo "Erro: Link para download não encontrado."
    exit 1
    fi

    # Completa o link se for relativo
    case "$DOWNLOAD_URL" in
    http*)
        # O link já é absoluto, não faz nada
        ;;
    *)
        # Constrói o link absoluto a partir da URL base
        BASE_URL=$(echo "$PAGE_URL" | sed -n 's#\(https\?://[^/]*\).*#\1#p')
        DOWNLOAD_URL="$BASE_URL$DOWNLOAD_URL"
        ;;
    esac

    # Exibe o link encontrado
    echo "Link para download encontrado: $DOWNLOAD_URL"
    filename="$DOWNLOAD_URL"
fi

# carregando arquivo de instalação
if echo "$filename" | grep -q '^https://'; then
    # Extrai o nome do arquivo da URL
    jar_filename=$(basename "$filename")
    # Caminho onde o arquivo será salvo
    save_path="./$jar_filename"
    # Verifica se o arquivo já existe
    if [ -f "$save_path" ]; then
        echo "O arquivo $jar_filename já existe nessa pasta de execução. Não será baixado novamente."
    else
        echo "Baixando o arquivo $jar_filename..."
        wget -O "$save_path" "$filename"
        echo "Download concluído."
    fi
else
    # Se filename não é uma URL, assume que é um caminho de arquivo local
    jar_filename="$filename"
fi


echo "${GREEN}Instalando e-SUS-PEC pelo arquivo $jar_filename${NC}"
docker compose -f docker-compose.all-in-one.yml down --volumes --remove-orphans
docker compose -f docker-compose.external-db.yml down --volumes --remove-orphans
docker compose -f docker-compose.split-db.yml down --volumes --remove-orphans

# Verifica se psql está instalado e testa a conexão ao banco de dados
if command -v psql > /dev/null; then
    echo "psql está instalado."
    if $use_external_db; then
        echo "Testando a conexão com o banco de dados externo: $POSTGRES_HOST"
        POSTGRES_HOST_FOR_TEST=$POSTGRES_HOST
        if [ "$POSTGRES_HOST" = "host.docker.internal" ]; then
            POSTGRES_HOST_FOR_TEST=localhost
        fi
        if PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST_FOR_TEST -U $POSTGRES_USER -p $POSTGRES_PORT -d $POSTGRES_DB -c '\q'; then
            echo "Conexão ao banco de dados externa bem-sucedida."
        else
            echo "${RED}Falha ao conectar ao banco de dados externo. Verifique as credenciais e a URL.${NC}"
            exit 1
        fi
    else
        echo "Sem URL do banco de dados externo fornecida, a conexão não será testada."
    fi
else
    echo "${RED}psql não está instalado. A conexão ao banco de dados não pode ser testada.${NC}"
fi

# Por fim instalando o sistema, definindo qual o docker-compose.yml será utilizado
if $use_external_db; then
    # Monta a URL do banco de dados JDBC
    jdbc_url="jdbc:postgresql://$POSTGRES_HOST:$POSTGRES_PORT/$POSTGRES_DB?ssl=true&sslmode=allow&sslfactory=org.postgresql.ssl.NonValidatingFactory" 
    # Se use_external_db é true, é para utilizar um banco de dados externo
    echo "\n\n*******************"
    echo "docker compose --progress plain -f docker-compose.external-db.yml build $cache --build-arg JAR_FILENAME=$jar_filename --build-arg HTTPS_DOMAIN=$https_domain --build-arg DB_URL=$jdbc_url"
    echo "*******************\n\n"
    docker compose --progress plain -f docker-compose.external-db.yml build $cache --build-arg JAR_FILENAME=$jar_filename --build-arg HTTPS_DOMAIN=$https_domain --build-arg DB_URL=$jdbc_url
    docker compose -f docker-compose.external-db.yml up -d
else
    # Roda versão de treinamento
    # training='-treinamento'
    training=''
    jdbc_url="jdbc:postgresql://$POSTGRES_HOST:$POSTGRES_PORT/$POSTGRES_DB" 
    echo "\n\n*******************"
    echo "docker compose --progress plain -f docker-compose.all-in-one.yml build $cache --build-arg JAR_FILENAME=$jar_filename --build-arg HTTPS_DOMAIN=$https_domain --build-arg DB_URL=$jdbc_url --build-arg DUMPFILE=$dumpfile --build-arg TRAINING=$training"
    echo "*******************\n\n"
    docker compose --progress plain -f docker-compose.all-in-one.yml build $cache --build-arg JAR_FILENAME=$jar_filename --build-arg HTTPS_DOMAIN=$https_domain --build-arg DB_URL=$jdbc_url --build-arg DUMPFILE=$dumpfile --build-arg TRAINING=$training
    docker compose -f docker-compose.all-in-one.yml up -d
fi