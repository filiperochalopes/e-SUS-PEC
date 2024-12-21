#!/bin/sh

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color
ARGS=""

# Verificando variáveis de ambiente
if [ -n "$POSTGRES_HOST" ] && [ -n "$POSTGRES_PORT" ] && [ -n "$POSTGRES_DB" ]; then
    DB_URL="jdbc:postgresql://$POSTGRES_HOST:$POSTGRES_PORT/$POSTGRES_DB"
fi

# Echo das variáveis de ambiente
echo -e "${GREEN}\n\n*******************"
echo "Variáveis de ambiente:"
echo "*******************"
echo "HTTPS_DOMAIN: ${HTTPS_DOMAIN}"
echo "DB_URL: ${DB_URL}"
echo "DB_USER: ${DB_USER}"  
echo "DB_PASS: ${DB_PASS}"
echo "JAR_FILENAME: ${JAR_FILENAME}"
echo "TRAINING: ${TRAINING}"
echo "*******************\n\n${NC}"


# Verificando variável de certificado https
if [ -n "$HTTPS_DOMAIN" ]; then
  ARGS="$ARGS -cert-domain=${HTTPS_DOMAIN}"
fi

# Verificando variáveis de banco de dados
if [ -n "$DB_URL" ]; then
  ARGS="$ARGS -url=${DB_URL}" 
fi

if [ -n "$DB_USER" ]; then
  ARGS="$ARGS -username=${DB_USER}"
fi

if [ -n "$DB_PASS" ]; then  
  ARGS="$ARGS -password=${DB_PASS}"
fi

# Verificando variável de treinamento e se não está vazio
if [ -n "$TRAINING" ]; then
  ARGS="$ARGS -treinamento"
fi

# A ser executado java -jar
echo -e "${GREEN}\n\n*******************"
echo "java -jar ${JAR_FILENAME} -console ${ARGS} -continue"
echo "*******************\n\n${NC}"

# Executa o comando
java -jar ${JAR_FILENAME} -console ${ARGS} -continue


# Verificando se a variável de treinamento existe, caso sim, executa o SQL
if [ -n "$TRAINING" ]; then
  echo -e "${GREEN}Treinamento habilitado. Executando SQL de configuração...${NC}"
  PSQL_CMD="psql -h ${POSTGRES_HOST} -p ${POSTGRES_PORT} -U ${DB_USER} -d ${POSTGRES_DB} -c \"update tb_config_sistema set ds_texto = null, ds_inteiro = 1 where co_config_sistema = 'TREINAMENTO';\""
  
  # Exporta a senha do banco para evitar o prompt
  export PGPASSWORD="${DB_PASS}"

  # Executa o comando SQL
  eval $PSQL_CMD
  if [ $? -eq 0 ]; then
    echo -e "${GREEN}Configuração de treinamento aplicada com sucesso.${NC}"
  else
    echo -e "${RED}Erro ao aplicar configuração de treinamento.${NC}"
  fi

  # Limpa a variável de senha para segurança
  unset PGPASSWORD
fi