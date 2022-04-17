FROM ubuntu:20.04

RUN apt-get update && apt-get install -y wget apt-utils gnupg2 software-properties-common locales libfreetype6
RUN wget -O- https://apt.corretto.aws/corretto.key | apt-key add - 
RUN add-apt-repository 'deb https://apt.corretto.aws stable main'
RUN apt-get update && apt-get install -y java-1.8.0-amazon-corretto-jdk

# Enable all repositories
RUN sed -i 's/# deb/deb/g' /etc/apt/sources.list

RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    dbus systemd systemd-cron rsyslog iproute2 python python-apt sudo bash ca-certificates && \
    apt-get clean && \
    rm -rf /usr/share/doc/* /usr/share/man/* /var/lib/apt/lists/* /tmp/* /var/tmp/*

ARG JAR_FILENAME
ARG POSTGRES_USERNAME
ARG POSTGRES_PASSWORD
ARG POSTGRES_DATABASE

ENV JAR_FILENAME=${JAR_FILENAME}
ENV POSTGRES_USERNAME=${POSTGRES_USERNAME}
ENV POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
ENV POSTGRES_DATABASE=${POSTGRES_DATABASE}

RUN java -version
RUN mkdir -p /var/www/html
WORKDIR /var/www/html

RUN locale -a
RUN locale-gen "pt_BR.UTF-8"
RUN update-locale 

RUN echo "Copiando arquivo de instalação $JAR_FILENAME"

COPY ./${JAR_FILENAME} ${JAR_FILENAME}
COPY ./install.sh install.sh
COPY ./run.sh run.sh

RUN chmod +x /var/www/html/install.sh
RUN chmod +x /var/www/html/run.sh

EXPOSE 8080

CMD "/var/www/html/run.sh"