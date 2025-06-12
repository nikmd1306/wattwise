# WattWise

[![CI](https://github.com/nikmd1306/wattwise/actions/workflows/ci.yml/badge.svg)](https://github.com/nikmd1306/wattwise/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Утилита **WattWise** автоматизирует учёт показаний счётчиков, расчёт тарифов и генерацию счётов для арендных площадей.

## Возможности

* Асинхронное ядро на Tortoise-ORM + Pydantic v2
* Алгоритмы расчёта расхода/стоимости c поддержкой подсчётчиков
* PDF экспорт счетов
* Telegram-бот на aiogram v3 для ввода данных и получения счётов
* Плагины: планировщик ночных расчётов, REST API (в разработке)

## Быстрый старт

```bash
# Установка зависимостей
poetry install

# Инициализация БД
poetry run aerich upgrade

# Запуск Telegram-бота
BOT_TOKEN=... DB_DSN=sqlite://db.sqlite3 \
poetry run python -m app.bots.tg.bot
```

## Развёртывание в Docker

```bash
# Скопируйте .env.example → .env и заполните BOT_TOKEN / DB_*
cp .env.example .env

# Сборка и запуск контейнера
docker compose up -d --build

# Просмотр логов
docker compose logs -f --tail=100
```

Контейнер собирается на основе `python:3.12-slim`, локаль `ru_RU.UTF-8` и все системные зависимости устанавливаются автоматически.

## Разработка

```bash
make lint            # mypy + ruff
make test            # pytest
make dev             # watcher с hot-reload
```

## Лицензия

Этот проект распространяется под лицензией MIT. См. файл [LICENSE](LICENSE). 