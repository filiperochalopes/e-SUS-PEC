GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

if [ -n "$DUMPFILE" ]; then
    DUMPFILE_OPT="-restore=${DUMPFILE}"
else
    DUMPFILE_OPT=""
fi

cd /var/www/html

echo "${GREEN}Instalando pacote java ${JAR_FILENAME}${NC}"
echo "Verificando variável de treinamento ${TRAINING}"

echo "\n*******************"
echo "java -jar ${JAR_FILENAME} -console -url="jdbc:postgresql://psql:5432/${POSTGRES_DATABASE}" -username=${POSTGRES_USERNAME} -password=${POSTGRES_PASSWORD} ${DUMPFILE_OPT} ${TRAINING}"
echo "*******************\n"

java -jar ${JAR_FILENAME} -console -url="jdbc:postgresql://psql:5432/${POSTGRES_DATABASE}" -username=${POSTGRES_USERNAME} -password=${POSTGRES_PASSWORD} ${DUMPFILE_OPT} ${TRAINING}