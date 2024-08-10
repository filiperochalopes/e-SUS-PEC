#!/bin/bash

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

training=''
cache=''
filename=''
dumpfile=''
use_external_db=false

while getopts "d:f:tce" flag; do
    case "${flag}" in
        f) filename=${OPTARG};;
        t) training='-treinamento';;
        d) dumpfile=${OPTARG};;
        c) cache='--no-cache';;
        e) use_external_db=true;;
        \?)
        echo "${RED}Opção(ões) inválida(s) adicionada(s), apenas

            -f {nome do arquivo ou URL} para especificar o arquivo jar a ser utilizado,
            -c para utilizar o cache quando estiver rodando build das imagens docker e
            -d para redirecionar a um dump de banco de dados,
            -t para versão de treinamento,
            -e para utilizar banco de dados externo especificado em .env.external-db
            são consideradas válidas${NC}"
        exit 1
        ;;
    esac
done

export COMPOSE_HTTP_TIMEOUT=8000

# Carrega variáveis do arquivo .env.external-db se necessário
if $use_external_db; then
    echo "Usando banco de dados externo especificado em .env.external-db"
    if [ -f ".env.external-db" ]; then
        export $(grep -v '^#' .env.external-db | xargs)
        filename=$FILENAME
    else
        echo "${RED}Arquivo .env.external-db não encontrado.${NC}"
        exit 1
    fi
fi

# Verifica se filename é uma URL
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
docker compose down --volumes --remove-orphans
sudo chmod -R 755 data

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

if $use_external_db; then
    # Monta a URL do banco de dados JDBC
    jdbc_url="jdbc:postgresql://$POSTGRES_HOST:$POSTGRES_PORT/$POSTGRES_DB?ssl=true&sslmode=allow&sslfactory=org.postgresql.ssl.NonValidatingFactory" 
    # Se use_external_db é true, é para utilizar um banco de dados externo
    echo "\n\n*******************"
    echo "docker compose --progress plain -f docker-compose.external-db.yml build $cache --build-arg JAR_FILENAME=$jar_filename --build-arg DB_URL=$jdbc_url"
    echo "*******************\n\n"
    docker compose --progress plain -f docker-compose.external-db.yml build $cache --build-arg JAR_FILENAME=$jar_filename --build-arg DB_URL=$jdbc_url
    docker compose -f docker-compose.external-db.yml up -d
else
    # Se use_external_db é false, não é para utilizar um banco de dados externo
    echo "\n\n*******************"
    echo "docker compose build $cache --build-arg JAR_FILENAME=$jar_filename --build-arg DUMPFILE=$dumpfile --build-arg TRAINING=$training"
    echo "*******************\n\n"
    docker compose build $cache --build-arg JAR_FILENAME=$jar_filename --build-arg DUMPFILE=$dumpfile --build-arg TRAINING=$training
    docker compose up -d

    echo "Avaliando estado de execução do container"
    docker compose ps
    # Aguardando container do banco de dados ficar pronto
    sleep 15
    docker compose ps

    # Na hora de fazer o build não pode instalar os pacotes porque depende do banco de dados, por isso deve ser instalado por fora
    echo "${GREEN}Instalando pacotes do e-SUS-PEC${NC}"
    docker exec -it esus_app bash -c "sh /var/www/html/install.sh"
    # Executando novamente o ENTRYPOINT do docker file, dessa vez com os pacotes já instalados.
    echo "${GREEN}Executando entrypoint do e-SUS-PEC${NC}"
    docker exec -it esus_app bash -c "sh /var/www/html/run.sh"
fi
