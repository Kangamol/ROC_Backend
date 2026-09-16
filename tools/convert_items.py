#!/usr/bin/env python3
"""Convert data/items_raw.json (dumped from iteminfo_new.lub) into data/items.json.

Parses the Thai client description text into structured fields (type, ATK,
DEF, weight, weapon level, required level, jobs, headgear position, element,
card compound slot) and classifies each item into an itemType / equipLocations
so it can be seeded straight into the database.
"""
import json, re, sys, collections
from pathlib import Path

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
P_TYPE   = r'ประเภท\s*:\s*([A-Za-z][A-Za-z \-\(\)/]*?)(?=\s*(?:พลัง|น้ำหน|Lv|เลเวล|ใช้|ตำแหน่ง|อาชีพ|ธาตุ|$|\n))'
P_ATK    = r'(?:พลังโจมตี|โจมตี)\s*:\s*(\d+)'
P_MATK   = r'MATK\s*[:\+]\s*(\d+)'
P_DEF    = r'(?:พลังพลังป้องกัน|พลังป้องกัน|ป้องกัน)\s*:\s*(\d+)'
P_WEIGHT = r'น้ำหน[ัั้]ก\s*:\s*(\d+)'
P_WLV    = r'(?:Lv\.?\s*ของอาวุธ|เลเวลอาวุธ|เลเวลของอาวุธ|อาวุธ\s*Lv\.?|อาวุธเลเวล|Lv\.?\s*อาวุธ|Weapon\s*Lv\.?)\s*:\s*(\d+)'
P_RLV    = r'(?:เลเวลที่ต้องการ|Lv\.?\s*ที่ต้องการ|ต้องการ\s*Lv\.?|เลเวล\.?\s*ที่ต้องการ|Level\s*ที่ต้องการ|Lv\.?\s*ที่สวมใส่ได้)\s*:\s*(\d+)'
P_JOBS   = r'(?:อาชีพ(?:ที่ใส่ได้|ที่สวมใส่ได้|ที่สวมใส่|ที่ใช้ได้|ที่ใช้)?)\s*:\s*([^\n]+)'
P_HLOC   = r'(?:ใช้สำหรับ|ตำแหน่ง)\s*:\s*([A-Za-z ,./\-]+)'
P_CLOC   = r'(?:ใช้กับ|ใส่กับ|ติดตั้ง)\s*:\s*([A-Za-z \(\)]+)'
P_ELEM   = r'ธาตุ\s*:\s*([A-Za-z]+)'

WEAPON_TYPES = {
    'dagger':'DAGGER','sword':'SWORD_1H','one-handed':'SWORD_1H','one-handed sword':'SWORD_1H','one':'SWORD_1H',
    'two-handed':'SWORD_2H','two-handed sword':'SWORD_2H','two':'SWORD_2H','both':'SWORD_2H',
    'spear':'SPEAR_1H','two-handed spear':'SPEAR_2H','axe':'AXE_1H','two-handed axe':'AXE_2H',
    'mace':'MACE','rod':'STAFF_1H','staff':'STAFF_1H','one-handed staff':'STAFF_1H','two-handed staff':'STAFF_2H','wand':'STAFF_1H',
    'bow':'BOW','katar':'KATAR','book':'BOOK','knuckle':'KNUCKLE','claw':'KNUCKLE','fist':'KNUCKLE',
    'instrument':'INSTRUMENT','musical instrument':'INSTRUMENT','whip':'WHIP',
    'huuma':'HUUMA','fuuma':'HUUMA','huuma shuriken':'HUUMA',
    'pistol':'REVOLVER','revolver':'REVOLVER','rifle':'RIFLE','shotgun':'SHOTGUN',
    'gatling':'GATLING','gatling gun':'GATLING','grenade':'GRENADE_LAUNCHER','grenade launcher':'GRENADE_LAUNCHER',
}
ARMOR_TYPES = {
    'armor':'ARMOR','robe':'ARMOR','shield':'SHIELD','garment':'GARMENT',
    'shoes':'SHOES','footwear':'SHOES','foot gear':'SHOES','foot':'SHOES','boots':'SHOES','shoe':'SHOES',
    'accessory':'ACCESSORY','accessary':'ACCESSORY','accessory(right)':'ACCESSORY_R','accessory (right)':'ACCESSORY_R',
    'accessory(left)':'ACCESSORY_L','accessory (left)':'ACCESSORY_L',
    'headgear':'HEADGEAR','helm':'HEADGEAR','hat':'HEADGEAR',
    'costume':'COSTUME','shadow':'SHADOW','shadow equipment':'SHADOW',
}
AMMO_TYPES = {'arrow':'ARROW','bullet':'BULLET','throwing weapon':'THROW','shell':'SHELL','grenade shell':'SHELL','kunai':'KUNAI','shuriken':'SHURIKEN','cannon ball':'CANNONBALL'}

def norm_type(t):
    return re.sub(r'\s+', ' ', t.lower()).strip() if t else ''

def parse_head_loc(s):
    if not s: return []
    s = s.lower()
    out = []
    if 'upper' in s or 'top' in s: out.append('HEAD_TOP')
    if 'mid' in s: out.append('HEAD_MID')
    if 'low' in s: out.append('HEAD_LOW')
    return out

def parse_card_loc(s):
    if not s: return None
    s = s.lower()
    for k, v in [('weapon','WEAPON'),('armor','ARMOR'),('shield','SHIELD'),('garment','GARMENT'),
                 ('foot','SHOES'),('shoe','SHOES'),('accessory (right)','ACCESSORY_R'),('accessory(right)','ACCESSORY_R'),
                 ('accessory (left)','ACCESSORY_L'),('accessory(left)','ACCESSORY_L'),('accessory','ACCESSORY'),
                 ('headgear','HEADGEAR'),('helm','HEADGEAR'),('ทุกสล็อต','ANY')]:
        if k in s: return v
    return None

# --- bonus parser -----------------------------------------------------------
# Unconditional lines: "STR + 2", "MaxHP + 10%", "ลด Variable Cast Time 10%" ...
# Refine-conditional lines ("เมื่ออัพเกรดถึงขั้น 7 ...", "ทุก ๆ การอัพเกรด 2 ขั้น ...")
# are kept separately so the stat engine can apply them per slot refine level.
# Set bonuses and skill-specific effects are skipped on purpose.
STAT_ALIASES = {
    'str':'str','agi':'agi','vit':'vit','int':'int','dex':'dex','luk':'luk','all stats':'allStats','all stat':'allStats',
    'atk':'atk','matk':'matk','def':'def','mdef':'mdef','hit':'hit','flee':'flee','crit':'crit','critical':'crit',
    'perfect dodge':'perfectDodge','cri':'crit','aspd':'aspd','maxhp':'maxHp','max hp':'maxHp','mhp':'maxHp','maxsp':'maxSp','max sp':'maxSp','msp':'maxSp',
    'hp':'maxHp','sp':'maxSp',
}
P_BONUS = re.compile(r'(?<![A-Za-z])(' + '|'.join(sorted(map(re.escape, STAT_ALIASES), key=len, reverse=True)) + r')\s*\+\s*(\d+)\s*(%?)', re.I)

# cast time / after-cast delay (reductions are stored as positive numbers)
_CAST = r'(?:Variable\s*Cast\s*Time|(?:ระยะ)?เวลา(?:ใน)?(?:การ)?ร่าย(?:เวทย์|เวทมนตร์|สกิล|คาถา)?(?:แบบแปรผัน)?)'
P_VCT_DOWN = re.compile(r'(?:ลด\s*' + _CAST + r'|' + _CAST + r'\s*ลดลง)\s*(?:ลง(?:อีก)?)?\s*(\d+(?:\.\d+)?)\s*%', re.I)
P_VCT_UP   = re.compile(r'เพิ่ม\s*' + _CAST + r'\s*(?:ขึ้น)?\s*(\d+(?:\.\d+)?)\s*%', re.I)
P_FCT_DOWN = re.compile(r'ลด\s*(?:Fixed\s*Cast\s*Time|ระยะเวลาร่ายแบบคงที่)\s*(?:ลง)?\s*(\d+(?:\.\d+)?)\s*(วินาที|%)', re.I)
_ACD = r'(?:After\s*Cast\s*Delay|(?:สกิล)?(?:Delay|ดีเลย์)(?:\s*หลัง(?:จาก)?ใช้สกิล)?)'
P_ACD_DOWN = re.compile(r'(?:ลด\s*' + _ACD + r'|' + _ACD + r'\s*ลดลง)\s*(?:ลง(?:อีก)?)?\s*(\d+(?:\.\d+)?)\s*%', re.I)
P_ACD_UP   = re.compile(r'เพิ่ม\s*' + _ACD + r'\s*(?:ขึ้น)?\s*(\d+(?:\.\d+)?)\s*%', re.I)

P_COND_MIN  = re.compile(r'(?:เมื่ออัพเกรด(?:ถึง)?ขั้น|อัพเกรดตั้งแต่ขั้น|เมื่อขั้นอัพเกรด(?:ตั้งแต่)?|เมื่อ\s*\+|ที่ระดับ\s*\+|เมื่อตีบวก(?:ถึง)?\s*\+?)\s*(\d+)')
P_COND_EACH = re.compile(r'ทุก\s*ๆ?\s*(?:การ)?(?:อัพเกรด|ตีบวก)\s*(\d+)\s*ขั้น')
P_SKIP = re.compile(r'เซ็ต|เซต|ร่วมกัน|ด้วยกัน|ผลรวม|Global Cooldown|หลังโจมตี|ของสกิล|ให้กับสกิล|สกิล\s*\[|เรียนรู้สกิล', re.I)

def _num(v):
    f = float(v)
    return int(f) if f.is_integer() else f

def _add(out, key, val):
    out[key] = _num((out.get(key, 0) + val))

def parse_bonus_line(line):
    out = {}
    for m in P_BONUS.finditer(line):
        key = STAT_ALIASES[m.group(1).lower()]
        if m.group(3): key += 'Percent'
        _add(out, key, int(m.group(2)))
    if P_SKIP.search(line):
        return out
    for m in P_VCT_DOWN.finditer(line): _add(out, 'variableCastPercent', float(m.group(1)))
    for m in P_VCT_UP.finditer(line):   _add(out, 'variableCastPercent', -float(m.group(1)))
    for m in P_FCT_DOWN.finditer(line):
        _add(out, 'fixedCastPercent' if m.group(2) == '%' else 'fixedCastSeconds', float(m.group(1)))
    for m in P_ACD_DOWN.finditer(line): _add(out, 'afterCastDelayPercent', float(m.group(1)))
    for m in P_ACD_UP.finditer(line):   _add(out, 'afterCastDelayPercent', -float(m.group(1)))
    return out

def parse_bonuses(lines):
    """Return (bonuses, conditional) where conditional = {'refine': [{min, bonuses}], 'perRefine': [{every, bonuses}]}."""
    plain, by_min, by_each = {}, {}, {}
    in_set = False
    for line in lines:
        # "[Set] ..." / "เมื่อสวมใส่ ... ร่วมกัน" starts a set-bonus block that runs until the type line
        if re.search(r'^\s*\[Set\]|เซ็ต|เซต|ร่วมกัน|ด้วยกัน', line):
            in_set = True
            continue  # set bonuses need the other pieces — not counted
        if line.startswith('ประเภท'):
            in_set = False
        if in_set:
            continue
        b = parse_bonus_line(line)
        if not b:
            continue
        m_each = P_COND_EACH.search(line)
        m_min = P_COND_MIN.search(line)
        target = by_each.setdefault(int(m_each.group(1)), {}) if m_each else by_min.setdefault(int(m_min.group(1)), {}) if m_min else plain
        for k, v in b.items(): _add(target, k, v)
    cond = {}
    if by_min: cond['refine'] = [{'min': k, 'bonuses': v} for k, v in sorted(by_min.items())]
    if by_each: cond['perRefine'] = [{'every': k, 'bonuses': v} for k, v in sorted(by_each.items())]
    return plain, cond

# --- costume enchant stones ("STR Stone (Upper)", "ATK Stone (Middle)" ...) ----
# ETC items that slot into a costume piece; position comes from the name or the
# description ("Costume ส่วน Upper", "Slot ของ Upper Costume").
_STONE_POS = {'upper': 'COSTUME_TOP', 'top': 'COSTUME_TOP', 'middle': 'COSTUME_MID', 'mid': 'COSTUME_MID',
              'lower': 'COSTUME_LOW', 'low': 'COSTUME_LOW', 'garment': 'COSTUME_GARMENT', 'robe': 'COSTUME_GARMENT'}
P_STONE_NAME = re.compile(r'stone.*\((upper|middle|lower|garment|top|mid|low|robe)\)', re.I)
P_STONE_DESC = re.compile(r'(?:costume\s*(?:ส่วน)?\s*(upper|middle|lower|garment)|(upper|middle|lower|garment)\s*costume)', re.I)

def costume_stone_location(name, text):
    if not re.search(r'stone|หิน', name, re.I) or not re.search(r'costume|คอสตูม', text, re.I):
        return None
    m = P_STONE_NAME.search(name)
    if m:
        return _STONE_POS.get(m.group(1).lower())
    m = P_STONE_DESC.search(text)
    if m:
        return _STONE_POS.get((m.group(1) or m.group(2)).lower())
    return None

def classify(item_id, typ, head_locs, card_loc):
    """Return (itemType, subType, equipLocations)."""
    t = norm_type(typ)
    if t == 'card' or card_loc and 4000 <= item_id < 5000:
        return 'CARD', 'CARD', []
    if t in WEAPON_TYPES:
        sub = WEAPON_TYPES[t]
        return 'WEAPON', sub, ['WEAPON'] if not sub.endswith('_2H') and sub not in ('BOW','KATAR','INSTRUMENT','WHIP','HUUMA','RIFLE','SHOTGUN','GATLING','GRENADE_LAUNCHER') else ['WEAPON','SHIELD']
    if t in AMMO_TYPES:
        return 'AMMO', AMMO_TYPES[t], ['AMMO']
    if t in ARMOR_TYPES:
        sub = ARMOR_TYPES[t]
        if sub == 'HEADGEAR':
            return 'ARMOR', 'HEADGEAR', head_locs or ['HEAD_TOP']
        if sub == 'COSTUME':
            return 'COSTUME', 'COSTUME', ['COSTUME_' + l[5:] for l in head_locs] if head_locs else (['COSTUME_GARMENT'] if 20500 <= item_id < 20800 else ['COSTUME_TOP'])
        if sub == 'SHADOW':
            return 'SHADOW', 'SHADOW', ['SHADOW']
        if sub == 'ACCESSORY': return 'ARMOR', 'ACCESSORY', ['ACCESSORY_1', 'ACCESSORY_2']
        if sub == 'ACCESSORY_R': return 'ARMOR', 'ACCESSORY', ['ACCESSORY_1']
        if sub == 'ACCESSORY_L': return 'ARMOR', 'ACCESSORY', ['ACCESSORY_2']
        return 'ARMOR', sub, [sub]
    if 'egg' in t: return 'PET_EGG', 'PET_EGG', []
    if 'pet' in t or 'taming' in t: return 'ETC', 'PET', []
    # fall back on ID ranges (official RO layout)
    if 4000 <= item_id < 5000: return 'CARD', 'CARD', []
    if 5000 <= item_id < 6000 or 18500 <= item_id < 20000: return 'ARMOR', 'HEADGEAR', head_locs or ['HEAD_TOP']
    if 20000 <= item_id < 21000: return 'COSTUME', 'COSTUME', ['COSTUME_TOP']
    if 1100 <= item_id < 2000 or 13000 <= item_id < 13500 or 21000 <= item_id < 22000: return 'WEAPON', 'UNKNOWN', ['WEAPON']
    if 2100 <= item_id < 2200: return 'ARMOR', 'SHIELD', ['SHIELD']
    if 2300 <= item_id < 2400 or 15000 <= item_id < 15200: return 'ARMOR', 'ARMOR', ['ARMOR']
    if 2400 <= item_id < 2500 or 22000 <= item_id < 22200: return 'ARMOR', 'SHOES', ['SHOES']
    if 2500 <= item_id < 2600 or 20700 <= item_id < 20900: return 'ARMOR', 'GARMENT', ['GARMENT']
    if 2600 <= item_id < 3000 or 28300 <= item_id < 28700: return 'ARMOR', 'ACCESSORY', ['ACCESSORY_1', 'ACCESSORY_2']
    if 500 <= item_id < 700 or 11500 <= item_id < 12800 or 14500 <= item_id < 14700: return 'CONSUMABLE', 'CONSUMABLE', []
    if 1750 <= item_id < 1800 or 13200 <= item_id < 13300: return 'AMMO', 'UNKNOWN', ['AMMO']
    return 'ETC', 'ETC', []

def main():
    raw = json.load(open(SRC, encoding='utf-8'))
    items, stats = [], collections.Counter()
    for sid, v in raw.items():
        if not sid.isdigit(): continue
        item_id = int(sid)
        lines = [clean(l) for l in v.get('identifiedDescriptionName', []) if isinstance(l, str)]
        text = '\n'.join(lines)
        typ = grab(text, P_TYPE)
        head_locs = parse_head_loc(grab(text, P_HLOC))
        card_loc = parse_card_loc(grab(text, P_CLOC))
        item_type, sub_type, locs = classify(item_id, typ, head_locs, card_loc)
        stone_loc = costume_stone_location(v.get('identifiedDisplayName', ''), text) if item_type == 'ETC' else None
        if stone_loc:
            sub_type, card_loc = 'COSTUME_STONE', stone_loc
        jobs = grab(text, P_JOBS)
        bonuses, cond = parse_bonuses(lines) if item_type in ('WEAPON','ARMOR','CARD','COSTUME','SHADOW') or stone_loc else ({}, {})
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
        }
        items.append(rec)
        stats[item_type] += 1
    items.sort(key=lambda r: r['id'])
    json.dump(items, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'wrote {len(items)} items -> {OUT}')
    for k, c in stats.most_common(): print(f'  {k:12s} {c}')

if __name__ == '__main__':
    main()
