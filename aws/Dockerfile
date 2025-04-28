FROM ubuntu:24.04.2

ENV DEBIAN_FRONTEND=noninteractive

# Instalando fontes que o PEC utiliza para impressão: ttf-mscorefonts-installer (limitação de versão 5.3.19-5.3.21)
# fontconfig para reinstalar fontes após modificação
# coreutils para reconhecer arquitetura x64
RUN apt-get update && apt-get install -y \
    locales \
    && locale-gen "pt_BR.UTF-8" \
    && dpkg-reconfigure --frontend=noninteractive locales \
    && apt-get install -y \
    coreutils wget apt-utils gnupg2 software-properties-common file libfreetype6 ntp ttf-mscorefonts-installer fontconfig

RUN fc-cache -fv

RUN chmod -R 777 /usr/share/fonts/truetype/msttcorefonts

# Adicionar chave pública diretamente da URL correta
RUN wget -O - https://apt.corretto.aws/corretto.key | gpg --dearmor -o /usr/share/keyrings/corretto-keyring.gpg

# Adicionar o repositório do Corretto, vinculando à chave
RUN echo "deb [signed-by=/usr/share/keyrings/corretto-keyring.gpg] https://apt.corretto.aws stable main" | tee /etc/apt/sources.list.d/corretto.list

# Atualizar repositórios e instalar o Corretto 17 LTS
RUN apt-get update && apt-get install -y java-17-amazon-corretto-jdk

# Enable all repositories
RUN sed -i 's/# deb/deb/g' /etc/apt/sources.list

# Instalações para uso do cron e configurações para utilização do systemd
RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    dbus systemd systemd-cron rsyslog iproute2 python-is-python3 python3 python3-apt sudo bash ca-certificates && \
    apt-get clean && \
    rm -rf /usr/share/doc/* /usr/share/man/* /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Instalar cliente PostgreSQL
RUN apt-get update && apt-get install -y postgresql-client

# Criando diretórios para uso posterior
RUN mkdir -p /opt/e-SUS/webserver/chaves
RUN mkdir -p /var/www/html
RUN mkdir /backups

# Entrando no diretório de trabalho
WORKDIR /var/www/html

# Baixando o último PEC disponível
RUN apt-get update && apt-get install -y curl jq && \
    ENDPOINT_URL="https://n8n.adri.orango.io/webhook/b1b09703-6eff-42cc-a2a2-8affd46debd3" && \
    JSON_RESPONSE=$(curl -s "$ENDPOINT_URL") && \
    DOWNLOAD_URL=$(echo "$JSON_RESPONSE" | jq -r '.link_linux') && \
    if [ -z "$DOWNLOAD_URL" ] || [ "$DOWNLOAD_URL" = "null" ]; then \
        echo "Erro: Link para download não encontrado."; \
        exit 1; \
    fi && \
    echo "Link para download encontrado: $DOWNLOAD_URL" && \
    JAR_FILENAME=$(basename "$DOWNLOAD_URL") && \
    if [ -f "/var/www/html/$JAR_FILENAME" ]; then \
        echo "O arquivo $JAR_FILENAME já existe e não será baixado novamente."; \
    else \
        wget -O "/var/www/html/$JAR_FILENAME" "$DOWNLOAD_URL"; \
        echo "Download concluído: $JAR_FILENAME"; \
    fi && \
    echo "JAR_FILENAME=$JAR_FILENAME" > /etc/jar_install_filename

# Substituir o comando `ps` para burlar a verificação de systemd
RUN mv /bin/ps /bin/ps.original && \
    echo '#!/bin/sh' > /bin/ps && \
    echo 'if [ "$1" = "--no-headers" ] && [ "$2" = "-o" ] && [ "$3" = "comm" ] && [ "$4" = "1" ]; then' >> /bin/ps && \
    echo '    echo "systemd (simulated: ps $@)"' >> /bin/ps && \
    echo 'else' >> /bin/ps && \
    echo '    /bin/ps.original "$@"' >> /bin/ps && \
    echo 'fi' >> /bin/ps && \
    chmod +x /bin/ps

RUN echo '#!/bin/sh' > /bin/systemctl && \
    echo 'echo "Simulated systemctl command: $0 $@"' >> /bin/systemctl && \
    echo 'case "$1" in' >> /bin/systemctl && \
    echo '  start|stop|restart|status) exit 0 ;;' >> /bin/systemctl && \
    echo '  *) echo "Simulated systemctl: $@"; exit 0 ;;' >> /bin/systemctl && \
    echo 'esac' >> /bin/systemctl && \
    chmod +x /bin/systemctl

# Copiando arquivos de backup
COPY *.sql /backups
COPY *.backup /backups

COPY ./install.sh .
COPY ./entrypoint.sh .
RUN chmod +x ./entrypoint.sh ./install.sh

RUN ls -la

ENTRYPOINT ["/var/www/html/entrypoint.sh"]