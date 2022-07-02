prod_run:
	docker-compose -f docker-compose.prod.yml down --remove-orphans --volumes
	docker-compose down --remove-orphans --volumes
	sudo chmod -R 777 data
	docker-compose -f docker-compose.prod.yml up -d
prod_update:
	docker-compose -f docker-compose.prod.yml down --remove-orphans --volumes
	docker-compose down --remove-orphans --volumes
	sudo chmod -R 777 data
	docker-compose -f docker-compose.prod.yml up -d --build
run:
	docker-compose down --remove-orphans --volumes
	sudo chmod -R 777 data
	docker-compose up -d
down:
	docker-compose down --remove-orphans --volumes
logs:
	docker-compose logs -f
update:
	docker-compose down
	sudo chmod -R 777 data
	docker-compose up -d --build