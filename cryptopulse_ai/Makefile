SHELL := /bin/bash

.PHONY: install test lint format run run-once samples docker-build docker-up docker-down logs smoke

install:
	python -m pip install -U pip
	python -m pip install -e '.[dev]'

test:
	pytest -q

lint:
	ruff check src tests
	mypy src/cryptopulse

format:
	ruff format src tests
	ruff check --fix src tests

run:
	cryptopulse serve

run-once:
	cryptopulse run-once

samples:
	cryptopulse generate-samples --output sample_output

docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

logs:
	docker compose logs -f app

smoke:
	bash scripts/smoke_test.sh
