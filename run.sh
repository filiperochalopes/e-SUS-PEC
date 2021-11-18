#!/bin/sh
chmod +x /opt/e-SUS/webserver/standalone.sh
ss -tl
nohup bash -c "sh /opt/e-SUS/webserver/standalone.sh &" && sleep 4
ss -tl