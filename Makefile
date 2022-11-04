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
prod-google-api:
	docker exec -it esus_cron sh -c "python /home/app.py"
google-oauth-quickstart:
	docker exec -it esus_cron sh -c "python /home/quickstart.py"