#!/bin/bash
set -e

: '
{
  "success" : true,
  "directory" : "/opt/e-SUS",
  "version" : "5.3.19",
  "production" : true,
  "customDatabase" : true,
  "databaseUrl" : "jdbc:postgresql://db:5432/esus",
  "databaseUsername" : "postgres",
  "databasePassword" : "pass",
  "jreVersion" : "17.0.10-linux_x64",
  "jreDirectory" : "/opt/e-SUS/jre/17.0.10-linux_x64",
  "webserverVersion" : "5.3.19",
  "webserverDirectory" : "/opt/e-SUS/webserver"
}
'

# Verifica se o sistema já foi instalado pela conferência da existência de um arquivo /etc/pec.config, caso não exista, instalar
if [ ! -f /etc/pec.config ]; then
    echo ">> Sistema ainda não foi instalado. Instalando..."
    echo ">> Gerando certificado com CertMgr e instalando o sistema..."
    chmod +x ./install.sh
    ./install.sh
fi

# Verifica existe um /etc/pec.config e se a instalação está em sucesso, caso sim, não instala. a estrutura do pec.config no início do arquivo
if [ -f "/etc/pec.config" ]; then
  # Lê o conteúdo do arquivo /etc/pec.config
  config=$(cat /etc/pec.config)
  
  # Verifica se a instalação foi bem-sucedida
  # Se a instalação foi bem-sucedida, o campo "success" deve ser true
  if echo "$config" | grep -q "\"success\" : true"; then
    # Inicie a aplicação principal
    echo ">> Iniciando aplicação principal..."
    exec /opt/e-SUS/webserver/standalone.sh
  else
    # Se a instalação não foi bem-sucedida, exiba uma mensagem de erro
    echo ">> Erro: Instalação não foi bem-sucedida."
    echo ">> Tentando reinstalar sistema..."
    chmod +x ./install.sh
    ./install.sh
    exit 1
  fi
fi

echo ">> Iniciando aplicação principal..."
exec /opt/e-SUS/webserver/standalone.sh