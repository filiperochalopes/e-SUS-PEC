#!/bin/sh

# URL da página onde está o link
PAGE_URL="https://sisaps.saude.gov.br/esus/"

# Captura o conteúdo da página
HTML_CONTENT=$(curl -s "$PAGE_URL")

# Extrai o link do arquivo de download para Linux
# Modifique o padrão se necessário, baseado no conteúdo real da página
DOWNLOAD_URL=$(echo "$HTML_CONTENT" | grep -o 'href="[^"]*Linux[^"]*' | sed 's/href="//' | head -1)

# Verifica se encontrou o link
if [ -z "$DOWNLOAD_URL" ]; then
  echo "Erro: Link para download não encontrado."
  exit 1
fi

# Completa o link se for relativo
case "$DOWNLOAD_URL" in
  http*)
    # O link já é absoluto, não faz nada
    ;;
  *)
    # Constrói o link absoluto a partir da URL base
    BASE_URL=$(echo "$PAGE_URL" | sed -n 's#\(https\?://[^/]*\).*#\1#p')
    DOWNLOAD_URL="$BASE_URL$DOWNLOAD_URL"
    ;;
esac

# Exibe o link encontrado
echo "Link para download encontrado: $DOWNLOAD_URL"