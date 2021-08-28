while getopts f: flag
do
    case "${flag}" in
        f) filename=${OPTARG};;
    esac
done

echo "Instalando e-SUS-PEC pelo arquivo $filename";
sudo chmod -R 755 data
docker-compose down --volumes --remove-orphans
docker-compose build --no-cache --build-arg JAR_FILENAME=$filename
docker-compose up -d
docker exec -it esus_app bash -c "sh /var/www/html/install.sh"
docker exec -it esus_app bash -c "sh /var/www/html/run.sh"