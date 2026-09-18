// /sprites/* routes: serve player sprites, headgear, robes and palettes straight
// from data.grf so nothing has to be pre-extracted. File names inside the GRF
// are Korean; the API exposes ASCII ids (job keys, hair ids, item viewIds).
import { Elysia, t } from "elysia";
import { existsSync, statSync } from "node:fs";
import { resolve } from "node:path";
import { GrfReader, type GrfIndex } from "./grf";

const ROOT = resolve(import.meta.dir, "../..");
const GRF_PATH = process.env.GRF_PATH ?? resolve(ROOT, "client/RagnarokClassic/data.grf");
const INDEX_PATH = resolve(ROOT, "data/grf_index.json");
const ACC_PATH = resolve(ROOT, "data/lua/acc.json");
const ROBE_PATH = resolve(ROOT, "data/lua/robe.json");

const GENDER: Record<string, string> = { m: "남", f: "여" };

/** key, display name, Korean sprite name — order is the UI order. */
export const JOBS: [string, string, string][] = [
  ["novice", "Novice", "초보자"], ["swordman", "Swordman", "검사"], ["magician", "Magician", "마법사"],
  ["archer", "Archer", "궁수"], ["acolyte", "Acolyte", "성직자"], ["merchant", "Merchant", "상인"], ["thief", "Thief", "도둑"],
  ["knight", "Knight", "기사"], ["priest", "Priest", "프리스트"], ["wizard", "Wizard", "위저드"], ["blacksmith", "Blacksmith", "제철공"],
  ["hunter", "Hunter", "헌터"], ["assassin", "Assassin", "어세신"],
  ["crusader", "Crusader", "크루세이더"], ["monk", "Monk", "몽크"], ["sage", "Sage", "세이지"], ["rogue", "Rogue", "로그"],
  ["alchemist", "Alchemist", "연금술사"], ["bard", "Bard", "바드"], ["dancer", "Dancer", "무희"],
  ["lord_knight", "Lord Knight", "로드나이트"], ["high_priest", "High Priest", "하이프리"], ["high_wizard", "High Wizard", "하이위저드"],
  ["whitesmith", "Whitesmith", "화이트스미스"], ["sniper", "Sniper", "스나이퍼"], ["assassin_cross", "Assassin Cross", "어쌔신크로스"],
  ["paladin", "Paladin", "팔라딘"], ["champion", "Champion", "챔피온"], ["professor", "Professor", "프로페서"],
  ["stalker", "Stalker", "스토커"], ["creator", "Creator", "크리에이터"], ["clown", "Clown", "클라운"], ["gypsy", "Gypsy", "집시"],
  ["super_novice", "Super Novice", "슈퍼노비스"], ["taekwon", "Taekwon", "태권소년"], ["star_gladiator", "Star Gladiator", "권성"],
  ["soul_linker", "Soul Linker", "소울링커"], ["ninja", "Ninja", "닌자"], ["gunslinger", "Gunslinger", "건너"],
  ["rebellion", "Rebellion", "리벨리온"],   // Kagerou / Oboro have no body sprite in this client → the app falls back to Ninja
];
const JOB_KO = new Map(JOBS.map(([key, , ko]) => [key, ko]));

const enabled = existsSync(GRF_PATH) && existsSync(INDEX_PATH);
let grf: GrfReader | undefined;
let accNames: Record<string, string> = {};
let robeNames: Record<string, string> = {};
let manifest: unknown;

if (enabled) {
  const index = (await Bun.file(INDEX_PATH).json()) as GrfIndex & { __meta__?: { grf: string; size: number; mtime: number } };
  const meta = index.__meta__;
  delete index.__meta__;
  const grfSize = statSync(GRF_PATH).size;
  if (meta && meta.size !== grfSize) {
    console.warn(
      `sprites: ${INDEX_PATH} was built for a different data.grf (${meta.grf}, ${meta.size} bytes; this one is ${grfSize} bytes) — ` +
        `re-run: python3 tools/build_grf_index.py`,
    );
  }
  grf = new GrfReader(GRF_PATH, index);
  accNames = ((await Bun.file(ACC_PATH).json()) as { AccNameTable: Record<string, string> }).AccNameTable;
  robeNames = ((await Bun.file(ROBE_PATH).json()) as { RobeNameTable: Record<string, string> }).RobeNameTable;
  manifest = buildManifest(grf);
  console.log(`sprites: serving from ${GRF_PATH} (${Object.keys(index).length} indexed entries)`);
} else {
  console.warn(
    `sprites: disabled — ` +
      (existsSync(GRF_PATH) ? "" : `data.grf not found at ${GRF_PATH} (set GRF_PATH in server/.env to your game client's data.grf); `) +
      (existsSync(INDEX_PATH) ? "" : `${INDEX_PATH} missing (run: python3 tools/build_grf_index.py)`),
  );
}

function buildManifest(g: GrfReader) {
  const jobs = JOBS.map(([key, name, ko]) => {
    const genders: string[] = [];
    const palettes: Record<string, number> = {};
    for (const [gk, gko] of Object.entries(GENDER)) {
      if (!g.has(`data/sprite/인간족/몸통/${gko}/${ko}_${gko}.spr`)) continue;
      genders.push(gk);
      palettes[gk] = g.list(`data/palette/몸/${ko}_${gko}_`).filter((k) => /_\d+\.pal$/.test(k)).length;
    }
    return { key, name, genders, palettes };
  });
  const hair: Record<string, number[]> = {};
  const hairPalettes: Record<string, Record<string, number>> = {};
  for (const [gk, gko] of Object.entries(GENDER)) {
    const ids = g.list(`data/sprite/인간족/머리통/${gko}/`)
      .map((k) => /\/(\d+)_[남여]\.spr$/.exec(k)?.[1]).filter((x): x is string => !!x).map(Number);
    hair[gk] = [...new Set(ids)].sort((a, b) => a - b);
    hairPalettes[gk] = Object.fromEntries(hair[gk].map((id) => [id, g.list(`data/palette/머리/머리${id}_${gko}_`).length]));
  }
  const acc: Record<string, string[]> = {};
  for (const [id, name] of Object.entries(accNames)) {
    const gs = Object.entries(GENDER).filter(([, gko]) => g.has(`data/sprite/악세사리/${gko}/${gko}${name}.spr`)).map(([gk]) => gk);
    if (gs.length) acc[id] = gs;
  }
  const robes: Record<string, string> = {};
  for (const [id, name] of Object.entries(robeNames)) if (g.list(`data/sprite/로브/${name}/`).length) robes[id] = name;
  return { jobs, hair, hairPalettes, acc, robes: Object.keys(robes) };
}

/** Map an API path to the GRF entry name. */
function resolveEntry(kind: string, file: string): string | null {
  const m = /^(.+)\.(spr|act|pal)$/.exec(file);
  if (!m) return null;
  const [, stem, ext] = m;
  const parts = stem!.split("_");
  const g = GENDER[parts[parts.length - 1]!];
  switch (kind) {
    case "body": { // <job>_<g>
      const ko = JOB_KO.get(parts.slice(0, -1).join("_"));
      return ko && g ? `data/sprite/인간족/몸통/${g}/${ko}_${g}.${ext}` : null;
    }
    case "head": // <hair>_<g>
      return g ? `data/sprite/인간족/머리통/${g}/${parts[0]}_${g}.${ext}` : null;
    case "acc": { // <viewId>_<g>
      const name = accNames[parts[0]!];
      return name && g ? `data/sprite/악세사리/${g}/${g}${name}.${ext}` : null;
    }
    case "robe": { // <robeId>_<job>_<g>
      const name = robeNames[parts[0]!];
      const ko = JOB_KO.get(parts.slice(1, -1).join("_"));
      if (!name || !ko || !g) return null;
      const perJob = `data/sprite/로브/${name}/${g}/${ko}_${g}.${ext}`;
      // Newer robes ship one shared .spr at the folder root and only per-job .act files.
      if (ext === "spr" && grf && !grf.has(perJob)) return `data/sprite/로브/${name}/${name}.spr`;
      return perJob;
    }
    case "pal-body": { // <job>_<g>_<n>
      const gg = GENDER[parts[parts.length - 2]!];
      const ko = JOB_KO.get(parts.slice(0, -2).join("_"));
      return ko && gg ? `data/palette/몸/${ko}_${gg}_${parts[parts.length - 1]}.pal` : null;
    }
    case "pal-head": { // <hair>_<g>_<n>
      const gg = GENDER[parts[1]!];
      return gg ? `data/palette/머리/머리${parts[0]}_${gg}_${parts[2]}.pal` : null;
    }
  }
  return null;
}

export const spriteRoutes = new Elysia({ prefix: "/sprites" })
  .get("/manifest.json", ({ status }) => (manifest ? manifest : status(503, { error: "sprites disabled" })))
  .get(
    "/:kind/:file",
    ({ params, status }) => {
      if (!grf) return status(503, { error: "sprites disabled" });
      const entry = resolveEntry(params.kind, params.file);
      if (!entry) return status(404, { error: "unknown sprite path" });
      const data = grf.read(entry);
      if (!data) return status(404, { error: "not in GRF", entry });
      return new Response(data, {
        headers: { "content-type": "application/octet-stream", "cache-control": "public, max-age=86400" },
      });
    },
    { params: t.Object({ kind: t.String(), file: t.String() }) },
  );
