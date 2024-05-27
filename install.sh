cd /var/www/html

echo "Instalando pacote java ${JAR_FILENAME}"
echo "Verificando variável de treinamento ${TRAINING}"

echo "java -jar ${JAR_FILENAME} -console -url="jdbc:postgresql://psql:5432/${POSTGRES_DATABASE}" -username ${POSTGRES_USERNAME} -password ${POSTGRES_PASSWORD} ${TRAINING}"
java -jar ${JAR_FILENAME} -console -url="jdbc:postgresql://psql:5432/${POSTGRES_DATABASE}" -username ${POSTGRES_USERNAME} -password ${POSTGRES_PASSWORD} ${TRAINING}