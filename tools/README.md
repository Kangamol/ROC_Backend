# Data extraction pipeline (Phase 1)

Source: local Gnjoy RO Classic (TH) client — `RagnarokClassic.zip` at project root.

```
RagnarokClassic.zip
  └─ System/iteminfo_new.lub   (Lua 5.1 bytecode, 32-bit)  ──lua51──▶ data/items_raw.json
  └─ data.grf                  (GRF 0x200, DES mixcrypt)   ──grf.py──▶ public/assets/{items,collection}/<id>.png
                                                data/items_raw.json ──convert_items.py──▶ data/items.json
```

## Steps

1. Unzip the client once (only needed files):
   `unzip -o RagnarokClassic.zip "RagnarokClassic/data.grf" "RagnarokClassic/System/*" -d client`
2. Dump iteminfo (the bundled `tools/lua51` is Lua 5.1.5 patched in `lundump.c` to accept the
   client's 32-bit `size_t` bytecode header — stock 64-bit Lua rejects it with "bad header"):
   `./tools/lua51 tools/dump_iteminfo.lua client/RagnarokClassic/System/iteminfo_new.lub data/items_raw.json`
3. Parse descriptions into structured fields:
   `python3 tools/convert_items.py`
4. Extract icons + collection images (needs Pillow):
   `python3 tools/extract_assets.py`

## Notes

- Strings in the .lub are already UTF-8 (Thai descriptions, Korean resource names).
- `iteminfo_new.lub` is the live file (patched by the launcher); `itemInfo.lub` is a stale 2022 copy.
- The client only carries *display* data. ATK/DEF/weight/levels/jobs are parsed out of the
  Thai description text (label spellings vary a lot — see the regexes in `convert_items.py`).
  Bonus effects ("STR + 2") are parsed heuristically into `bonuses`; complex scripts are not.
- `data/asset_report.json` lists items whose icon/collection image is missing from the GRF.

## Sprites (visual preview)

5. `python3 tools/build_grf_index.py` — writes `data/grf_index.json` (offsets of sprite/palette entries) so the
   Bun server can read sprites straight from `data.grf`. Needs `data/lua/acc.json` + `robe.json`
   (viewId → sprite name, dumped with `tools/dump_lua_globals.lua` from `accessoryid/accname/spriterobeid/spriterobename.lub`;
   those tables are CP949, not UTF-8 — the dump step transcodes them).
- GRF flag 4 ("DES") only encrypts the first 20 blocks; flag 2 is mixcrypt. Both handled in `grf.py`.
- `tools/sprite.py` is the Python reference parser used to validate anchors (see the 8-direction test).

## Card compound position

`convert_items.py` reads the card's position from any `label : value` pair in the description (the client
uses ~10 spellings: "ใช้กับ", "ติดตั้ง", "Slot", "Location", "Device", "ส่วนที่ใส่", Thai words like รองเท้า/อาวุธ…).
Cards that still have no position fall back to `data/card_location_fallback.json` (derived from rAthena
`item_db_etc.yml`, position only — never stats). IDs 4700–4999 are enchant "cards" → `ANY`.

## Costume position / enchant stones

- Costume position comes from `ใช้สำหรับ / ตำแหน่ง / ตำแหน่งที่สวมใส่ : Upper|Middle|Lower|Garment` (plus a few Thai/typo
  variants); items whose description says `ประเภท : Garment` but carry the client's `costume = true` flag are
  costume garments, not garments. The `ประเภท` regex stops at any Thai word (`ป้องกัน`, `โจมตี` …) — the old
  version silently dropped ~440 type labels and fell back to ID ranges.
- Costume enchant stones (`subType = COSTUME_STONE`, `cardLocation = COSTUME_*`) are ETC items whose name ends in
  `(Upper|Middle|Lower|Garment)` — job stones, `Change STR (Middle)`, visual `... Effect (Middle)` / `Footprint (Garment)`.
  The client also carries the slotted-card form of every stone (IDs 29xxx / 310xxx); those are only kept when no
  ETC stone with the same name exists (11 such: `ATK + 1% (Upper)`, `Fatal (Garment)`, `Reload Stone (…)` …).
