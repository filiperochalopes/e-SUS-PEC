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

## Dump databse

```sh
docker exec -it esus_psql bash
export NOW=$(date +%Y_%m_%d_%H_%M_%S)
pg_dump --username=${POSTGRES_USER} -W ${POSTGRES_DB} > /tmp/dumps/${POSTGRES_DB}_${NOW}.sql
```

## Known Issues

- Testes realizados com versão `4.2.7` e `4.2.8` não foram bem sucedidos
- A versão 4.2.8 está com erro no formulário de cadastro, nas requisições ao banco de dados, pelo endpoint graphql, retorna "Não autorizado"
