// Seeds the Item table from ../data/items.json (produced by tools/convert_items.py).
// Usage: bun prisma/seed.ts [--reset]
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { prisma } from "../src/db";
import type { Prisma } from "../generated/prisma/client";

const ROOT = resolve(import.meta.dir, "../..");
const ITEMS_JSON = resolve(ROOT, "data/items.json");
const ASSETS = resolve(ROOT, "public/assets");
const CHUNK = 500;

type RawItem = {
  id: number;
  name: string;
  unidentifiedName: string | null;
  resourceName: string;
  unidentifiedResourceName: string | null;
  slotCount: number;
  viewId: number;
  isCostume: boolean;
  effectId: number | null;
  itemType: Prisma.ItemCreateManyInput["itemType"];
  subType: string;
  typeLabel: string | null;
  equipLocations: string[];
  cardLocation: string | null;
  atk: number | null;
  matk: number | null;
  def: number | null;
  weight: number | null;
  weaponLevel: number | null;
  requiredLevel: number | null;
  element: string | null;
  jobs: string | null;
  description: string;
  descriptionRaw: string[];
  bonuses: Record<string, number>;
};

async function main() {
  const reset = process.argv.includes("--reset");
  const items: RawItem[] = await Bun.file(ITEMS_JSON).json();
  console.log(`loaded ${items.length} items from ${ITEMS_JSON}`);

  if (reset) {
    await prisma.equipmentSlot.deleteMany();
    await prisma.item.deleteMany();
    console.log("cleared Item / EquipmentSlot");
  }

  const rows: Prisma.ItemCreateManyInput[] = items.map((it) => ({
    id: it.id,
    name: it.name,
    unidentifiedName: it.unidentifiedName,
    resourceName: it.resourceName,
    unidentifiedResourceName: it.unidentifiedResourceName,
    slotCount: it.slotCount,
    viewId: it.viewId,
    isCostume: it.isCostume,
    effectId: it.effectId,
    itemType: it.itemType,
    subType: it.subType,
    typeLabel: it.typeLabel,
    equipLocations: it.equipLocations,
    cardLocation: it.cardLocation,
    atk: it.atk,
    matk: it.matk,
    def: it.def,
    weight: it.weight,
    weaponLevel: it.weaponLevel,
    requiredLevel: it.requiredLevel,
    element: it.element,
    jobs: it.jobs,
    description: it.description,
    descriptionLines: it.descriptionRaw,
    bonuses: it.bonuses,
    hasIcon: existsSync(resolve(ASSETS, "items", `${it.id}.png`)),
    hasCollection: existsSync(resolve(ASSETS, "collection", `${it.id}.png`)),
  }));

  let inserted = 0;
  for (let i = 0; i < rows.length; i += CHUNK) {
    const res = await prisma.item.createMany({ data: rows.slice(i, i + CHUNK), skipDuplicates: true });
    inserted += res.count;
  }
  const total = await prisma.item.count();
  console.log(`inserted ${inserted} new rows; Item table now has ${total} rows`);
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(() => prisma.$disconnect());
