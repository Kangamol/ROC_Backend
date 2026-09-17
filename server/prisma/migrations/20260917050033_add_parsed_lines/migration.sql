-- AlterTable
ALTER TABLE "Item" ADD COLUMN     "conditionalLines" JSONB NOT NULL DEFAULT '[]',
ADD COLUMN     "parsedLines" JSONB NOT NULL DEFAULT '[]';
