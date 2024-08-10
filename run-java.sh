#!/bin/bash

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Construa os argumentos para o comando
if [ -n "$DUMPFILE" ]; then
  ARGS="-restore=/var/www/html/${DUMPFILE}"
else
  ARGS=""
fi

# A ser executado java -jar
echo -e "${GREEN}\n\n*******************"
echo "java -jar ${JAR_FILENAME} -console -url=${DB_URL} -username=${DB_USER} -password=${DB_PASS} ${ARGS} -continue"
echo "*******************\n\n${NC}"

# Executa o comando
java -jar "${JAR_FILENAME}" -console -url="${DB_URL}" -username="${DB_USER}" -password="${DB_PASS}" ${ARGS} -continue