run:
	docker-compose up -d
logs:
	docker-compose logs -f
update:
	docker-compose down
	sudo chmod -R 777 data
	docker-compose up -d --build