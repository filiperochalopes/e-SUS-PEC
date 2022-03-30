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
```

## Fazendo backup do banco de dados

```bash
docker exec -it esus_psql bash -c 'pg_dump --host localhost --port 5432 -U "postgres" --format custom --blobs --encoding UTF8 --no-privileges --no-tablespaces --no-unlogged-table-data --file "/home/$(date +"%Y_%m_%d__%H_%M_%S").backup" "esus"'
```

## Restaurando backup

```bash
pg_restore -U "postgres" -d "esus" -1 "/home/seu_arquivo.backup"
```

## Known Issues

- Testes realizados com versão `4.2.7` e `4.2.8` não foram bem sucedidos
- A versão 4.2.8 está com erro no formulário de cadastro, nas requisições ao banco de dados, pelo endpoint graphql, retorna "Não autorizado"
