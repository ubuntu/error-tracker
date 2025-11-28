#!/usr/bin/bash

BASE_DIR="$(dirname "$(realpath "$0")")"

export PYTHONPATH="$BASE_DIR"
python3 "$BASE_DIR"/retracer.py -a amd64 --sandbox-dir /tmp/sandbox -v --config-dir "$BASE_DIR"/retracer/config
