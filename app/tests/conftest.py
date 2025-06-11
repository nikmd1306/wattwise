"""Pytest configuration and fixtures."""

import pytest_asyncio
from tortoise import Tortoise


@pytest_asyncio.fixture(scope="function", autouse=True)
async def db_session():
    """
    Provides a clean in-memory SQLite database for each test function.
    """
    await Tortoise.init(
        db_url="sqlite://:memory:",
        modules={"models": ["app.core.models"]},
    )
    await Tortoise.generate_schemas()

    yield

    await Tortoise.close_connections()
