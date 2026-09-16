-- AlterTable
ALTER TABLE "Item" ADD COLUMN     "conditionalBonuses" JSONB NOT NULL DEFAULT '{}';
