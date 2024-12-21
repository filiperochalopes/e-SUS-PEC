FROM ubuntu:22.04

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

ARG JAR_FILENAME
ARG HTTPS_DOMAIN
ARG DB_URL
ARG POSTGRES_PASS
ARG POSTGRES_USER
ARG TRAINING

# Promovendo ARGS para ENV para uso no install.sh que roda dentro do entrypoint.sh e precisa dessas variáveis
ENV JAR_FILENAME=${JAR_FILENAME}
ENV TRAINING=${TRAINING}
ENV DB_URL=${DB_URL}
ENV POSTGRES_PASS=${POSTGRES_PASS}
ENV POSTGRES_USER=${POSTGRES_USER}
ENV HTTPS_DOMAIN=${HTTPS_DOMAIN}

# criando diretórios para uso posterior
RUN mkdir -p /opt/e-SUS/webserver/chaves
RUN mkdir /backups
RUN mkdir -p /var/www/html
WORKDIR /var/www/html

COPY ./${JAR_FILENAME} ${JAR_FILENAME}
COPY ./install.sh .

# Copiando arquivos de backup
COPY *.sql /backups
COPY *.backup /backups

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
