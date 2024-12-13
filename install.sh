#!/bin/bash

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color
ARGS=""

# Echo das variáveis de ambiente
echo -e "${GREEN}\n\n*******************"
echo "Variáveis de ambiente:"
echo "*******************"
echo "HTTPS_DOMAIN: ${HTTPS_DOMAIN}"
echo "DB_URL: ${DB_URL}"
echo "DB_USER: ${DB_USER}"  
echo "DB_PASS: ${DB_PASS}"
echo "JAR_FILENAME: ${JAR_FILENAME}"
echo "DUMPFILE: ${DUMPFILE}"
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

# Construa os argumentos para o comando
if [ -n "$DUMPFILE" ]; then
  ARGS="-restore=/backups/${DUMPFILE}"
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