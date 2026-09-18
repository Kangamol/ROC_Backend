#!/usr/bin/env python3
"""Convert data/items_raw.json (dumped from iteminfo_new.lub) into data/items.json.

Parses the Thai client description text into structured fields (type, ATK,
DEF, weight, weapon level, required level, jobs, headgear position, element,
card compound slot) and classifies each item into an itemType / equipLocations
so it can be seeded straight into the database.
"""
import json, re, sys, collections
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'data' / 'items_raw.json'
OUT = ROOT / 'data' / 'items.json'

COLOR = re.compile(r'\^[0-9a-fA-F]{6}')
def clean(s): return COLOR.sub('', s).replace(' ', ' ').strip()

def grab(text, pattern, cast=str, flags=re.I):
    m = re.search(pattern, text, flags)
    if not m: return None
    v = m.group(1).strip()
    if cast is int:
        n = re.match(r'\d+', v)
        return int(n.group()) if n else None
    return v

# --- description field patterns (many label spellings exist in the client) ---
P_TYPE   = r'ประเภท\s*:\s*(?:([A-Za-z][A-Za-z \-\(\)/]*?)(?=\s*(?:[฀-๿]|Lv|$|\n|:))|([฀-๿][^\n:]*?)(?=\s*(?:พลัง|ป้องกัน|โจมตี|น้ำหน|Lv|เลเวล|ใช้|ตำแหน่ง|อาชีพ|ธาตุ|$|\n|:)))'
P_ATK    = r'(?:พลังโจมตี|โจมตี)\s*:\s*(\d+)'
P_MATK   = r'MATK\s*[:\+]\s*(\d+)'
P_DEF    = r'(?:พลังพลังป้องกัน|พลังป้องกัน|ป้องกัน)\s*:\s*(\d+)'
P_WEIGHT = r'น้ำหน[ัั้]ก\s*:\s*(\d+)'
P_WLV    = r'(?:Lv\.?\s*ของอาวุธ|เลเวลอาวุธ|เลเวลของอาวุธ|อาวุธ\s*Lv\.?|อาวุธเลเวล|Lv\.?\s*อาวุธ|Weapon\s*Lv\.?)\s*:\s*(\d+)'
P_RLV    = r'(?:เลเวลที่ต้องการ|Lv\.?\s*ที่ต้องการ|ต้องการ\s*Lv\.?|เลเวล\.?\s*ที่ต้องการ|Level\s*ที่ต้องการ|Lv\.?\s*ที่สวมใส่ได้)\s*:\s*(\d+)'
P_JOBS   = r'(?:อาชีพ(?:ที่ใส่ได้|ที่สวมใส่ได้|ที่สวมใส่|ที่ใช้ได้|ที่ใช้)?)\s*:\s*([^\n]+)'
# position labels: "ใช้สำหรับ : Upper", "ตำแหน่ง : Middle-Lower", "ตำแหน่งที่สวมใส่ : Garment", "ต่ำแหน่ง : Upper" (typo),
# "ตำแหน่ง Upper" (no colon), and a second "ประเภท : Lower" on some costumes.
P_HLOC   = r'(?:ใช้สำหรับ|ตำแหน่ง(?:ที่สวมใส่)?|ต่ำแหน่ง)\s*:\s*([^\n:]+)|(?:ตำแหน่ง|ประเภท)\s*:?\s*((?:Upper|Middle|Lower|Garment)[^\n:]*)'
P_CLOC   = r'(?:ใช้กับ|ใส่กับ|ติดตั้ง)\s*:\s*([A-Za-z \(\)]+)'
P_ELEM   = r'ธาตุ\s*:\s*([A-Za-z]+)'

WEAPON_TYPES = {
    'dagger':'DAGGER','sword':'SWORD_1H','one-handed':'SWORD_1H','one-handed sword':'SWORD_1H','one':'SWORD_1H',
    'two-handed':'SWORD_2H','two-handed sword':'SWORD_2H','two hand sword':'SWORD_2H','two':'SWORD_2H','both':'SWORD_2H',
    'spear':'SPEAR_1H','two-handed spear':'SPEAR_2H','axe':'AXE_1H','two-handed axe':'AXE_2H',
    'mace':'MACE','rod':'STAFF_1H','staff':'STAFF_1H','one-handed staff':'STAFF_1H','one hand staff':'STAFF_1H','ไม้เท้ามือเดียว':'STAFF_1H','two-handed staff':'STAFF_2H','wand':'STAFF_1H',
    'bow':'BOW','ธนู':'BOW','katar':'KATAR','book':'BOOK','knuckle':'KNUCKLE','claw':'KNUCKLE','fist':'KNUCKLE',
    'instrument':'INSTRUMENT','musical instrument':'INSTRUMENT','whip':'WHIP',
    'huuma':'HUUMA','fuuma':'HUUMA','huuma shuriken':'HUUMA',
    'pistol':'REVOLVER','revolver':'REVOLVER','rifle':'RIFLE','shotgun':'SHOTGUN',
    'gatling':'GATLING','gatling gun':'GATLING','grenade':'GRENADE_LAUNCHER','grenade launcher':'GRENADE_LAUNCHER',
}
ARMOR_TYPES = {
    'armor':'ARMOR','ชุดเกราะ':'ARMOR','robe':'ARMOR','shield':'SHIELD','garment':'GARMENT',
    'shoes':'SHOES','footwear':'SHOES','foot gear':'SHOES','foot':'SHOES','boots':'SHOES','shoe':'SHOES',
    'accessory':'ACCESSORY','accessary':'ACCESSORY','accessory(right)':'ACCESSORY_R','accessory (right)':'ACCESSORY_R',
    'accessory(left)':'ACCESSORY_L','accessory (left)':'ACCESSORY_L',
    'headgear':'HEADGEAR','headgear defence':'HEADGEAR','helm':'HEADGEAR','helmet':'HEADGEAR','helemt':'HEADGEAR','hat':'HEADGEAR','หมวก':'HEADGEAR',
    'เครื่องประดับ':'ACCESSORY','accssory':'ACCESSORY','armour':'ARMOR','garmet':'GARMENT',
    'costume':'COSTUME','costume equipment':'COSTUME','shadow':'SHADOW','shadow equipment':'SHADOW','อุปกรณ์ shadow':'SHADOW',
}
TWO_HANDED = {'SWORD_2H','SPEAR_2H','AXE_2H','STAFF_2H','BOW','KATAR','INSTRUMENT','WHIP','HUUMA','RIFLE','SHOTGUN','GATLING','GRENADE_LAUNCHER'}
AMMO_TYPES = {'arrow':'ARROW','ลูกธนู':'ARROW','bullet':'BULLET','กระสุน':'BULLET','throwing weapon':'THROW','shell':'SHELL','grenade shell':'SHELL','kunai':'KUNAI','shuriken':'SHURIKEN','cannon ball':'CANNONBALL'}

def norm_type(t):
    return re.sub(r'\s+', ' ', t.lower()).strip() if t else ''

def find_head_loc(text):
    """First position label whose value parses (descriptions also use "ใช้สำหรับ : 7 วัน" etc.)."""
    for m in re.finditer(P_HLOC, text, re.I):
        locs = parse_head_loc(m.group(1) or m.group(2))
        if locs: return locs
    return []

def parse_head_loc(s):
    """'Upper-Middle น้ำหนัก : 0' -> ['HEAD_TOP','HEAD_MID']; 'Garment' (costume) -> ['GARMENT']."""
    if not s: return []
    s = re.split(r'น้ำหน|พลัง|ป้องกัน', s.lower())[0]
    out = []
    if 'upper' in s or 'top' in s or 'บน' in s: out.append('HEAD_TOP')
    if 'mid' in s or 'medium' in s or 'กลาง' in s: out.append('HEAD_MID')
    if 'low' in s or 'ล่าง' in s: out.append('HEAD_LOW')
    if 'garment' in s or 'robe' in s or 'ผ้าคลุม' in s: out.append('GARMENT')
    return out

def parse_card_loc(s):
    if not s: return None
    s = s.lower()
    for k, v in [('weapon','WEAPON'),('อาวุธ','WEAPON'),('armor','ARMOR'),('เกราะ','ARMOR'),('ชุดเกราะ','ARMOR'),
                 ('shield','SHIELD'),('โล่','SHIELD'),('garment','GARMENT'),('ผ้าคลุม','GARMENT'),('เสื้อคลุม','GARMENT'),
                 ('foot','SHOES'),('shoe','SHOES'),('boot','SHOES'),('รองเท้า','SHOES'),
                 ('accessory (right)','ACCESSORY_R'),('accessory(right)','ACCESSORY_R'),
                 ('accessory (left)','ACCESSORY_L'),('accessory(left)','ACCESSORY_L'),('accessory','ACCESSORY'),('accessary','ACCESSORY'),('เครื่องประดับ','ACCESSORY'),
                 ('headgear','HEADGEAR'),('helm','HEADGEAR'),('head','HEADGEAR'),('หมวก','HEADGEAR'),('ศีรษะ','HEADGEAR'),
                 ('ทุกสล็อต','ANY'),('ทุก slot','ANY'),('all slot','ANY')]:
        if k in s: return v
    return None

from effects import parse_effects

# --- costume enchant stones ("STR Stone (Upper)", "High Wizard Stone (Garment)", "Change STR (Middle)",
# "Electric Effect (Middle)" ...) ---------------------------------------------------------------
# ETC items that slot into a costume piece. Position comes from the "(Upper)" suffix in the name, else
# from the description ("Slot ของ Costume Garment", "Slot ของ Garment", "Middle Costume").
# The client also lists the *slotted* card form of each stone (IDs 29xxx / 310xxx, no slot text);
# those are only kept when no ETC stone of the same name exists, to avoid showing every stone twice.
_STONE_POS = {'upper': 'COSTUME_TOP', 'top': 'COSTUME_TOP', 'middle': 'COSTUME_MID', 'mid': 'COSTUME_MID',
              'lower': 'COSTUME_LOW', 'low': 'COSTUME_LOW', 'garment': 'COSTUME_GARMENT', 'robe': 'COSTUME_GARMENT'}
P_STONE_NAME = re.compile(r'\((upper|middle|lower|garment|top|mid|low|robe)\)', re.I)
P_STONE_DESC = re.compile(r'(?:costume\s*(?:ส่วน|ประเภท)?\s*\(?(upper|middle|lower|garment)|(upper|middle|lower|garment)\s*costume'
                          r'|slot\s*ของ\s*(upper|middle|lower|garment))', re.I)
P_STONE_TEXT = re.compile(r'slot|สล็อต|enchant|ติดตั้ง|costume|คอสตูม', re.I)

# Every option ID referenced by data/enchant_pools.json is an NPC enchant (Zodiac Mettle/…/Gems, Battle Pass
# Hit Plus / Spirit of Knight / [Event] X's Memory …). The client files them as ETC; we expose them as CARD/ENCHANT
# so the enchant picker can list them and they never show up as ordinary cards. 29061–29120 are the Zodiac
# slot-4 families Lv.1–10 (the table only lists Lv.1–4, the rest exist in the client).
def _pool_option_ids():
    path = ROOT / 'data' / 'enchant_pools.json'
    ids = set(range(29061, 29121))
    if path.exists():
        pools = json.load(open(path, encoding='utf-8'))
        for rule in [pools.get('default')] + list(pools.get('items', {}).values()):
            for slot in (rule or {}).get('slots', []):
                ids.update(slot.get('options') or [])
    return ids
ZODIAC_ENCHANTS = _pool_option_ids()

def is_stone_card_form(item_id):
    return 29000 <= item_id < 30000 or 310000 <= item_id < 320000

def costume_stone_location(item_id, name, text):
    m = P_STONE_NAME.search(name)
    if m:
        if is_stone_card_form(item_id) or P_STONE_TEXT.search(text):
            return _STONE_POS.get(m.group(1).lower())
        return None
    if not re.search(r'stone|หิน', name, re.I):
        return None
    m = P_STONE_DESC.search(text)
    if m:
        return _STONE_POS.get(next(g for g in m.groups() if g).lower())
    return None

def stone_key(name):
    return re.sub(r'\s+', ' ', name).strip().lower()

def costume_locs(item_id, head_locs):
    if head_locs:
        return ['COSTUME_GARMENT' if l == 'GARMENT' else 'COSTUME_' + l[5:] for l in head_locs]
    return ['COSTUME_GARMENT'] if 20500 <= item_id < 20700 else ['COSTUME_TOP']

def classify(item_id, typ, head_locs, card_loc, is_costume=False, def_=None, name=''):
    """Return (itemType, subType, equipLocations).

    `is_costume` is the client's own costume flag (iteminfo `costume = true`); it is
    reliable for garment costumes whose description says "ประเภท : Garment"."""
    t = norm_type(typ)
    if 4700 <= item_id < 5000 or item_id in ZODIAC_ENCHANTS:
        return 'CARD', 'ENCHANT', []   # NPC enchant options (STR+1, Fighting Spirit, Mettle Lv.N, Zodiac Gems …) — never a real card
    if t in ('card', 'การ์ด') or card_loc and 4000 <= item_id < 5000:
        return 'CARD', 'CARD', []
    if is_costume and t in ('garment', 'headgear', '') and (name.lower().startswith('costume') or not def_):
        if t == 'garment':
            return 'COSTUME', 'COSTUME', ['COSTUME_GARMENT']
        if head_locs:
            return 'COSTUME', 'COSTUME', costume_locs(item_id, head_locs)
    if t in WEAPON_TYPES:
        sub = WEAPON_TYPES[t]
        return 'WEAPON', sub, ['WEAPON'] if not sub.endswith('_2H') and sub not in ('BOW','KATAR','INSTRUMENT','WHIP','HUUMA','RIFLE','SHOTGUN','GATLING','GRENADE_LAUNCHER') else ['WEAPON','SHIELD']
    if t in AMMO_TYPES:
        return 'AMMO', AMMO_TYPES[t], ['AMMO']
    if t in ARMOR_TYPES:
        sub = ARMOR_TYPES[t]
        if sub == 'HEADGEAR':
            return 'ARMOR', 'HEADGEAR', [l for l in head_locs if l != 'GARMENT'] or ['HEAD_TOP']
        if sub == 'COSTUME':
            return 'COSTUME', 'COSTUME', costume_locs(item_id, head_locs)
        if sub == 'SHADOW':
            return 'SHADOW', 'SHADOW', ['SHADOW']
        if sub == 'ACCESSORY': return 'ARMOR', 'ACCESSORY', ['ACCESSORY_1', 'ACCESSORY_2']
        if sub == 'ACCESSORY_R': return 'ARMOR', 'ACCESSORY', ['ACCESSORY_1']
        if sub == 'ACCESSORY_L': return 'ARMOR', 'ACCESSORY', ['ACCESSORY_2']
        return 'ARMOR', sub, [sub]
    if 'egg' in t: return 'PET_EGG', 'PET_EGG', []
    if 'pet' in t or 'taming' in t or 'จับสัตว์' in t: return 'ETC', 'PET', []
    # fall back on ID ranges (official RO layout)
    if 4000 <= item_id < 5000: return 'CARD', 'CARD', []
    if 5000 <= item_id < 6000 or 18500 <= item_id < 20000: return 'ARMOR', 'HEADGEAR', head_locs or ['HEAD_TOP']
    if 20000 <= item_id < 20700 or is_costume and head_locs: return 'COSTUME', 'COSTUME', costume_locs(item_id, head_locs)
    if 24000 <= item_id < 25000: return 'SHADOW', 'SHADOW', ['SHADOW']
    if 1100 <= item_id < 2000 or 13000 <= item_id < 13500 or 21000 <= item_id < 22000: return 'WEAPON', 'UNKNOWN', ['WEAPON']
    if 2100 <= item_id < 2200: return 'ARMOR', 'SHIELD', ['SHIELD']
    if 2300 <= item_id < 2400 or 15000 <= item_id < 15200: return 'ARMOR', 'ARMOR', ['ARMOR']
    if 2400 <= item_id < 2500 or 22000 <= item_id < 22200: return 'ARMOR', 'SHOES', ['SHOES']
    if 2500 <= item_id < 2600 or 20700 <= item_id < 21000: return 'ARMOR', 'GARMENT', ['GARMENT']
    if 2600 <= item_id < 3000 or 28300 <= item_id < 28700: return 'ARMOR', 'ACCESSORY', ['ACCESSORY_1', 'ACCESSORY_2']
    if 500 <= item_id < 700 or 11500 <= item_id < 12800 or 14500 <= item_id < 14700: return 'CONSUMABLE', 'CONSUMABLE', []
    if 1750 <= item_id < 1800 or 13200 <= item_id < 13300: return 'AMMO', 'UNKNOWN', ['AMMO']
    return 'ETC', 'ETC', []

OVERRIDES = ROOT / 'data' / 'manual_overrides.json'   # from tools/export_review.py --import
MANUAL = json.load(open(OVERRIDES, encoding='utf-8')) if OVERRIDES.exists() else {}
FALLBACK = ROOT / 'data' / 'card_location_fallback.json'
CARD_LOC_FALLBACK = json.load(open(FALLBACK, encoding='utf-8')) if FALLBACK.exists() else {}

def main():
    raw = json.load(open(SRC, encoding='utf-8'))
    items, stats = [], collections.Counter()
    etc_stone_names = {stone_key(v.get('identifiedDisplayName', '')) for sid, v in raw.items()
                       if sid.isdigit() and not is_stone_card_form(int(sid)) and P_STONE_NAME.search(v.get('identifiedDisplayName', ''))}
    for sid, v in raw.items():
        if not sid.isdigit(): continue
        item_id = int(sid)
        lines = [clean(l) for l in v.get('identifiedDescriptionName', []) if isinstance(l, str)]
        text = '\n'.join(lines)
        mt = re.search(P_TYPE, text, re.I)
        typ = (mt.group(1) or mt.group(2)).strip() if mt else None
        head_locs = find_head_loc(text)
        card_loc = parse_card_loc(grab(text, P_CLOC))
        if card_loc is None and ((typ or '').strip().lower() in ('card', 'การ์ด') or 4000 <= item_id < 5000 or item_id in ZODIAC_ENCHANTS):
            # cards use many label spellings ("ประเภท : Accessory", "อาชีพ : Footwear", "ส่วนที่ใส่ : Armor"):
            # take the first "label : value" whose value is an equip position
            for m in re.finditer(r'[^\n:]{1,24}\s*:\s*([^\n:]{2,40})', text):
                loc = parse_card_loc(m.group(1))
                if loc and m.group(1).strip().lower() not in ('card', 'การ์ด'):
                    card_loc = loc
                    break
            if card_loc is None and (4700 <= item_id < 5000 or item_id in ZODIAC_ENCHANTS):
                card_loc = 'ANY'  # enchant "cards" (STR+1 ...) go into any free slot
            if card_loc is None:
                card_loc = CARD_LOC_FALLBACK.get(str(item_id))  # rAthena (drop cards match the official DB)
                if card_loc: stats['cardLocation_from_rathena'] += 1
        name = v.get('identifiedDisplayName', '')
        item_type, sub_type, locs = classify(item_id, typ, head_locs, card_loc, bool(v.get('costume') or v.get('Costume')), grab(text, P_DEF, int), name)
        stone_loc = costume_stone_location(item_id, name, text) if item_type == 'ETC' else None
        if stone_loc and is_stone_card_form(item_id) and stone_key(name) in etc_stone_names:
            stone_loc = None   # slotted-card duplicate of an ETC stone
            stats['stone_card_duplicate_skipped'] += 1
        if stone_loc:
            sub_type, card_loc = 'COSTUME_STONE', stone_loc
        jobs = grab(text, P_JOBS)
        bonuses, cond, unparsed, parsed, conditional = parse_effects(lines) if item_type in ('WEAPON','ARMOR','CARD','COSTUME','SHADOW') or stone_loc else ({}, {}, [], [], [])
        rec = {
            'id': item_id,
            'name': v.get('identifiedDisplayName', ''),
            'unidentifiedName': v.get('unidentifiedDisplayName') or None,
            'resourceName': v.get('identifiedResourceName', ''),
            'unidentifiedResourceName': v.get('unidentifiedResourceName') or None,
            'slotCount': int(v.get('slotCount') or 0),
            'viewId': int(v.get('ClassNum') or 0),
            'isCostume': bool(v.get('costume') or v.get('Costume')),
            'effectId': v.get('EffectID'),
            'itemType': item_type,
            'subType': sub_type,
            'typeLabel': typ,
            'equipLocations': locs,
            'cardLocation': card_loc if item_type == 'CARD' or stone_loc else None,
            'atk': grab(text, P_ATK, int),
            'matk': grab(text, P_MATK, int),
            'def': grab(text, P_DEF, int),
            'weight': grab(text, P_WEIGHT, int),
            'weaponLevel': grab(text, P_WLV, int),
            'requiredLevel': grab(text, P_RLV, int),
            'element': (grab(text, P_ELEM) or None),
            'jobs': jobs.strip() if jobs else None,
            'description': text,
            'descriptionRaw': v.get('identifiedDescriptionName', []),
            'bonuses': bonuses,
            'conditionalBonuses': cond,
            'unparsedLines': unparsed,
            'parsedLines': parsed,
            'conditionalLines': conditional,
        }
        fix = MANUAL.get(sid)
        if fix:
            rec.update({k: v for k, v in fix.items() if k in rec})
            if 'subType' in fix and rec['itemType'] == 'WEAPON':
                rec['equipLocations'] = ['WEAPON', 'SHIELD'] if fix['subType'] in TWO_HANDED else ['WEAPON']
            stats['manual_override'] += 1
        items.append(rec)
        stats[item_type] += 1
    items.sort(key=lambda r: r['id'])
    json.dump(items, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'wrote {len(items)} items -> {OUT}')
    for k, c in stats.most_common(): print(f'  {k:12s} {c}')

if __name__ == '__main__':
    main()
