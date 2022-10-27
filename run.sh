#!/bin/sh

echo "Inicializando configuração de data e hora..."
ntpd -gq
service ntp start

echo "Ajustando data para $TIMEZONE ..."
echo $TIMEZONE > /etc/timezone && \
ln -sf /usr/share/zoneinfo/${TIMEZONE} /etc/localtime && \
dpkg-reconfigure -f noninteractive tzdata

echo "Inicializando sistema..."
FILE=/opt/e-SUS/webserver/standalone.sh

if test -f "$FILE"; then
    echo "$FILE existe. Executando entrypoint do eSUS-PEC"
    if ss -tulpn | grep 8080 > /dev/null ; then
        echo "Já tem uma aplicação rodando na porta 8080, mantendo terminal aberto."
    else
        echo "Nada rodando em 8080, executando entrada..."
        chmod +x /opt/e-SUS/webserver/standalone.sh
        nohup /opt/e-SUS/webserver/standalone.sh & tail -f nohup.out
    fi
else
    printf "$FILE não existe, execute manualmente o sistema com\n \
    sh /opt/e-SUS/webserver/standalone.sh\n\n \
    ou instale o sitema primeiro, caso seja a primeira vez instalando:\n\n
    sh /install.sh"
fi

/bin/bash