FROM python:3.12-slim

ENV POETRY_VERSION=1.8.2 \
    POETRY_HOME=/opt/poetry \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false

RUN pip install --no-cache-dir "poetry==${POETRY_VERSION}"

WORKDIR /app
COPY pyproject.toml poetry.lock README.md ./
RUN poetry install --no-root --only main

COPY . .

HEALTHCHECK CMD python -m app.bots.tg.bot --help || exit 1

CMD ["python", "-m", "app.bots.tg.bot"] 