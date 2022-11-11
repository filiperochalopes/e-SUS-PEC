# eSUS PEC

Compatível e testado com  
![version](https://img.shields.io/badge/version-5.0.12-blue) ![version](https://img.shields.io/badge/version-5.0.8-blue) ![version](https://img.shields.io/badge/version-4.5.5-blue) ![version](https://img.shields.io/badge/version-4.2.6-blue) ![version](https://img.shields.io/badge/version-5.0.14-blue)

É um sistema bastante utilizado por profissionais de saúde da Atenção Básica para registros de pacientes e dados de saúde. Esse repositório se propõe a criar uma estrutura docker com linux para viabilizar o deploy do sistema em qualquer ambiente que tenha docker e facilitar a instalação e atualização do sistema [e-SUS PEC](https://sisaps.saude.gov.br/esus/)

## Preparando pacotes

Tenha o [`docker`](https://docs.docker.com/engine/install/) e [`docker-compose`](https://docs.docker.com/compose/install/) instalado na máquina

## Instalando serviço

Para instalação foi criado um script que posse ser executado copiando o bloco abaixo, se você estiver migrando de versão [leia o parágrafo abaixo](#migrando-versao)

```sh
# Substitua eSUS-AB-PEC-5.0.8-Linux64.jar pelo pacote que você baixou no site https://sisaps.saude.gov.br/esus/
sh build.sh -f eSUS-AB-PEC-5.0.8-Linux64.jar
```

## Executando o serviço

Caso o container tenha sido interrompido sem querer, o comando abaixo pode ser útil

```sh
# Em linux
make run
# Depois de rodar novamente os containers
docker-compose up -d
# Caso nenhum dos anteriores funcione execute diretamente o executável do sistema pec
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

## Realizando migração de versão <a id='migrando-versao'></a>

Testado e funcionou após migrar a versão de `4.2.6` para `4.5.5`

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
docker exec -it esus_psql bash
pg_restore -U "postgres" -d "esus" -1 /home/seu_arquivo.backup
```

6. Instale o programa

Fora do container, na pasta raiz do projeto execute, substituindo o nome do pacote `eSUS-AB-PEC-5.0.8-Linux64.jar` para a versão que você vai instalar em sua máquina.

```sh
sh build.sh -f eSUS-AB-PEC-5.0.14-Linux64.jar
```

## Known Issues (Bugs Conhecidos)

- Testes realizados com versão `4.2.7` e `4.2.8` não foram bem sucedidos
- A versão 4.2.8 está com erro no formulário de cadastro, nas requisições ao banco de dados, pelo endpoint graphql, retorna "Não autorizado"
- Verificar sempre a memória caso queira fazer depois em servidor. Senão ele trará no console um `Killed` inesperado https://stackoverflow.com/questions/37071106/spring-boot-application-quits-unexpectedly-with-killed
- Não instale a versão `5.0.8`, do de cabeça, não carrega alguns exames e atendimentos de forma aparentemente aleatória, corrigido após instalar versão `5.0.14`

## Serviço de backup

Para fazer funcionar o serviço de backup na nuvem pelo [Google Drive](https://developers.google.com/drive/api/v3/reference) ela deve estar relacionada a um Google Drive, se assim não for irá armazenar os backups apenas localmente. Para o uso de backup na nuvem é necessário:

1. [Criar uma chave de Client ID Google](https://developers.google.com/drive/api/quickstart/python)
2. Salve o arquivo json baixado com segurança e cole na pasta como `cron/app/credentials.json`
3. Execute 
```sh
make google-oauth
```
Para iniciar autenticação Google e permitir acessos. É necessário para criar o `token.json` que guardará as credenciais. Caso o comando não funcione, provavelmente você não está no linux ou não tem o `python3` instalado no seu linux. **É importante que ao executar o comando você esteja dentro da pasta raiz do projeto.**

Para realizar um teste de backup execute:
```
make cloud-backup
```

As configurações de tempo de expiração de backup estão disponíveis em `env.py`