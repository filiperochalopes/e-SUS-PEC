FROM python:alpine3.16

# instalando dependências para o container
RUN apk add --no-cache postgresql-client

# Copiando arquivos de uso do cron
ADD crontab.txt /crontab.txt
ADD script.sh /script.sh
COPY entry.sh /entry.sh
RUN chmod 755 /script.sh /entry.sh
RUN /usr/bin/crontab /crontab.txt

# Criando o cenário para rodar a aplicação python
WORKDIR /home
COPY app .
COPY wsgi.py /
RUN pip install -r requirements.txt

WORKDIR /
CMD ["/entry.sh"]