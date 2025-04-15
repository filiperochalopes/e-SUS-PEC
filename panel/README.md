# [Painel APS](https://saps-ms.github.io/Manual-eSUS_APS/docs/Painel)

É uma aplicação em fase inicial de desenvolvimento para mostrar métricas extraídas do banco de dados do PEC de forma mais dinâmica e intuitiva com a finalidade de facilitar tomada de decisão de profissionais de saúde na atuação descentralizazda e de gestores. É como um Power BI do PEC.

## Configurações

Você deve ter o Docker e Docker Composer instalado na máquina para funcionar

```sh
cp .env.example .env
```

O código do IBGE do seu município você pode consultas [nesse link](https://www.ibge.gov.br/explica/codigos-dos-municipios.php)

```sh
docker compose up -d
```

## Gerando credenciais

```bash
# Gera ADMIN_PASSWORD com 12 caracteres
ADMIN_PASSWORD=$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 12)

# Gera SECRET_TOKEN com 22 caracteres
SECRET_TOKEN=$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 22)

# Gera PASSWORD_SALT fake (formato visual de bcrypt: $2a$12$[22 chars])
PASSWORD_SALT='$2a$12$'$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 22)

# Exibe os resultados
echo "ADMIN_PASSWORD='$ADMIN_PASSWORD'"
echo "SECRET_TOKEN=$SECRET_TOKEN"
echo "PASSWORD_SALT='$PASSWORD_SALT'"
```

## Recomendações

O recomendado é que se utilize um usuário do banco somente de leitura e isso é reforçado [na documentação](https://saps-ms.github.io/Manual-eSUS_APS/docs/Painel/manual_instalacao/). Caso você esteja rodando uma aplicação com banco de dados local instalado junto com o PEC você pode acessar as credenciais no Powershell (Windows):

```powershell
cat 'C:\Program Files\e-SUS\webserver\config\credenciais.txt'
```

Para banco de dados próprios segue uma configuração de usuário com total controle e com apenas leitura e pronto para uso no Painel em um novo banco de dados. Segue script para gerar comando SQL que será executado como superusuário/`postgres`

**Caso de uso**: você vai migrar um banco de dados antigo para o novo ou está criando a instalação do zero em banco de dados externo

```sh
#!/bin/bash

# Definir variáveis
DB_NAME="" # nome do novo banco de dados, 
DB_OWNER="" # nome do usuário novo com acesso total ao banco de dados
READ_ONLY_USER="esus_leitura"
PASSWORD_OWNER=$(openssl rand -base64 30 | tr -d /=+ | cut -c1-20)
PASSWORD_READ_ONLY=$(openssl rand -base64 30 | tr -d /=+ | cut -c1-20)

# Exibir senhas geradas
echo "Senha para o proprietário ($DB_OWNER): $PASSWORD_OWNER"
echo "Senha para o usuário de leitura ($READ_ONLY_USER): $PASSWORD_READ_ONLY"

# Comando SQL para executar no PostgreSQL
SQL_COMMAND=$(cat <<EOF
-- Criando o proprietário do banco de dados
CREATE USER $DB_OWNER WITH PASSWORD '$PASSWORD_OWNER';

-- Criando banco de dados com o proprietário
CREATE DATABASE "$DB_NAME" WITH OWNER = $DB_OWNER ENCODING = 'UTF8';

-- Criando o usuário de leitura
CREATE USER $READ_ONLY_USER WITH PASSWORD '$PASSWORD_READ_ONLY';

-- Permitir conexão ao banco para o usuário de leitura
GRANT CONNECT ON DATABASE "$DB_NAME" TO $READ_ONLY_USER;

-- Permitir uso do esquema public para o usuário de leitura
GRANT USAGE ON SCHEMA public TO $READ_ONLY_USER;

-- Conceder leitura nas tabelas existentes
GRANT SELECT ON ALL TABLES IN SCHEMA public TO $READ_ONLY_USER;

-- Configurar leitura para tabelas futuras
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO $READ_ONLY_USER;
EOF
)

# Executar comandos no PostgreSQL
echo "Executando comandos no PostgreSQL..."
psql -U postgres -c "$SQL_COMMAND"
```
