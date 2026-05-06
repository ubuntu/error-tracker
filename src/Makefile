BASE_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

export PYTHONPATH := $(BASE_DIR)

.PHONY: daisy-run errors-run errors-shell retracer-run populate-test-data

daisy-run:
	python3 $(BASE_DIR)daisy/app.py

errors-run:
	python3 $(BASE_DIR)errors/manage.py migrate
	python3 $(BASE_DIR)errors/manage.py runserver

errors-uwsgi:
	python3 $(BASE_DIR)errors/manage.py migrate
	uwsgi --plugins python3 --http-socket 0.0.0.0:9000 --wsgi-file $(BASE_DIR)errors/wsgi.py --static-map "/static=$(BASE_DIR)../static/" --chdir $(BASE_DIR) --die-on-term --master --env PYTHONPATH=$(BASE_DIR)

errors-shell:
	python3 $(BASE_DIR)errors/manage.py shell

retracer-run:
	python3 $(BASE_DIR)retracer.py -a amd64 --sandbox-dir /tmp/sandbox -v --config-dir $(BASE_DIR)retracer/config

populate-test-data:
	python3 $(BASE_DIR)tests/create_test_data.py
