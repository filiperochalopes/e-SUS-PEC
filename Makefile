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