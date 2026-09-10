#!/bin/sh

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
cd "$PROJECT_ROOT"

# Definição de cores
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Variáveis iniciais
cache=''
filename=''
https_domain=''
use_external_db=false
production=false
cloud_mode=false
restore_file=''
local_compose_file='compose.local-db.yml'
external_compose_file='compose.external-db.yml'
cloud_compose_file='cloud/compose.yml'

compose_override_for() {
    compose_base=$1
    compose_dir=$(dirname "$compose_base")
    echo "$compose_dir/compose.override.yml"
}

compose_run() {
    if [ -n "$compose_override_file" ]; then
        docker compose --env-file "$env_file" \
            -f "$compose_file" -f "$compose_override_file" "$@"
    else
        docker compose --env-file "$env_file" -f "$compose_file" "$@"
    fi
}

compose_run_for() (
    explicit_env_file=$1
    explicit_compose_file=$2
    shift 2
    explicit_override_file=$(compose_override_for "$explicit_compose_file")

    if [ -f "$explicit_override_file" ]; then
        docker compose --env-file "$explicit_env_file" \
            -f "$explicit_compose_file" -f "$explicit_override_file" "$@"
    else
        docker compose --env-file "$explicit_env_file" -f "$explicit_compose_file" "$@"
    fi
)

# Exibe ajuda do script
if [ "${1:-}" = "--help" ]; then
    echo "
    Script para instalação do PEC

    Uso: scripts/build.sh [-f <arquivo ou URL>] [-h <domínio HTTPS>] [-c] [-p] [-e] [-C] [-r <backup>]

    -f {nome do arquivo ou URL} para especificar o arquivo JAR a ser utilizado (busca o último se não informado)
    -c para reconstruir as imagens Docker sem cache
    -h {domínio HTTPS} para gerar o certificado
    -p para instalar em ambiente de produção
    -e para utilizar banco de dados externo especificado em .env
    -C para utilizar a configuração cloud/compose.yml
    -r {arquivo .backup} para restaurar o banco antes de iniciar o PEC

    Quando existir compose.override.yml no mesmo diretório do arquivo Compose
    selecionado, ele será aplicado automaticamente.
    "
    exit 0
fi

# Processa os argumentos
while getopts "f:h:cpeCr:" flag; do
    case "${flag}" in
        f) filename=${OPTARG} ;;
        h) https_domain=${OPTARG} ;;
        c) cache='--no-cache' ;;
        p) production=true ;;
        e) use_external_db=true ;;
        C) cloud_mode=true ;;
        r) restore_file=${OPTARG} ;;
        \?)
            echo "${RED}Opção inválida! Utilize --help para ajuda.${NC}"
            exit 1
            ;;
    esac
done

# Caso o banco de dados for externo modifica a variável logo para produção
if [ "$use_external_db" = true ]; then
    production=true
fi

if [ "$cloud_mode" = true ] && [ "$use_external_db" = true ]; then
    echo "${RED}Erro: -C e -e não podem ser utilizados juntos.${NC}"
    exit 1
fi

if [ -n "$restore_file" ] && [ "$use_external_db" = true ]; then
    echo "${RED}Erro: a restauração automática é suportada apenas com banco local.${NC}"
    exit 1
fi

# Define timeout para o Docker Compose
export COMPOSE_HTTP_TIMEOUT=8000

# Carrega variáveis de ambiente do .env
env_file='.env'
compose_file="$local_compose_file"
backup_dir='esus-data/backups'

if [ "$cloud_mode" = true ]; then
    env_file='cloud/.env'
    compose_file="$cloud_compose_file"
    backup_dir='cloud/esus-data/backups'
elif [ "$use_external_db" = true ]; then
    compose_file="$external_compose_file"
fi

override_candidate=$(compose_override_for "$compose_file")
if [ -f "$override_candidate" ]; then
    compose_override_file=$override_candidate
    echo "${GREEN}Aplicando override: $compose_override_file${NC}"
else
    compose_override_file=''
fi

echo "Carregando variáveis de $env_file..."
if [ -f "$env_file" ]; then
    set -a
    . "./$env_file"
    set +a
    filename=${filename:-${FILENAME:-}}
    https_domain=${https_domain:-${HTTPS_DOMAIN:-}}
    POSTGRES_USER=${POSTGRES_USER:-postgres}
    POSTGRES_PASS=${POSTGRES_PASS:-pass}
    POSTGRES_HOST=${POSTGRES_HOST:-db}
    POSTGRES_PORT=${POSTGRES_PORT:-5432}
    POSTGRES_DB=${POSTGRES_DB:-esus}
    echo "${GREEN}Arquivo $env_file carregado com sucesso.${NC}"
else
    echo "${RED}Arquivo $env_file não encontrado.${NC}"
    exit 1
fi

if [ "$production" = true ]; then
    training=false
else
    training=${TRAINING:-true}
fi

if [ -n "$restore_file" ] && [ ! -f "$restore_file" ]; then
    echo "${RED}Erro: backup não encontrado: $restore_file${NC}"
    exit 1
fi

# Busca o link do arquivo JAR, caso não especificado
if [ -z "$filename" ]; then
    echo "${GREEN}Buscando link de instalação no SISAPS...${NC}"
    
    DOWNLOAD_URL=$("$SCRIPT_DIR/get-latest-pec-release.sh" --url-only)

    if [ -z "$DOWNLOAD_URL" ] || [ "$DOWNLOAD_URL" = "null" ]; then
        echo "${RED}Erro: Link para download não encontrado.${NC}"
        exit 1
    fi

    echo "${GREEN}Link para download encontrado: $DOWNLOAD_URL${NC}"
    filename="$DOWNLOAD_URL"
fi

# Faz o download do arquivo JAR
if echo "$filename" | grep -q '^https://'; then
    jar_filename=$(basename "$filename")
    save_path="./$jar_filename"
    if [ -f "$save_path" ]; then
        echo "O arquivo $jar_filename já existe. Não será baixado novamente."
    else
        echo "Baixando o arquivo $jar_filename..."
        wget -O "$save_path" "$filename"
        echo "${GREEN}Download concluído.${NC}"
    fi
else
    jar_filename="$filename"
fi

# Exibe mensagem de instalação
echo "${GREEN}Instalando e-SUS-PEC com o arquivo $jar_filename...${NC}"

if [ "$cloud_mode" = true ]; then
    if [ -f ".env" ]; then
        compose_run_for .env "$local_compose_file" down --remove-orphans
    fi
else
    if [ -f "cloud/.env" ]; then
        compose_run_for cloud/.env "$cloud_compose_file" down --remove-orphans
    fi
fi

compose_run down --remove-orphans

# Verifica se o psql está disponível
if command -v psql > /dev/null; then
    echo "psql está instalado."
    if $use_external_db; then
        echo "Testando conexão com o banco de dados externo em $POSTGRES_HOST..."
        POSTGRES_HOST_FOR_TEST=$([ "$POSTGRES_HOST" = "host.docker.internal" ] && echo "localhost" || echo "$POSTGRES_HOST")
        if PGPASSWORD=$POSTGRES_PASS psql -h $POSTGRES_HOST_FOR_TEST -U $POSTGRES_USER -p $POSTGRES_PORT -d $POSTGRES_DB -c '\q'; then
            echo "${GREEN}Conexão ao banco de dados externa bem-sucedida.${NC}"
        else
            echo "${RED}Falha ao conectar ao banco de dados externo. Verifique as credenciais.${NC}"
            exit 1
        fi
    else
        echo "Sem banco de dados externo fornecido."
    fi
else
    echo "${RED}psql não está instalado. Conexão ao banco de dados não pode ser testada.${NC}"
fi

# Executa instalação com o Docker Compose correto
if [ "$use_external_db" = true ]; then
    jdbc_url="jdbc:postgresql://$POSTGRES_HOST:$POSTGRES_PORT/$POSTGRES_DB?ssl=true&sslmode=allow&sslfactory=org.postgresql.ssl.NonValidatingFactory"
    echo "\n${GREEN}Construindo e subindo Docker com banco de dados externo...${NC}"
    compose_run --progress plain build $cache \
        --build-arg JAR_FILENAME=$jar_filename \
        --build-arg HTTPS_DOMAIN=$https_domain \
        --build-arg DB_URL=$jdbc_url
    compose_run up -d
else
    jdbc_url="jdbc:postgresql://$POSTGRES_HOST:$POSTGRES_PORT/$POSTGRES_DB"
    echo "\n${GREEN}Construindo e subindo Docker com banco de dados local...${NC}"
    echo "docker compose --progress plain --env-file $env_file -f $compose_file build $cache \
        --build-arg JAR_FILENAME=$jar_filename \
        --build-arg HTTPS_DOMAIN=$https_domain \
        --build-arg DB_URL=$jdbc_url \
        --build-arg TRAINING=$training"
    compose_run --progress plain build $cache \
        --build-arg JAR_FILENAME=$jar_filename \
        --build-arg HTTPS_DOMAIN=$https_domain \
        --build-arg DB_URL=$jdbc_url \
        --build-arg TRAINING=$training

    if [ -n "$restore_file" ]; then
        mkdir -p "$backup_dir"
        backup_name=$(basename "$restore_file")
        case "$restore_file" in
            "$backup_dir"/*) ;;
            *) cp "$restore_file" "$backup_dir/$backup_name" ;;
        esac

        echo "${GREEN}Subindo PostgreSQL para restauração...${NC}"
        compose_run up -d db

        attempts=0
        until compose_run exec -T db \
            pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1; do
            attempts=$((attempts + 1))
            if [ "$attempts" -ge 60 ]; then
                echo "${RED}Erro: PostgreSQL não ficou disponível a tempo.${NC}"
                exit 1
            fi
            sleep 2
        done

        echo "${GREEN}Recriando banco $POSTGRES_DB...${NC}"
        compose_run exec -T db \
            psql -U "$POSTGRES_USER" -d postgres -v ON_ERROR_STOP=1 \
            -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$POSTGRES_DB' AND pid <> pg_backend_pid();"
        compose_run exec -T db \
            dropdb -U "$POSTGRES_USER" --if-exists "$POSTGRES_DB"
        compose_run exec -T db \
            createdb -U "$POSTGRES_USER" "$POSTGRES_DB"

        echo "${GREEN}Restaurando $backup_name...${NC}"
        compose_run exec -T db \
            pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" -1 --no-owner --no-acl \
            "/backups/$backup_name"

        if [ "$cloud_mode" = true ]; then
            echo "${GREEN}Reaplicando acesso de esus_leitura após restauração...${NC}"
            compose_run exec -T db \
                psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
                -f /docker-entrypoint-initdb.d/grant-esus-leitura.sql
        fi

        echo "${GREEN}Restauração concluída. Iniciando PEC...${NC}"
        compose_run up -d pec
    else
        compose_run up -d
    fi
fi
