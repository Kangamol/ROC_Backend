-- AlterTable
ALTER TABLE "Item" ADD COLUMN     "unparsedLines" JSONB NOT NULL DEFAULT '[]';
