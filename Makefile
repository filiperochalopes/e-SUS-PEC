update:
	docker-compose down
	sudo chmod -R 777 data
	docker-compose up -d --build