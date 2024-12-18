FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    locales \
    && locale-gen "pt_BR.UTF-8" \
    && dpkg-reconfigure --frontend=noninteractive locales \
    && apt-get install -y \
    wget apt-utils gnupg2 software-properties-common file libfreetype6 ntp

# Instalando java 8, pre-requisitos para instalação do sistema PEC
RUN wget -O- https://apt.corretto.aws/corretto.key | apt-key add - 
RUN add-apt-repository 'deb https://apt.corretto.aws stable main'
RUN apt-get update && apt-get install -y java-1.8.0-amazon-corretto-jdk

# Enable all repositories
RUN sed -i 's/# deb/deb/g' /etc/apt/sources.list

# Instalações para uso do cron e configurações para utilização do systemd
RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    dbus systemd systemd-cron rsyslog iproute2 python-is-python3 python3 python3-apt sudo bash ca-certificates && \
    apt-get clean && \
    rm -rf /usr/share/doc/* /usr/share/man/* /var/lib/apt/lists/* /tmp/* /var/tmp/*

ARG JAR_FILENAME
ARG TRAINING
ARG POSTGRES_USERNAME
ARG POSTGRES_PASSWORD
ARG POSTGRES_DATABASE
ARG TZ
ARG DUMPFILE

ENV JAR_FILENAME=${JAR_FILENAME}
ENV DUMPFILE=${DUMPFILE}
ENV TRAINING=${TRAINING}
ENV POSTGRES_USERNAME=${POSTGRES_USERNAME}
ENV POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
ENV POSTGRES_DATABASE=${POSTGRES_DATABASE}
ENV TZ=${TZ}

RUN export JAR_FILENAME=${JAR_FILENAME}

RUN mkdir -p /var/www/html
WORKDIR /var/www/html

COPY ./${JAR_FILENAME} ${JAR_FILENAME}
COPY ./${DUMPFILE} ${DUMPFILE}
COPY ./install.sh install.sh
COPY ./run.sh run.sh

RUN chmod +x /var/www/html/install.sh
RUN chmod +x /var/www/html/run.sh

CMD ["/bin/bash", "/var/www/html/run.sh"]
