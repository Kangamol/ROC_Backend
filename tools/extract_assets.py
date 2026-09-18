#!/usr/bin/env python3
"""Extract item icons and collection images from data.grf for every item in
data/items.json. Output PNGs (magenta background made transparent) named by
item ID so the frontend can reference /assets/items/<id>.png.
"""
import json, io, sys, collections
from pathlib import Path
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parent))
from grf import open_grf

ROOT = Path(__file__).resolve().parent.parent
ITEMS = ROOT / 'data' / 'items.json'
OUT_ICON = ROOT / 'public' / 'assets' / 'items'
OUT_COLL = ROOT / 'public' / 'assets' / 'collection'
UI = 'data/texture/유저인터페이스/'

def bmp_to_png(data, dest):
    img = Image.open(io.BytesIO(data)).convert('RGBA')
    px = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if r >= 0xF8 and g <= 0x08 and b >= 0xF8:  # RO magenta key
                px[x, y] = (0, 0, 0, 0)
    img.save(dest, 'PNG', optimize=True)

def main():
    g = open_grf(sys.argv[1] if len(sys.argv) > 1 else None)
    items = json.load(open(ITEMS, encoding='utf-8'))
    OUT_ICON.mkdir(parents=True, exist_ok=True); OUT_COLL.mkdir(parents=True, exist_ok=True)
    stats = collections.Counter(); missing = []; failed = []
    cache = {}
    for it in items:
        res = it['resourceName']
        if not res: stats['no_resource'] += 1; continue
        for kind, folder, out_dir in (('icon', 'item', OUT_ICON), ('collection', 'collection', OUT_COLL)):
            entry = g.get(f'{UI}{folder}/{res}.bmp')
            if entry is None:
                stats[f'{kind}_missing'] += 1
                if kind == 'icon': missing.append((it['id'], it['name'], res))
                continue
            dest = out_dir / f"{it['id']}.png"
            if dest.exists(): stats[f'{kind}_ok'] += 1; continue
            try:
                key = entry.name.lower()
                data = cache.get(key)
                if data is None:
                    data = g.read(entry)
                    if data[:2] != b'BM': raise ValueError(f'not BMP (flags={entry.flags}, head={data[:4]!r})')
                    cache[key] = data
                bmp_to_png(data, dest)
                stats[f'{kind}_ok'] += 1
            except Exception as e:
                stats[f'{kind}_failed'] += 1
                failed.append((it['id'], res, kind, str(e)[:80]))
    print(dict(stats))
    json.dump({'missing_icons': missing, 'failed': failed}, open(ROOT / 'data' / 'asset_report.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('failed samples:', failed[:5])
    print('missing icon samples:', missing[:10])

if __name__ == '__main__':
    main()
