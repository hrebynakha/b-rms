run:
	python manage.py runserver
migrate:
	python manage.py migrate
migrations:
	python manage.py makemigrations

firmware:
	pio run -e b-rms

firmware-fs:
	pio run -e b-rms -t uploadfs

firmware-upload:
	pio run -e b-rms -t upload

esp:
	python scripts/fake_esp32_on.py
sensor:
	python scripts/fake_sensor.py --profile $(or $(PROFILE),scripts/sensor_profile.json) $(if $(START_STAGE),--start-stage $(START_STAGE),) $(if $(SKIP_STAGES),--skip-stages $(SKIP_STAGES),)
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
