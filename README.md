## Para instalação

Tenha o `docker` e `docker-compose` instalado na máquina

```sh
# No momento, última versão funcional para linux 4.2.6, fazer download em https://rangtecnologia.com.br/downloadsEsus.xhtml
sh build.sh -f eSUS-AB-PEC-4.2.6-Linux64.jar
# Após isso o sistema deve estar funcionando na porta determinada pelo arquivo .env
```

## Para execução

Caso o container tenha sido interrompido sem querer, o comando abaixo pode ser útil

```sh
# Depois de rodar novamente os containers
docker-compose up -d 
docker-compose up -d esus_app /opt/e-SUS/webserver/standalone.sh
```

## Fazendo backup do banco de dados

```bash
docker exec -it esus_psql bash -c 'pg_dump --host localhost --port 5432 -U "postgres" --format custom --blobs --encoding UTF8 --no-privileges --no-tablespaces --no-unlogged-table-data --file "/home/$(date +"%Y_%m_%d__%H_%M_%S").backup" "esus"'
```

## Restaurando backup

```bash
pg_restore -U "postgres" -d "esus" -1 "/home/seu_arquivo.backup"
```

## Realizadno migração de versão

Testado e funcionou após migrar a versão de `4.2.6` para `4.5.3`

1. Crie um backup do banco de dados e retire da pasta `data`
```sh
docker exec -it esus_psql bash -c 'pg_dump --host localhost --port 5432 -U "postgres" --format custom --blobs --encoding UTF8 --no-privileges --no-tablespaces --no-unlogged-table-data --file "/home/$(date +"%Y_%m_%d__%H_%M_%S").backup" "esus"'
sudo cp data/backups/nome_do_arquivo.backup .
```
2. Exclua todo o banco de dados e dados relacionados em volume
```sh
docker-compose down --remove-orphans --volumes
sudo rm -rf data
```
3. Crie o banco de dados
```sh
docker-compose up -d psql
```
4. Copie o arquivo de backup
```sh
sudo cp nome_do_arquivo.backup data/backups/
```
5. Crie o banco de dados com base no backup
```sh
sudo cp nome_do_arquivo.backup data/backups/
```
6. Instale o programa
```sh
sh build.sh -f eSUS-AB-PEC-4.5.3-Linux64.jar
```

## Known Issues

- Testes realizados com versão `4.2.7` e `4.2.8` não foram bem sucedidos
- A versão 4.2.8 está com erro no formulário de cadastro, nas requisições ao banco de dados, pelo endpoint graphql, retorna "Não autorizado"
