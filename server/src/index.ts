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
      randomOptions: t.Optional(t.Array(t.Object({ key: t.String({ maxLength: 60 }), value: t.Number() }), { maxItems: 4 })),
    }),
  ),
});

// Per-job tables (base HP/SP, ASPD, job-level stat bonuses) built by tools/build_job_data.py
const JOBS_PATH = resolve(import.meta.dir, "../../data/jobs.json");
const jobs: Record<string, any> = (await Bun.file(JOBS_PATH).exists()) ? await Bun.file(JOBS_PATH).json() : {};

// ---- Awakened classes (Gnjoy, 2026): derived from the base class tables + data/awakened.json ----------------
const AWAKENED_PATH = resolve(import.meta.dir, "../../data/awakened.json");
const awakened: any = (await Bun.file(AWAKENED_PATH).exists()) ? await Bun.file(AWAKENED_PATH).json() : null;
/** Continue a per-level table past its last entry with a quadratic fitted to the last 20 points (pre-re HP grows quadratically, SP linearly). */
function extrapolate(arr: number[], to: number): number[] {
  const n = arr.length;
  if (n >= to) return arr;
  const k = Math.min(20, n);
  const xs = Array.from({ length: k }, (_, i) => n - k + i + 1);
  const ys = arr.slice(n - k);
  // least squares y = a + b x + c x^2
  const S = (f: (x: number, y: number) => number) => xs.reduce((acc, x, i) => acc + f(x, ys[i]!), 0);
  const m = [[k, S((x) => x), S((x) => x * x)], [S((x) => x), S((x) => x * x), S((x) => x ** 3)], [S((x) => x * x), S((x) => x ** 3), S((x) => x ** 4)]];
  const v = [S((_, y) => y), S((x, y) => x * y), S((x, y) => x * x * y)];
  // gaussian elimination
  for (let i = 0; i < 3; i++) {
    const piv = m[i]![i]!;
    for (let j = i; j < 3; j++) m[i]![j]! /= piv;
    v[i]! /= piv;
    for (let r = 0; r < 3; r++) if (r !== i) { const f = m[r]![i]!; for (let j = i; j < 3; j++) m[r]![j]! -= f * m[i]![j]!; v[r]! -= f * v[i]!; }
  }
  const [a, b, c] = v as [number, number, number];
  const out = [...arr];
  for (let x = n + 1; x <= to; x++) out.push(Math.round(a + b * x + c * x * x));
  return out;
}
if (awakened) {
  const caps = awakened.caps;
  for (const [name, def] of Object.entries<any>(awakened.classes)) {
    const base = jobs[def.base];
    if (!base) continue;
    const aspd: Record<string, number> = { ...base.aspd };
    if (def.aspd) {
      // page gives bare-hand base ASPD + per-weapon penalty; the engine wants attack delay = (200 - ASPD) * 10
      aspd.NONE = (200 - def.aspd.base) * 10;
      for (const [w, pen] of Object.entries<number>(def.aspd.penalty)) {
        if (w === "SHIELD") aspd.SHIELD = -pen * 10; // added to the delay when a shield is worn
        else aspd[w] = (200 - (def.aspd.base + pen)) * 10;
      }
    }
    jobs[name] = {
      ...base,
      key: name,
      baseClass: def.base,
      awakened: true,
      hp: extrapolate(base.hp, caps.baseLevel),
      sp: extrapolate(base.sp, caps.baseLevel),
      hpApproxFrom: base.hp.length + 1,
      aspd,
      aspdApprox: !def.aspd,
      caps,
    };
  }
}
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
  // Awakened-class rules: level / stat / ASPD caps and the cumulative stat-point tables
  .get("/api/awakened", () => awakened ?? { caps: null, statPoints: null, classes: {} })
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
              randomOptions: s.randomOptions ?? [],
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
