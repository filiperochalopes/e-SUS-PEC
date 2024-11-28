#!/bin/bash
set -e

echo ">> Iniciando servidor temporário na porta 80..."
# Inicie o servidor HTTP temporário aqui, se necessário

echo ">> Gerando certificado com CertMgr..."
chmod +x ./run-java.sh
./run-java.sh

echo ">> Certificado gerado com sucesso. Iniciando aplicação principal..."
exec /opt/e-SUS/webserver/standalone.sh