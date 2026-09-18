// `bun run setup:check` — tells you what this machine is missing before you
// start the API. Exit code 1 if anything blocking is wrong.
import { existsSync, readdirSync, statSync } from "node:fs";
import { resolve } from "node:path";

const ROOT = resolve(import.meta.dir, "../..");
const GRF_PATH = process.env.GRF_PATH ?? resolve(ROOT, "client/RagnarokClassic/data.grf");
const INDEX_PATH = resolve(ROOT, "data/grf_index.json");
let failures = 0;

const ok = (msg: string) => console.log(`  ✔ ${msg}`);
const warn = (msg: string) => console.log(`  ⚠ ${msg}`);
const fail = (msg: string) => { failures++; console.log(`  ✘ ${msg}`); };

console.log("server/.env");
if (existsSync(resolve(ROOT, "server/.env"))) ok(".env present");
else fail(".env missing → cp server/.env.example server/.env");

console.log("database");
if (!process.env.DATABASE_URL) fail("DATABASE_URL not set");
else {
  try {
    const { prisma } = await import("../src/db");
    const items = await prisma.item.count();
    const builds = await prisma.characterBuild.count();
    if (items > 0) ok(`connected — ${items} items, ${builds} saved builds`);
    else fail("connected but 0 items → bun run db:seed");
    await prisma.$disconnect();
  } catch (e) {
    const err = e as Error & { code?: string };
    const reason = err.code ?? err.message.trim().split("\n").filter((l) => !l.startsWith("Invalid `")).pop() ?? String(e);
    fail(`cannot connect (${reason}) → docker compose up -d && bunx prisma migrate dev`);
  }
}

console.log("item icons (public/assets)");
const iconDir = resolve(ROOT, "public/assets/items");
const n = existsSync(iconDir) ? readdirSync(iconDir).filter((f) => f.endsWith(".png")).length : 0;
if (n > 10000) ok(`${n} icons`);
else fail(`${n} icons in ${iconDir} → git pull (icons are committed) or python3 tools/extract_assets.py`);

console.log("character sprites (data.grf)");
if (!existsSync(GRF_PATH)) {
  warn(`data.grf not found at ${GRF_PATH}`);
  warn("→ set GRF_PATH in server/.env to your installed client's data.grf (e.g. C:/Gravity/RagnarokClassic/data.grf)");
} else {
  const size = statSync(GRF_PATH).size;
  ok(`data.grf: ${GRF_PATH} (${(size / 1e9).toFixed(2)} GB)`);
  if (!existsSync(INDEX_PATH)) warn(`data/grf_index.json missing → python3 tools/build_grf_index.py`);
  else {
    const meta = ((await Bun.file(INDEX_PATH).json()) as { __meta__?: { size: number } }).__meta__;
    if (!meta) warn("data/grf_index.json is from an older tool version → re-run python3 tools/build_grf_index.py");
    else if (meta.size !== size) warn(`data/grf_index.json was built for a different data.grf → re-run python3 tools/build_grf_index.py`);
    else ok("data/grf_index.json matches data.grf");
  }
}

console.log(failures ? `\n${failures} problem(s) — the API will start but parts of the app will not work.` : "\nAll good.");
process.exit(failures ? 1 : 0);
