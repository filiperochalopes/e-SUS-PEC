FROM python:slim-buster

RUN apt-get update \
    && apt-get install gcc cron nginx -y \
    && apt-get clean

COPY requirements.txt /app/requirements.txt
WORKDIR /app
RUN pip install -r requirements.txt
COPY . .

# Configure nginx
COPY ./nginx.conf /etc/nginx/sites-enabled/default

# Configure cron
COPY ./crontab /etc/cron.d/default

COPY ./start.sh /
RUN chmod +x /start.sh

EXPOSE 5000 80

CMD ["/start.sh"]