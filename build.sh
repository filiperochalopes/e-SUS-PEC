while getopts f: flag
do
    case "${flag}" in
        f) filename=${OPTARG};;
    esac
done

export COMPOSE_HTTP_TIMEOUT=8000

echo "Instalando e-SUS-PEC pelo arquivo $filename";
docker-compose down --volumes --remove-orphans
sudo chmod -R 755 data
docker-compose build --no-cache --build-arg JAR_FILENAME=$filename
# docker-compose build --build-arg JARS_FILENAME=$filename
docker-compose up -d
echo "Avaliando estado de execução container"
docker-compose ps
sleep 15
docker-compose ps

# Na hora de fazer o build não pode instalar os pacotes porque depende do banco de dados, por isso deve ser instalado por fora
docker exec -it esus_app bash -c "sh /var/www/html/install.sh"
# Executando novamente o ENTRYPOINT do docker file, dessa vez com os pacotes já instalados.
docker exec -it esus_app bash -c "sh /var/www/html/run.sh"

# sudo cp eSUS-PEC.ico /usr/share/icons/eSUS-PEC.ico
# sudo cp eSUS-PEC.sh /usr/bin/eSUS-PEC.sh
# sudo chmod +x /usr/bin/eSUS-PEC.sh