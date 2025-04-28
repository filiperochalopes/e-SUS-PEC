#!/bin/sh

# ======================================== #
#          Script Atualizado               #
# ======================================== #

# Endpoint novo
ENDPOINT_URL="https://n8n.adri.orango.io/webhook/b1b09703-6eff-42cc-a2a2-8affd46debd3"

# Captura o JSON do endpoint
JSON_RESPONSE=$(curl -s "$ENDPOINT_URL")

# Extrai o valor de "link_linux"
DOWNLOAD_URL=$(echo "$JSON_RESPONSE" | jq -r '.link_linux')

# Verifica se encontrou o link
if [ -z "$DOWNLOAD_URL" ] || [ "$DOWNLOAD_URL" = "null" ]; then
  echo "Erro: Link para download não encontrado no JSON."
  exit 1
fi

# Exibe o link encontrado
echo "Link para download encontrado: $DOWNLOAD_URL"

# Baixa o arquivo
wget "$DOWNLOAD_URL"