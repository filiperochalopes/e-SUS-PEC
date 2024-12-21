#!/bin/sh

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color
ARGS=""

# Verificando variáveis de ambiente
if [ -n "$POSTGRES_HOST" ] && [ -n "$POSTGRES_PORT" ] && [ -n "$POSTGRES_DB" ]; then
    DB_URL="jdbc:postgresql://$POSTGRES_HOST:$POSTGRES_PORT/$POSTGRES_DB"
fi

# Captura JAR_FILENAME de /etc/jar_install_filename
JAR_FILENAME=$(cat /etc/jar_install_filename | grep JAR_FILENAME | cut -d '=' -f2)

# Echo das variáveis de ambiente
echo -e "${GREEN}\n\n*******************"
echo "Variáveis de ambiente:"
echo "*******************"
echo "DB_URL: ${DB_URL}"
echo "POSTGRES_USER: ${POSTGRES_USER}"  
echo "POSTGRES_PASS: ${POSTGRES_PASS}"
echo "JAR_FILENAME: ${JAR_FILENAME}"
echo "TRAINING: ${TRAINING}"
echo "*******************\n\n${NC}"

# Verificando variáveis de banco de dados
if [ -n "$DB_URL" ]; then
  ARGS="$ARGS -url=${DB_URL}" 
fi

if [ -n "$POSTGRES_USER" ]; then
  ARGS="$ARGS -username=${POSTGRES_USER}"
fi

if [ -n "$POSTGRES_PASS" ]; then  
  ARGS="$ARGS -password=${POSTGRES_PASS}"
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
  PSQL_CMD="psql -h ${POSTGRES_HOST} -p ${POSTGRES_PORT} -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c \"update tb_config_sistema set ds_texto = null, ds_inteiro = 1 where co_config_sistema = 'TREINAMENTO';\""
  
  # Exporta a senha do banco para evitar o prompt
  export PGPASSWORD="${POSTGRES_PASS}"

  # Executa o comando SQL
  eval $PSQL_CMD
  if [ $? -eq 0 ]; then
    echo -e "${GREEN}Configuração de treinamento aplicada com sucesso!${NC}"
  else
    echo -e "${RED}Erro ao aplicar configuração de treinamento.${NC}"
  fi

  # Limpa a variável de senha para segurança
  unset PGPASSWORD
fi