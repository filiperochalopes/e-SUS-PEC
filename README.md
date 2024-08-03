# eSUS PEC

Compatível e testado com  
![version](https://img.shields.io/badge/version-5.2.28-cyan) ![version](https://img.shields.io/badge/version-5.0.12-blue) ![version](https://img.shields.io/badge/version-5.0.8-blue) ![version](https://img.shields.io/badge/version-4.5.5-blue) ![version](https://img.shields.io/badge/version-4.2.6-blue) ![version](https://img.shields.io/badge/version-5.0.14-blue)

É um sistema bastante utilizado por profissionais de saúde da Atenção Básica para registros de pacientes e dados de saúde. Esse repositório se propõe a criar uma estrutura docker com linux para viabilizar o deploy do sistema em qualquer ambiente que tenha docker e facilitar a instalação e atualização do sistema [e-SUS PEC](https://sisaps.saude.gov.br/esus/)

## Instalação TD;LR

Baixe o jar da aplicação e execute o script de instalação para um banco de dados novo, use o argumento `-t` se quiser que a versão instalada seja de treinamento:

```sh
wget https://arquivos.esusab.ufsc.br/PEC/mtRazOmMxfBpkEMK/5.2.28/eSUS-AB-PEC-5.2.28-Linux64.jar
sh build.sh -f eSUS-AB-PEC-5.2.28-Linux64.jar -t
```
Acesse [Live/Demo](https://pec.filipelopes.med.br) 
Dúvidas? Colaboração? Ideias? Entre em contato pelo [WhatsApp](https://wa.me/5571986056232?text=Gostaria+de+informa%C3%A7%C3%B5es+sobre+o+projeto+PEC+SUS)

## Alinhando conhecimentos

Para poder rodar esse sistema é necessário ter conhecimentos básicos dos seguintes programas e ambientes:
- Linux: É o sistema opercional (OS) amplamente utilizado em servidores devido a sua segurança, leveza e versatilidade. Em servidores não temos uma identificação visual de pastas e arquivos, portanto toda a navegação e ações do usuário são por [linhas de código](https://diolinux.com.br/sistemas-operacionais/principais-comandos-do-linux-saiba-o.html)
- [Docker](https://www.youtube.com/watch?v=ntbpIfS44Gw): É um programa que você deve pensar como um container com todos os arquivos dentro para rodar o sistema que você quer rodar ao final, ao colocar o container no seu servidor e rodar ele, deve então funcionar em qualquer ambiente da mesma forma. Isso dispensa o ter que configurar todo o ambiente para receber o programa, pois quem fez o container já fez isso para você.

## Preparando pacotes

Tenha o [`docker`](https://docs.docker.com/engine/install/) e [`docker-compose`](https://docs.docker.com/compose/install/) instalado na máquina

Em uma VPS Ubuntu ou Debian, vamos [instalar o docker](https://docs.docker.com/engine/install/ubuntu/):

```sh
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Para controle dos containers pode ser útil utilizar o [Portainer](https://docs.portainer.io/start/install-ce/server/docker/linux), assim ficará mais fácil verificar os erros e entrar nas aplicações:

```sh
docker volume create portainer_data
docker run -d -p 8000:8000 -p 9443:9443 --name portainer --restart=always -v /var/run/docker.sock:/var/run/docker.sock -v portainer_data:/data portainer/portainer-ce:latest
```

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

Para instalar a versão de treinamento use o argumento `-t`

```sh
sh build.sh -f eSUS-AB-PEC-5.2.28-Linux64.jar -t
```

**Sobre a versão de Treinamento**

[O pacote java disponibilizado](https://sisaps.saude.gov.br/esus/) pelo Ministério da Saúde/Secretaria de Atenção Primária à Saúde. [Laboratório Bridge](https://www.linkedin.com/company/laboratoriobridge/)/Universidade Federal de Santa Catarina. [Página de Suporte](https://esusaps.freshdesk.com/support/login)

```sh
# java -jar {pacote} -help
Usage: <main class> [[-url=<url>] [-username=<username>]
                    [-password=<password>]] [[-restore=<dumpFilePath>]]
                    [[-backup]] [-console] [-continue] [-help] [-treinamento]
      -console               Inicializa o assistente em modo linha de comandos. Se omitido esse parâmetro, o assistente inicializa em modo interface gráfica.
      -treinamento           Indica que a Nova Instalação será de Treinamento. Se omitido esse parâmetro, a Nova Instalação será de Produção.
      -help                  Mostra estas informações sobre a utilização dos parâmetros do assistente.
      -continue              Modo não interativo. Continua com a execução das tarefas necessárias sem a necessidade de confirmação do usuário.

Caso tenha um Banco de Dados instalado, informe os seguintes parâmetros para
Nova Instalação:
      -url=<url>             URL de conexão para acesso ao Banco de Dados
      -username=<username>   Nome de usuário para acesso ao Banco de Dados
      -password=<password>   Senha para acesso ao Banco de Dados

Caso seja uma nova instalação padrão, pode-se utilizar um backup do Banco de
Dados do PEC existente com o seguinte comando:
      -restore=<dumpFilePath>
                             Caminho do arquivo de backup do Banco de Dados do PEC

Caso seja uma atualização de uma instalação padrão, pode ser usado o seguinte
parâmetro:
      -backup                Cria um backup do Banco de Dados antes de atualizar. Se omitido esse parâmetro, não será realizado um backup.
```

## Backup e Restauração de Banco de Dados

### Fazendo backup

```bash
docker compose exec -it psql bash -c 'pg_dump --host localhost --port 5432 -U "postgres" --format custom --blobs --encoding UTF8 --no-privileges --no-tablespaces --no-unlogged-table-data --file "/home/$(date +"%Y_%m_%d__%H_%M_%S").backup" "esus"'
```

### Restaurando backup

```bash
pg_restore -U "postgres" -d "esus" -1 "/home/seu_arquivo.backup"
```

```bash
psql -U postgres esus < backupfile.sql
```

## Migração de Versão PEC <a id='migrando-versao'></a>


⚠️ **Disclaimer**: É importante notar, segundo nota da própria equipe que mantém o PEC, que a migração do banco de dados em sistema linux não tem tantas verificações quanto o Windows, podendo, talvez, existir alguma versão de banco sem a migração adequada. *Testado e funcionou após migrar a versão de `4.2.6` para `4.5.5`* .

1. Crie um backup do banco de dados e retire da pasta `data`

```sh
docker exec -it esus_psql bash -c 'pg_dump --host localhost --port 5432 -U "postgres" --format custom --blobs --encoding UTF8 --no-privileges --no-tablespaces --no-unlogged-table-data --file "/home/$(date +"%Y_%m_%d__%H_%M_%S").backup" "esus"'
sudo cp data/backups/nome_do_arquivo.backup .
```

Ou pode-se optar por fazer o backup pela própria ferramenta do PEC, use:

```sh
java jar esus-pec.jar -help
```
Para mais informações.


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
pg_restore --verbose -U "postgres" -d "esus" -1 /home/seu_arquivo.backup
```

6. Instale o programa

Fora do container, na pasta raiz do projeto execute, substituindo o nome do pacote `eSUS-AB-PEC-5.0.8-Linux64.jar` para a versão que você vai instalar em sua máquina.

```sh
sh build.sh -f eSUS-AB-PEC-5.0.14-Linux64.jar
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
- Não instale a versão `5.0.8`, do de cabeça, não carrega alguns exames e atendimentos de forma aparentemente aleatória, corrigido após instalar versão `5.0.14`

## Serviço de Backup Automático com Google Drive

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