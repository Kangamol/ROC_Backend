import { Elysia, t } from "elysia";
import { cors } from "@elysiajs/cors";
import { staticPlugin } from "@elysiajs/static";
import { resolve } from "node:path";
import { prisma } from "./db";
import { spriteRoutes } from "./sprites";
import type { Prisma } from "../generated/prisma/client";

const PORT = Number(process.env.PORT ?? 3000);
const ASSETS_DIR = resolve(import.meta.dir, "../../public/assets");

const ITEM_TYPES = ["WEAPON", "ARMOR", "CARD", "AMMO", "CONSUMABLE", "COSTUME", "SHADOW", "PET_EGG", "ETC"] as const;

/** Fields returned in list endpoints — keeps search responses small. */
const listSelect = {
  id: true,
  name: true,
  slotCount: true,
  itemType: true,
  subType: true,
  equipLocations: true,
  cardLocation: true,
  atk: true,
  matk: true,
  def: true,
  weight: true,
  weaponLevel: true,
  requiredLevel: true,
  element: true,
  bonuses: true,
  conditionalBonuses: true,
  unparsedLines: true,
  hasIcon: true,
  viewId: true,
} satisfies Prisma.ItemSelect;

const buildBody = t.Object({
  title: t.String({ minLength: 1, maxLength: 80 }),
  jobClass: t.String(),
  baseLevel: t.Integer({ minimum: 1, maximum: 999 }),
  jobLevel: t.Integer({ minimum: 1, maximum: 999 }),
  gender: t.Optional(t.Union([t.Literal("M"), t.Literal("F")])),
  hairStyle: t.Optional(t.Integer({ minimum: 0, maximum: 999 })),
  hairColor: t.Optional(t.Integer({ minimum: 0, maximum: 999 })),
  clothColor: t.Optional(t.Integer({ minimum: 0, maximum: 999 })),
  stats: t.Object({
    str: t.Integer({ minimum: 1 }),
    agi: t.Integer({ minimum: 1 }),
    vit: t.Integer({ minimum: 1 }),
    int: t.Integer({ minimum: 1 }),
    dex: t.Integer({ minimum: 1 }),
    luk: t.Integer({ minimum: 1 }),
  }),
  slots: t.Array(
    t.Object({
      location: t.String(),
      refineLevel: t.Integer({ minimum: 0, maximum: 15, default: 0 }),
      itemId: t.Optional(t.Nullable(t.Integer())),
      card1Id: t.Optional(t.Nullable(t.Integer())),
      card2Id: t.Optional(t.Nullable(t.Integer())),
      card3Id: t.Optional(t.Nullable(t.Integer())),
      card4Id: t.Optional(t.Nullable(t.Integer())),
    }),
  ),
});

// Per-job tables (base HP/SP, ASPD, job-level stat bonuses) built by tools/build_job_data.py
const JOBS_PATH = resolve(import.meta.dir, "../../data/jobs.json");
const jobs: Record<string, unknown> = (await Bun.file(JOBS_PATH).exists()) ? await Bun.file(JOBS_PATH).json() : {};
const ENCHANT_PATH = resolve(import.meta.dir, "../../data/enchant_pools.json");
/** Read on every request (a few KB) so edits to the hand-maintained table show up without restarting the API. */
const enchantPools = async () => ((await Bun.file(ENCHANT_PATH).exists()) ? Bun.file(ENCHANT_PATH).json() : { default: null, items: {} });
if (!Object.keys(jobs).length) console.warn(`jobs: ${JOBS_PATH} missing — run tools/build_job_data.py (engine falls back to approximations)`);

const app = new Elysia()
  .use(cors())
  .use(staticPlugin({ assets: ASSETS_DIR, prefix: "/assets" }))
  .use(spriteRoutes)
  .get("/api/health", () => ({ ok: true }))
  .get("/api/jobs", () => jobs)
  // NPC enchant rules per item (hand-maintained data/enchant_pools.json; the client has no enchant data)
  .get("/api/enchant-pools", () => enchantPools())

  // ---- meta ---------------------------------------------------------------
  .get("/api/meta", async () => {
    const [byType, locations] = await Promise.all([
      prisma.item.groupBy({ by: ["itemType"], _count: { _all: true } }),
      prisma.$queryRaw<{ location: string; count: bigint }[]>`
        SELECT loc AS location, COUNT(*)::bigint AS count
        FROM "Item", unnest("equipLocations") AS loc
        GROUP BY loc ORDER BY loc`,
    ]);
    return {
      itemTypes: byType.map((r) => ({ type: r.itemType, count: r._count._all })),
      equipLocations: locations.map((r) => ({ location: r.location, count: Number(r.count) })),
    };
  })

  // ---- items --------------------------------------------------------------
  .get(
    "/api/items",
    async ({ query }) => {
      const where: Prisma.ItemWhereInput = {};
      if (query.search) {
        const asId = Number(query.search);
        where.OR = [
          { name: { contains: query.search, mode: "insensitive" } },
          ...(Number.isInteger(asId) ? [{ id: asId }] : []),
        ];
      }
      if (query.type) where.itemType = query.type;
      if (query.subType) where.subType = query.subType;
      if (query.location) where.equipLocations = { has: query.location };
      if (query.cardLocation) where.cardLocation = query.cardLocation;
      if (query.slots !== undefined) where.slotCount = { gte: query.slots };

      const [total, items] = await Promise.all([
        prisma.item.count({ where }),
        prisma.item.findMany({
          where,
          select: listSelect,
          orderBy: { id: "asc" },
          take: query.limit,
          skip: query.offset,
        }),
      ]);
      return { total, items };
    },
    {
      query: t.Object({
        search: t.Optional(t.String()),
        type: t.Optional(t.Union(ITEM_TYPES.map((v) => t.Literal(v)))),
        subType: t.Optional(t.String()),
        location: t.Optional(t.String()),
        cardLocation: t.Optional(t.String()),
        slots: t.Optional(t.Integer({ minimum: 0, maximum: 4 })),
        limit: t.Integer({ minimum: 1, maximum: 500, default: 50 }),
        offset: t.Integer({ minimum: 0, default: 0 }),
      }),
    },
  )

  .get(
    "/api/items/:id",
    async ({ params, status }) => {
      const item = await prisma.item.findUnique({ where: { id: params.id } });
      return item ?? status(404, { error: "Item not found" });
    },
    { params: t.Object({ id: t.Integer() }) },
  )

  // ---- builds -------------------------------------------------------------
  .post(
    "/api/builds",
    async ({ body }) => {
      const shareCode = crypto.randomUUID().replace(/-/g, "").slice(0, 8);
      const build = await prisma.characterBuild.create({
        data: {
          shareCode,
          title: body.title,
          jobClass: body.jobClass,
          baseLevel: body.baseLevel,
          jobLevel: body.jobLevel,
          gender: body.gender ?? "M",
          hairStyle: body.hairStyle ?? 1,
          hairColor: body.hairColor ?? 0,
          clothColor: body.clothColor ?? 0,
          ...body.stats,
          slots: {
            create: body.slots.map((s) => ({
              location: s.location,
              refineLevel: s.refineLevel,
              itemId: s.itemId ?? null,
              card1Id: s.card1Id ?? null,
              card2Id: s.card2Id ?? null,
              card3Id: s.card3Id ?? null,
              card4Id: s.card4Id ?? null,
            })),
          },
        },
      });
      return { shareCode: build.shareCode };
    },
    { body: buildBody },
  )

  .get(
    "/api/builds/:shareCode",
    async ({ params, status }) => {
      const build = await prisma.characterBuild.findUnique({
        where: { shareCode: params.shareCode },
        include: {
          slots: {
            include: {
              item: { select: listSelect },
              card1: { select: listSelect },
              card2: { select: listSelect },
              card3: { select: listSelect },
              card4: { select: listSelect },
            },
          },
        },
      });
      return build ?? status(404, { error: "Build not found" });
    },
    { params: t.Object({ shareCode: t.String() }) },
  )

  .listen(PORT);

console.log(`RO Simulator API running at http://localhost:${app.server?.port}`);

export type App = typeof app;
