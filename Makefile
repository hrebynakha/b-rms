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