from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "tariff" ADD "rate_type" VARCHAR(7) NOT NULL DEFAULT 'default' /* DEFAULT: default\nDAY: day\nNIGHT: night\nPEAK: peak */;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "tariff" DROP COLUMN "rate_type";"""
