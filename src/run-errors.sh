#!/usr/bin/bash

BASE_DIR="$(dirname "$(realpath "$0")")"

export PYTHONPATH="$BASE_DIR"
python3 "$BASE_DIR"/errors/manage.py runserver
