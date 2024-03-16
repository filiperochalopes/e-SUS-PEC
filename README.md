# eSUS PEC

É um sistema bastante utilizado por profissionais de saúde da Atenção Básica para registros de pacientes e dados de saúde. Esse repositório se propõe a criar uma estrutura docker com linux para viabilizar o deploy do sistema em qualquer ambiente que tenha docker e facilitar a instalação e atualização.

## Alinhando conhecimentos

Para poder rodar esse sistema é necessário ter conhecimentos básicos dos seguintes programas e ambientes:
- Linux: É o sistema opercional (OS) amplamente utilizado em servidores devido a sua segurança, leveza e versatilidade. Em servidores não temos uma identificação visual de pastas e arquivos, portanto toda a navegação e ações do usuário são por [linhas de código](https://diolinux.com.br/sistemas-operacionais/principais-comandos-do-linux-saiba-o.html)
- Docker: É um programa que você deve pensar como um container com todos os arquivos dentro para rodar o sistema que você quer rodar ao final, ao colocar o container no seu servidor e rodar ele, deve então funcionar em qualquer ambiente da mesma forma. Isso dispensa o ter que configurar todo o ambiente para receber o programa, pois quem fez o container já fez isso para você.

## Preparando pacotes

Tenha o [`docker`](https://docs.docker.com/engine/install/) e [`docker-compose`](https://docs.docker.com/compose/install/) instalado na máquina

## Instalação do PEC

Para instalação foi criado um script que posse ser executado copiando o bloco abaixo, se você estiver migrando de versão [leia o parágrafo abaixo](#migrando-versao)

### 1. Baixe o pacote do programa PEC na versão que deseja instalar/atualizar. Você pode também [baixar no site oficial do PEC APS](https://sisaps.saude.gov.br/esus)

```sh
wget https://arquivos.esusab.ufsc.br/PEC/mtRazOmMxfBpkEMK/5.2.28/eSUS-AB-PEC-5.2.28-Linux64.jar
```

Gostaria de migrar de outro banco de dados? [Acesse a seção de migração](#migrando-versao) 

### 2. Rode o script para instalar o pacote baixado e criar o container

```sh
sh build.sh -f eSUS-AB-PEC-5.2.28-Linux64.jar
```

## Backup e Restauração de Banco de Dados

### Fazendo backup

```bash
docker exec -it esus_psql bash -c 'pg_dump --host localhost --port 5432 -U "postgres" --format custom --blobs --encoding UTF8 --no-privileges --no-tablespaces --no-unlogged-table-data --file "/home/$(date +"%Y_%m_%d__%H_%M_%S").backup" "esus"'
```

### Restaurando backup

```bash
pg_restore -U "postgres" -d "esus" -1 "/home/seu_arquivo.backup"
```

## Migração de Versão PEC <a id='migrando-versao'></a>

**Disclaimer: É importante notar, segundo nota da própria equipe que mantém o PEC, que a migração do banco de dados em sistema linux não tem tantas verificações quanto o Windows, podendo, talvez, existir alguma versão de banco sem a migração adequada. *Testado e funcionou após migrar a versão de `4.2.6` para `4.5.5`* **

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
sh build.sh -f eSUS-AB-PEC-5.0.8-Linux64.jar
```

## Comandos interessantes

Caso o container tenha sido interrompido sem querer, o comando abaixo pode ser útil

```sh
# Em linux
make run
# Depois de rodar novamente os containers
docker-compose up -d
# Caso nenhum dos anteriores funcione execute diretamente o executável do sistema pec
docker-compose up -d esus_app /opt/e-SUS/webserver/standalone.sh
```

## Known Issues (Bugs Conhecidos)

- Testes realizados com versão `4.2.7` e `4.2.8` não foram bem sucedidos
- A versão 4.2.8 está com erro no formulário de cadastro, nas requisições ao banco de dados, pelo endpoint graphql, retorna "Não autorizado"
- Verificar sempre a memória caso queira fazer depois em servidor. Senão ele trará no console um `Killed` inesperado https://stackoverflow.com/questions/37071106/spring-boot-application-quits-unexpectedly-with-killed
