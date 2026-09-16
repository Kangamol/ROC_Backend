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
