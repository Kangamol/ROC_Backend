#!/usr/bin/env python3
"""Write data/grf_index.json: a lookup of the GRF entries the API serves at
runtime (sprites + palettes), so the Bun server can read them straight out of
data.grf without parsing the CP949 file table itself.

Re-run after the game client patches.  Format:
  { "data/sprite/...": [offset, compSize, compSizeAligned, realSize, flags], ... }
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from grf import Grf

ROOT = Path(__file__).resolve().parent.parent
GRF = ROOT / 'client' / 'RagnarokClassic' / 'data.grf'
OUT = ROOT / 'data' / 'grf_index.json'
PREFIXES = ('data/sprite/인간족/', 'data/sprite/악세사리/', 'data/sprite/로브/', 'data/sprite/방패/', 'data/palette/')


def main():
    g = Grf(GRF)
    index = {}
    for key, e in g.entries.items():
        if key.startswith(PREFIXES):
            index[key] = [e.offset, e.comp_size, e.comp_size_aligned, e.real_size, e.flags]
    json.dump(index, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print(f'{len(index)} entries -> {OUT} ({OUT.stat().st_size / 1e6:.1f} MB)')


if __name__ == '__main__':
    main()
