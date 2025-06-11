PY?=python

.PHONY: install test lint format dev

install:
	poetry install --no-root

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
	poetry run uvicorn app.bots.tg.bot:main --reload 