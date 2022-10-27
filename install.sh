cd /var/www/html

echo "Instalando pacotes java"

java -jar ${JAR_FILENAME} -console -url="jdbc:postgresql://psql:5432/${POSTGRES_DATABASE}" -username ${POSTGRES_USERNAME} -password ${POSTGRES_PASSWORD}