from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "tariff" ADD "name" VARCHAR(50) NOT NULL DEFAULT 'Стандартный';
        ALTER TABLE "tariff" DROP COLUMN "rate_type";"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "tariff" ADD "rate_type" VARCHAR(50) NOT NULL DEFAULT '';
        ALTER TABLE "tariff" DROP COLUMN "name";"""
