# Define a variável do domínio
DNS ?= pec.filipelopes.med.br

# Target para gerar SSL
generate-ssl:
	docker run -it --rm --name certbot \
		-v "./certificates:/etc/letsencrypt" \
		-v "/var/lib/letsencrypt:/var/lib/letsencrypt" \
		certbot/certbot certonly \
		--manual --preferred-challenges dns \
		-d $(DNS) \
		--agree-tos --no-eff-email

# Target para converter certificados para JKS e instalar no PEC
install-ssl:
	# Transformação de tipo de chave 
	docker compose exec -it pec sh -c '\
		mkdir -p /opt/e-SUS/webserver/chaves && \
		# Criar PKCS#12 \
		openssl pkcs12 -export -in /certificates/live/$(DNS)/fullchain.pem \
		                -inkey /certificates/live/$(DNS)/privkey.pem \
		                -out /opt/e-SUS/webserver/chaves/keystore.p12 \
		                -name esuspec \
		                -CAfile /certificates/live/$(DNS)/chain.pem \
		                -caname root \
		                -password pass:$(PASS) && \
		# Converter PKCS#12 para JKS \
		keytool -importkeystore -deststorepass $(PASS) \
		        -destkeypass $(PASS) \
		        -destkeystore /opt/e-SUS/webserver/chaves/keystore.jks \
		        -srckeystore /opt/e-SUS/webserver/chaves/keystore.p12 \
		        -srcstoretype PKCS12 \
		        -srcstorepass $(PASS) \
		        -alias esuspec \
	'

	# Colocando configurações no arquivo de configurações
	docker compose exec -it pec sh -c '\
		# Alterando porta \
		sed -i "/^server.port=/d" /opt/e-SUS/webserver/config/application.properties && \
		echo "server.port=443" >> /opt/e-SUS/webserver/config/application.properties && \
		# Alterando tipo de certificado \
		sed -i "/^server.ssl.key-store-type=/d" /opt/e-SUS/webserver/config/application.properties && \
		echo "server.ssl.key-store-type=JKS" >> /opt/e-SUS/webserver/config/application.properties && \
		# Alterando caminho do certificado \
		sed -i "/^server.ssl.key-store=/d" /opt/e-SUS/webserver/config/application.properties && \
		echo "server.ssl.key-store=/opt/e-SUS/webserver/chaves/keystore.jks" >> /opt/e-SUS/webserver/config/application.properties && \
		# Alterando senha do certificado \
		sed -i "/^server.ssl.key-store-password=/d" /opt/e-SUS/webserver/config/application.properties && \
		echo "server.ssl.key-store-password=$(PASS)" >> /opt/e-SUS/webserver/config/application.properties && \
		# Alterando alias do certificado \
		sed -i "/^server.ssl.key-alias=/d" /opt/e-SUS/webserver/config/application.properties && \
		echo "server.ssl.key-alias=esuspec" >> /opt/e-SUS/webserver/config/application.properties && \
		# Alterando flag de SSL \
		sed -i "/^server.ssl.enabled=/d" /opt/e-SUS/webserver/config/application.properties && \
		echo "server.ssl.enabled=true" >> /opt/e-SUS/webserver/config/application.properties \
	'

# Target para executar todas as etapas
all: generate-ssl install-ssl