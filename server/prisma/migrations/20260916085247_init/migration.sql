-- CreateEnum
CREATE TYPE "ItemType" AS ENUM ('WEAPON', 'ARMOR', 'CARD', 'AMMO', 'CONSUMABLE', 'COSTUME', 'SHADOW', 'PET_EGG', 'ETC');

-- CreateTable
CREATE TABLE "Item" (
    "id" INTEGER NOT NULL,
    "name" TEXT NOT NULL,
    "unidentifiedName" TEXT,
    "resourceName" TEXT NOT NULL,
    "unidentifiedResourceName" TEXT,
    "slotCount" INTEGER NOT NULL DEFAULT 0,
    "viewId" INTEGER NOT NULL DEFAULT 0,
    "isCostume" BOOLEAN NOT NULL DEFAULT false,
    "effectId" INTEGER,
    "itemType" "ItemType" NOT NULL,
    "subType" TEXT NOT NULL,
    "typeLabel" TEXT,
    "equipLocations" TEXT[],
    "cardLocation" TEXT,
    "atk" INTEGER,
    "matk" INTEGER,
    "def" INTEGER,
    "weight" INTEGER,
    "weaponLevel" INTEGER,
    "requiredLevel" INTEGER,
    "element" TEXT,
    "jobs" TEXT,
    "description" TEXT NOT NULL,
    "descriptionLines" JSONB NOT NULL,
    "bonuses" JSONB NOT NULL,
    "hasIcon" BOOLEAN NOT NULL DEFAULT false,
    "hasCollection" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Item_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "CharacterBuild" (
    "id" TEXT NOT NULL,
    "shareCode" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "jobClass" TEXT NOT NULL,
    "baseLevel" INTEGER NOT NULL DEFAULT 99,
    "jobLevel" INTEGER NOT NULL DEFAULT 50,
    "str" INTEGER NOT NULL DEFAULT 1,
    "agi" INTEGER NOT NULL DEFAULT 1,
    "vit" INTEGER NOT NULL DEFAULT 1,
    "int" INTEGER NOT NULL DEFAULT 1,
    "dex" INTEGER NOT NULL DEFAULT 1,
    "luk" INTEGER NOT NULL DEFAULT 1,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "CharacterBuild_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "EquipmentSlot" (
    "id" TEXT NOT NULL,
    "buildId" TEXT NOT NULL,
    "location" TEXT NOT NULL,
    "refineLevel" INTEGER NOT NULL DEFAULT 0,
    "itemId" INTEGER,
    "card1Id" INTEGER,
    "card2Id" INTEGER,
    "card3Id" INTEGER,
    "card4Id" INTEGER,

    CONSTRAINT "EquipmentSlot_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "Item_itemType_idx" ON "Item"("itemType");

-- CreateIndex
CREATE INDEX "Item_subType_idx" ON "Item"("subType");

-- CreateIndex
CREATE INDEX "Item_name_idx" ON "Item"("name");

-- CreateIndex
CREATE UNIQUE INDEX "CharacterBuild_shareCode_key" ON "CharacterBuild"("shareCode");

-- CreateIndex
CREATE UNIQUE INDEX "EquipmentSlot_buildId_location_key" ON "EquipmentSlot"("buildId", "location");

-- AddForeignKey
ALTER TABLE "EquipmentSlot" ADD CONSTRAINT "EquipmentSlot_buildId_fkey" FOREIGN KEY ("buildId") REFERENCES "CharacterBuild"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "EquipmentSlot" ADD CONSTRAINT "EquipmentSlot_itemId_fkey" FOREIGN KEY ("itemId") REFERENCES "Item"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "EquipmentSlot" ADD CONSTRAINT "EquipmentSlot_card1Id_fkey" FOREIGN KEY ("card1Id") REFERENCES "Item"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "EquipmentSlot" ADD CONSTRAINT "EquipmentSlot_card2Id_fkey" FOREIGN KEY ("card2Id") REFERENCES "Item"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "EquipmentSlot" ADD CONSTRAINT "EquipmentSlot_card3Id_fkey" FOREIGN KEY ("card3Id") REFERENCES "Item"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "EquipmentSlot" ADD CONSTRAINT "EquipmentSlot_card4Id_fkey" FOREIGN KEY ("card4Id") REFERENCES "Item"("id") ON DELETE SET NULL ON UPDATE CASCADE;
