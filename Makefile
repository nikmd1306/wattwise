PY?=python

.PHONY: install test lint format dev

install:
	poetry install

aerich:
	poetry run aerich upgrade

lint:
	poetry run ruff check .
	poetry run mypy . --strict

test:
	poetry run pytest -q --cov=app

format:
	poetry run ruff format .

dev:
	PYTHONPATH=src poetry run python -m app.bots.tg.bot