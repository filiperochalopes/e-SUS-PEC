#!/bin/sh

# start python app
gunicorn --bind 0.0.0.0:5000 -D --enable-stdio-inheritance --capture-output --log-level debug --reload wsgi:app
# start cron
/usr/sbin/crond -f -l 8