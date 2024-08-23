generate-ssl:
	# Verifica se a URL foi fornecida
	@if [ -z "$(url)" ]; then \
		echo "Erro: É necessário fornecer a URL."; \
		exit 1; \
	fi

	# Verifica se o email foi fornecido
	@if [ -z "$(email)" ]; then \
		echo "Erro: É necessário fornecer o email."; \
		exit 1; \
	fi

	# Criação do certificado SSL usando Certbot
	docker compose exec -it nginx sh -c "certbot certonly --webroot -w /var/www/certbot -d $(url) --email $(email) --agree-tos --non-interactive"

	# Colocar o certificado no nginx.conf
	docker compose exec -it nginx sh -c "sed -i 's|# ssl_certificate /etc/ssl/certs/ssl-cert-snakeoil.pem;|ssl_certificate /etc/letsencrypt/live/$(url)/fullchain.pem;|' /etc/nginx/nginx.conf"
	docker compose exec -it nginx sh -c "sed -i 's|# ssl_certificate_key /etc/ssl/private/ssl-cert-snakeoil.key;|ssl_certificate_key /etc/letsencrypt/live/$(url)/privkey.pem;|' /etc/nginx/nginx.conf"

	# Reiniciar Nginx no container
	docker compose exec -it nginx sh -c "nginx -s reload"

	# Instalar certificado no PEC
	docker compose exec -it pec sh -c "cp /etc/letsencrypt/live/$(url)/fullchain.pem /opt/e-SUSwebserver/config/"
	docker compose exec -it pec sh -c "cp /etc/letsencrypt/live/$(url)/privkey.pem /opt/e-SUSwebserver/config/"
	docker compose exec -it pec sh -c "sed -i '\$$a\server.port=443' /opt/e-SUSwebserver/config/application.properties"
	docker compose exec -it pec sh -c "sed -i '\$$a\server.ssl.key-store-type=PKCS12' /opt/e-SUSwebserver/config/application.properties"
	docker compose exec -it pec sh -c "sed -i '\$$a\server.ssl.key-store=/opt/e-SUSwebserver/config/fullchain.pem' /opt/e-SUSwebserver/config/application.properties"
	docker compose exec -it pec sh -c "sed -i '\$$a\server.ssl.key-store-password=REPLACE_WITH_PASSWORD' /opt/e-SUSwebserver/config/application.properties"
	docker compose exec -it pec sh -c "sed -i '\$$a\server.ssl.key-alias=$(url)' /opt/e-SUSwebserver/config/application.properties"
	docker compose exec -it pec sh -c "sed -i '\$$a\security.require-ssl=true' /opt/e-SUSwebserver/config/application.properties"
