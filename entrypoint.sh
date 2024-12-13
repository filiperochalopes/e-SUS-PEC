#!/bin/bash
set -e

# Inicie o servidor HTTPS temporário aqui, se necessário
echo ">> Iniciando servidor temporário na porta 80..."

echo ">> Gerando certificado com CertMgr e instalando o sistema..."
chmod +x ./install.sh
./install.sh

echo ">> Certificado gerado com sucesso. Iniciando aplicação principal..."
exec /opt/e-SUS/webserver/standalone.sh