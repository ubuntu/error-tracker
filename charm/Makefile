BASE_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

.PHONY: tests pack

pack:
	charmcraft pack --project-dir $(BASE_DIR)..

tests:
	uv run --all-extras pytest -o log_cli=1 -v --log-level=INFO --pdb --charm-path ../error-tracker_ubuntu@24.04-amd64.charm tests/
