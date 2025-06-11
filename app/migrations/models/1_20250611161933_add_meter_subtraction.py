from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "meter" ADD "subtract_from_id" CHAR(36);
        ALTER TABLE "meter" ADD CONSTRAINT "fk_meter_meter_317ece22" FOREIGN KEY ("subtract_from_id") REFERENCES "meter" ("id") ON DELETE SET NULL;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "meter" DROP FOREIGN KEY "fk_meter_meter_317ece22";
        ALTER TABLE "meter" DROP COLUMN "subtract_from_id";"""
