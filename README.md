# RO Equipment Simulator (Gnjoy Classic TH)

Visual & equipment simulator built on item data extracted from the **local Gnjoy RO Classic client**,
so names, icons, slots and descriptions match the live Thai server.

```
tools/      Python/Lua extraction pipeline  (client .lub + .grf  →  data/items.json + public/assets)
data/       items.json (11,154 items, structured)  ·  asset_report.json
public/     assets/items/<id>.png (icons)  ·  assets/collection/<id>.png
server/     ElysiaJS + Prisma 7 + PostgreSQL API  (bun)
web/        Vue 3 + Vuetify 3 frontend
```

## Quick start

```bash
# 1. database
docker compose up -d

# 2. api  (http://localhost:3000)
cd server
bun install
bunx prisma migrate dev          # create tables + generate client
bun run db:seed                  # load data/items.json (add --reset to reload)
bun run dev

# 3. web  (http://localhost:5173 — proxies /api and /assets to the server)
cd web
bun install
bun run dev

# 4. rebuild data from the client (only when the game patches)
#    see tools/README.md
```

## Frontend (web/)

- `src/lib/slots.ts` — slot definitions (which `equipLocations` / card types each slot accepts)
- `src/lib/stats.ts` — stat engine (pre-renewal formulas; bonuses come from parsed descriptions)
- `src/stores/build.ts` — Pinia store: character, equipment, cards, refine, save/load via API
- `src/components/` — `EquipmentSlot`, `ItemPickerDialog`, `ItemTooltip`, `CharacterPanel`, `StatPanel`
- Share links: `/b/<shareCode>` loads a saved build
- `src/lib/ro/` — browser-side parsers for Gravity `.spr` / `.act` and a canvas compositor
  (`renderer.ts`: body → head → headgear using ACT anchors, palette swap for hair/cloth colours)
- `CharacterPreview.vue` — live sprite of the character wearing the equipped headgear
  (gender, hair style/colour, cloth colour, 8 directions, idle/walk/sit/attack)

## Visual preview data

The API serves sprites **directly out of `client/RagnarokClassic/data.grf`** (`server/src/grf.ts`,
`server/src/sprites.ts`) — nothing is pre-extracted. It needs `data/grf_index.json`
(`python3 tools/build_grf_index.py`, re-run after a client patch) and `data/lua/{acc,robe}.json`.
Routes: `/sprites/manifest.json`, `/sprites/body/<job>_<m|f>.spr|act`, `/sprites/head/<hair>_<g>.*`,
`/sprites/acc/<viewId>_<g>.*`, `/sprites/robe/<robeId>_<job>_<g>.*`, `/sprites/pal-body/…`, `/sprites/pal-head/…`.
Rendered: body, hair (+colours), headgear (upper/mid/lower, including self-animated ones), garments
(newer robes keep one shared `.spr` at the folder root — the server falls back to it). Costume pieces hide the normal
equipment in the same position. Weapons/shields are not rendered yet.

## API

| Method | Path | Notes |
|---|---|---|
| GET | `/api/jobs` | per-job base HP/SP per level, ASPD per weapon, job-level stat bonuses, max weight (`data/jobs.json`, built by `tools/build_job_data.py` from rAthena **pre-re** job tables — job data only, never items) |
| GET | `/api/meta` | counts per itemType / equipLocation |
| GET | `/api/items` | `search`, `type`, `subType`, `location`, `cardLocation`, `slots`, `limit`, `offset` |
| GET | `/api/items/:id` | full item incl. description + parsed bonuses |
| POST | `/api/builds` | save a build → `{ shareCode }` |
| GET | `/api/builds/:shareCode` | build with items and cards resolved |
| GET | `/assets/items/:id.png` | item icon (also `/assets/collection/:id.png`) |
