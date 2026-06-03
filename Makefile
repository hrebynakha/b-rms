run:
	python manage.py runserver
migrate:
	python manage.py migrate
migrations:
	python manage.py makemigrations

esp:
	python scripts/fake_esp32_on.py
sensor:
	python scripts/fake_sensor.py
web:
	docker run --rm \
		-p 80:80 \
		-v d:/repos/b-rms/config/nginx.conf:/etc/nginx/nginx.conf:ro \
		--add-host=host.docker.internal:host-gateway \
		nginx

up:
	python manage.py runserver
	docker run --rm \
		-p 80:80 \
		-v d:/repos/b-rms/config/nginx.conf:/etc/nginx/nginx.conf:ro \
		--add-host=host.docker.internal:host-gateway \
		nginx