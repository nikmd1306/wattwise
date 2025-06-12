from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "tenant" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "name" VARCHAR(255) NOT NULL UNIQUE
);
COMMENT ON TABLE "tenant" IS 'Represents a tenant who rents a property.';
CREATE TABLE IF NOT EXISTS "invoice" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "amount" DECIMAL(10,2) NOT NULL,
    "period" DATE NOT NULL,
    "tenant_id" UUID NOT NULL REFERENCES "tenant" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_invoice_tenant__8db641" UNIQUE ("tenant_id", "period")
);
COMMENT ON TABLE "invoice" IS 'Represents a bill for a tenant for a specific period.';
CREATE TABLE IF NOT EXISTS "adjustment" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "amount" DECIMAL(10,2) NOT NULL,
    "description" VARCHAR(255) NOT NULL,
    "invoice_id" UUID NOT NULL REFERENCES "invoice" ("id") ON DELETE CASCADE
);
COMMENT ON TABLE "adjustment" IS 'Represents a manual adjustment on an invoice.';
CREATE TABLE IF NOT EXISTS "meter" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "name" VARCHAR(255) NOT NULL,
    "resource_type" VARCHAR(11) NOT NULL DEFAULT 'electricity',
    "tenant_id" UUID NOT NULL REFERENCES "tenant" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "meter"."resource_type" IS 'ELECTRICITY: electricity\nWATER: water\nHEAT: heat';
COMMENT ON TABLE "meter" IS 'Represents a utility meter.';
CREATE TABLE IF NOT EXISTS "deductionlink" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "description" VARCHAR(255) NOT NULL,
    "child_meter_id" UUID NOT NULL REFERENCES "meter" ("id") ON DELETE CASCADE,
    "parent_meter_id" UUID NOT NULL REFERENCES "meter" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_deductionli_parent__293dda" UNIQUE ("parent_meter_id", "child_meter_id")
);
COMMENT ON COLUMN "deductionlink"."child_meter_id" IS 'The meter whose consumption is used as a basis for deduction';
COMMENT ON COLUMN "deductionlink"."parent_meter_id" IS 'The meter from which the value will be deducted';
COMMENT ON TABLE "deductionlink" IS 'Describes a link between two meters for subsequent manual deduction';
CREATE TABLE IF NOT EXISTS "reading" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "value" DECIMAL(10,2) NOT NULL,
    "period" DATE NOT NULL,
    "manual_adjustment" DECIMAL(10,2) DEFAULT 0,
    "meter_id" UUID NOT NULL REFERENCES "meter" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_reading_meter_i_2bb1cf" UNIQUE ("meter_id", "period")
);
COMMENT ON COLUMN "reading"."manual_adjustment" IS 'Manual adjustment in kWh entered by user';
COMMENT ON TABLE "reading" IS 'Represents a meter reading for a specific period.';
CREATE TABLE IF NOT EXISTS "tariff" (
    "id" UUID NOT NULL PRIMARY KEY,
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "rate" DECIMAL(10,4) NOT NULL,
    "rate_type" VARCHAR(50) NOT NULL DEFAULT '',
    "period_start" DATE NOT NULL,
    "period_end" DATE,
    "meter_id" UUID NOT NULL REFERENCES "meter" ("id") ON DELETE CASCADE
);
COMMENT ON TABLE "tariff" IS 'Represents a tariff with a specific rate for a period.';
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSONB NOT NULL
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """
