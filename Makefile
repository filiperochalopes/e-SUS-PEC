prod-run:
	docker-compose down --remove-orphans --volumes
	sudo chmod -R 777 data
	docker-compose up -d
prod-update:
	docker-compose down --remove-orphans --volumes
	sudo chmod -R 777 data
	docker-compose up -d --build
dev-run:
	docker-compose -f docker-compose.dev.yml down --remove-orphans --volumes
	sudo chmod -R 777 data
	docker-compose -f docker-compose.dev.yml up -d
dev-down:
	docker-compose -f docker-compose.dev.yml down --remove-orphans --volumes
dev-logs:
	docker-compose -f docker-compose.dev.yml logs -f
dev-update:
	docker-compose -f docker-compose.dev.yml down --remove-orphans --volumes
	sudo chmod -R 777 data
	docker-compose -f docker-compose.dev.yml up -d --build
terminal:
	docker exec -it esus_app bash
db-terminal:
	docker exec -it esus_psql bash
backup-test:
	docker exec -it esus_cron sh -c "curl localhost:5000/backup-database"
google-oauth:
	cd cron/app; \
		python3 --version; \
		pip3 install virtualenv; \
		virtualenv cron/app/venv; \
		chmod +x ./venv/bin/activate; \
		./venv/bin/activate; \
		pip install -r requirements.txt; \
		python googleoauth.py; \