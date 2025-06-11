from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "tenant" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "name" VARCHAR(255) NOT NULL UNIQUE
) /* Represents a tenant who rents a property. */;
CREATE TABLE IF NOT EXISTS "invoice" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "amount" VARCHAR(40) NOT NULL,
    "period" DATE NOT NULL,
    "tenant_id" CHAR(36) NOT NULL REFERENCES "tenant" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_invoice_tenant__8db641" UNIQUE ("tenant_id", "period")
) /* Represents a bill for a tenant for a specific period. */;
CREATE TABLE IF NOT EXISTS "adjustment" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "amount" VARCHAR(40) NOT NULL,
    "description" VARCHAR(255) NOT NULL,
    "invoice_id" CHAR(36) NOT NULL REFERENCES "invoice" ("id") ON DELETE CASCADE
) /* Represents a manual adjustment on an invoice. */;
CREATE TABLE IF NOT EXISTS "meter" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "name" VARCHAR(255) NOT NULL,
    "resource_type" VARCHAR(11) NOT NULL DEFAULT 'electricity' /* ELECTRICITY: electricity\nWATER: water\nHEAT: heat */,
    "tenant_id" CHAR(36) NOT NULL REFERENCES "tenant" ("id") ON DELETE CASCADE
) /* Represents a utility meter. */;
CREATE TABLE IF NOT EXISTS "reading" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "value" VARCHAR(40) NOT NULL,
    "period" DATE NOT NULL,
    "meter_id" CHAR(36) NOT NULL REFERENCES "meter" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_reading_meter_i_2bb1cf" UNIQUE ("meter_id", "period")
) /* Represents a meter reading for a specific period. */;
CREATE TABLE IF NOT EXISTS "tariff" (
    "id" CHAR(36) NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "rate" VARCHAR(40) NOT NULL,
    "period_start" DATE NOT NULL,
    "period_end" DATE,
    "meter_id" CHAR(36) NOT NULL REFERENCES "meter" ("id") ON DELETE CASCADE
) /* Represents a tariff with a specific rate for a period. */;
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSON NOT NULL
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """
