BASE_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

export PYTHONPATH := $(BASE_DIR)

.PHONY: run-daisy run-errors run-retracer populate-test-data

run-daisy:
	python3 $(BASE_DIR)daisy/app.py

run-errors:
	python3 $(BASE_DIR)errors/manage.py runserver

run-retracer:
	python3 $(BASE_DIR)retracer.py -a amd64 --sandbox-dir /tmp/sandbox -v --config-dir $(BASE_DIR)retracer/config

populate-test-data:
	python3 $(BASE_DIR)tests/create_test_data.py
