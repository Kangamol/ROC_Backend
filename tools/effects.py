#!/usr/bin/env python3
"""Turn the Thai client description of an item into structured effects.

Output of parse_effects(lines):
    bonuses    {key: number}                       unconditional
    cond       {refine:    [{min, bonuses}],       applies once refine >= min
                perRefine: [{every, bonuses}],     bonuses * floor(refine / every)
                perStat:   [{stat, every, max, bonuses}],  bonuses * floor(baseStat / every)
                statMin:   [{stat, min, refine?, bonuses}], applies once base stat >= min (and refine >= refine)
                level:     [{min?, max?, bonuses}],        applies while min <= base level <= max
                perLevel:  [{every, min?, max?, bonuses}], bonuses * floor(min(baseLv, max) / every), once baseLv >= min
                set:       [{requires: [names], bonuses}]}  all named items / cards must be worn
    "Base STR" / "Base Lv" always mean the character's own base value (what the player
    sets on the status window / level), never the total after item or job bonuses.
    unparsed   [line]   lines that look like effects but nothing was extracted
    parsed     [line]   lines that produced unconditional effects
    conditional[line]   lines that produced effects under a condition (refine / stat / set)

Keys are flat strings so the stat engine can just sum them; targeted effects
embed the target: "physDamage:race:demihuman", "resist:element:neutral",
"skillDamage:Bowling Bash". Reductions (cast time, delay, damage taken,
SP cost) are stored as positive numbers.
"""
import re

# ----------------------------------------------------------------- vocab ----
STAT_ALIASES = {
    'str': 'str', 'agi': 'agi', 'vit': 'vit', 'int': 'int', 'dex': 'dex', 'luk': 'luk',
    'all stats': 'allStats', 'all stat': 'allStats', 'all state': 'allStats', 'all status': 'allStats', 'allstat': 'allStats',
    'atk': 'atk', 'พลังโจมตี': 'atk', 'matk': 'matk', 'def': 'def', 'mdef': 'mdef', 'hit': 'hit', 'flee': 'flee',
    'crit': 'crit', 'cri': 'crit', 'critical': 'crit', 'critical rate': 'crit', 'perfect dodge': 'perfectDodge',
    'critical damage': 'critDamagePercent', 'cri damage': 'critDamagePercent', 'crit damage': 'critDamagePercent',
    'aspd': 'aspd', 'attack speed': 'aspd', 'maxhp': 'maxHp', 'max hp': 'maxHp', 'mhp': 'maxHp', 'maxsp': 'maxSp', 'max sp': 'maxSp', 'msp': 'maxSp',
    'mhp/msp': 'maxHpSp', 'maxhp/maxsp': 'maxHpSp', 'hp': 'maxHp', 'sp': 'maxSp',
}
_STAT_RE = '|'.join(sorted(map(re.escape, STAT_ALIASES), key=len, reverse=True))
# "STR + 2", "MATK +5%", "LUK -3", "+Matk 2%", "INT + 1 / VIT + 1"
P_STAT = re.compile(r'(?<![A-Za-z])(' + _STAT_RE + r')\s*([+\-])\s*(\d+(?:\.\d+)?)\s*(%?)', re.I)
P_STAT_PRE = re.compile(r'(?<![A-Za-z\d])([+\-])\s*(' + _STAT_RE + r')\s*(\d+(?:\.\d+)?)\s*(%?)', re.I)
# "เพิ่ม ASPD 5%", "เพิ่มพลังโจมตีทางกายภาพ 5%", "ASPD เพิ่มขึ้น 5%"
P_STAT_TH = re.compile(r'เพิ่ม\s*(?:ค่า)?\s*(' + _STAT_RE + r')\s*(?:ขึ้น|อีก|ทีละ|ครั้งละ|เพิ่มเติม|\s)*\+?\s*(\d+(?:\.\d+)?)\s*(%?)', re.I)
# "ATK เพิ่มขึ้นทีละ +5", "HIT เพิ่ม 5"
P_STAT_POST = re.compile(r'(?<![A-Za-z])(' + _STAT_RE + r')\s*เพิ่ม(?:ขึ้น|อีก|ทีละ|ครั้งละ|เพิ่มเติม|เท่ากับ|\s)*\+?\s*(\d+(?:\.\d+)?)\s*(%?)', re.I)
P_HPSP_CONTEXT = re.compile(r'ฟื้นฟู|ฟื้น|Recovery|Regen|ใช้\s*SP|SP\s*ที่ใช้|การใช้|สูญเสีย|ดูด|Drain|ปริมาณ', re.I)
# "ATK, MATK + 1" — a list of stats sharing one value
P_STAT_LIST = re.compile(r'(?<![A-Za-z])(' + _STAT_RE + r')\s*,\s*(?=(?:(?:' + _STAT_RE + r')\s*,\s*)*(?:' + _STAT_RE + r')\s*[+\-]\s*\d)', re.I)

RACE = {
    'กึ่งมนุษย์': 'demihuman', 'demi-human': 'demihuman', 'demihuman': 'demihuman', 'demi human': 'demihuman',
    'สัตว์': 'brute', 'brute': 'brute', 'พืช': 'plant', 'plant': 'plant', 'แมลง': 'insect', 'insect': 'insect',
    'ปลา': 'fish', 'fish': 'fish', 'สัตว์น้ำ': 'fish', 'ปีศาจ': 'demon', 'demon': 'demon',
    'อันเดด': 'undead', 'undead': 'undead', 'มังกร': 'dragon', 'dragon': 'dragon',
    'เทพ': 'angel', 'เทวดา': 'angel', 'angel': 'angel', 'ไร้รูปร่าง': 'formless', 'ไร้รูป': 'formless', 'formless': 'formless',
    'player': 'player', 'ผู้เล่น': 'player', 'boss': 'boss', 'บอส': 'boss', 'ทุกเผ่า': 'all', 'ศัตรูทั่วไป': 'normal', 'มอนสเตอร์ธรรมดา': 'normal', 'monster ธรรมดา': 'normal', 'มอนสเตอร์ทั่วไป': 'normal', 'ศัตรูทั้งหมด': 'all', 'ศัตรูทุกชนิด': 'all',
}
ELEMENT = {
    'neutral': 'neutral', 'ไร้ธาตุ': 'neutral', 'water': 'water', 'น้ำ': 'water', 'earth': 'earth', 'ดิน': 'earth',
    'fire': 'fire', 'ไฟ': 'fire', 'wind': 'wind', 'ลม': 'wind', 'poison': 'poison', 'พิษ': 'poison',
    'holy': 'holy', 'ศักดิ์สิทธิ์': 'holy', 'shadow': 'shadow', 'dark': 'shadow', 'มืด': 'shadow',
    'ghost': 'ghost', 'ผี': 'ghost', 'undead': 'undead', 'อันเดด': 'undead', 'ทุกธาตุ': 'all',
}
SIZE = {'เล็ก': 'small', 'small': 'small', 'กลาง': 'medium', 'medium': 'medium', 'ใหญ่': 'large', 'large': 'large', 'ทุกขนาด': 'all'}

def _alt(d): return '|'.join(sorted(map(re.escape, d), key=len, reverse=True))
P_RACE = re.compile(r'(?:เผ่า|ประเภท|race|จาก|ต่อ|ของ|โจมตี|มอนสเตอร์)?\s*(' + _alt(RACE) + r')(?![A-Za-z])', re.I)
P_ELEMENT = re.compile(r'ธาตุ\s*(?:\()?\s*(' + _alt(ELEMENT) + r')(?![A-Za-z])', re.I)
P_SIZE = re.compile(r'(?:(?:ขนาด|size)\s*(' + _alt(SIZE) + r')|(ทุกขนาด))(?![A-Za-z])', re.I)
P_SKILL = re.compile(r'(?:สกิล|skill)\s*\[?\s*([A-Z][A-Za-z\'\-\. ]+?)\s*\]?\s*(?=\+|\d|Lv|ลง|เพิ่ม|ลด|,|$|ขึ้น|ที่)', re.I)
P_PCT = re.compile(r'([+\-]?\s*\d+(?:\.\d+)?)\s*%')
P_NUM = re.compile(r'(\d+(?:\.\d+)?)')

# cast / delay ----------------------------------------------------------------
_VCT = r'(?:Vari?able\s*Cast(?:ing)?\s*Time|Virable\s*Cast\s*Time|VCT|(?:ระยะ)?เวลา(?:ใน)?(?:การ)?ร่าย(?:เวทย์|เวทมนตร์|สกิล|คาถา)?(?:แบบ)?(?:แปรผัน|ผันแปร)?)'
P_VCT_DOWN = re.compile(r'(?:ลด\s*' + _VCT + r'|' + _VCT + r'\s*ลดลง)\s*(?:ลง|เพิ่มเติม|เพิ่มอีก|อีก|\s)*(\d+(?:\.\d+)?)\s*%', re.I)
P_VCT_UP = re.compile(r'เพิ่ม\s*' + _VCT + r'\s*(?:ขึ้น)?\s*(\d+(?:\.\d+)?)\s*%', re.I)
P_FCT_DOWN = re.compile(r'ลด\s*(?:Fixed\s*Cast(?:ing)?\s*Time|FCT|ระยะเวลาร่ายแบบคงที่)\s*(?:ลง)?\s*(?:อีก)?\s*(\d+(?:\.\d+)?)\s*(วินาที|%)', re.I)
_ACD = r'(?:After\s*Cast\s*Delay|ACD|(?:สกิล)?\s*(?:Delay|ดีเลย์)(?:\s*หลัง(?:จาก)?(?:การ)?ใช้สกิล)?)'
P_ACD_DOWN = re.compile(r'(?:ลด\s*' + _ACD + r'|' + _ACD + r'\s*ลดลง)\s*(?:ลง|เพิ่มเติม|เพิ่มอีก|อีก|\s)*(\d+(?:\.\d+)?)\s*%', re.I)
P_ACD_UP = re.compile(r'เพิ่ม\s*' + _ACD + r'\s*(?:ขึ้น)?\s*(\d+(?:\.\d+)?)\s*%', re.I)
# "ลดระยะเวลาในการร่ายเวทย์คิดเป็น% ตามการอั[พป]เกรดหมวก"  → 1% per refine
P_RECOV = re.compile(r'(ลด|เพิ่ม)?\s*(?:อัตรา|ความเร็ว)?(?:ใน)?(?:การ)?ฟื้น(?:ฟู|ค่า)?\s*(HP|SP)(?:\s*ตามธรรมชาติ)?\s*(?:ลง|ขึ้น|อีก|\s)*(\d+(?:\.\d+)?)\s*%|(HP|SP)\s*Recovery\s*(?:Rate)?\s*\+?\s*(\d+(?:\.\d+)?)\s*%', re.I)
P_VCT_PER_REFINE = re.compile(r'ลด\s*' + _VCT + r'.*(?:คิดเป็น|เท่ากับ)\s*%?\s*ตาม(?:การ|ระดับ)?(?:อั[พป]เกรด|ตีบวก|Refine)', re.I)

# conditions ------------------------------------------------------------------
P_COND_MIN = re.compile(r'(?:(?:หาก|เมื่อ)?\s*(?:Item\s*)?อั[พป]เกรดตั้งแต่ระดับ\s*\+?|ตั้งแต่ขั้นอั[พป]เกรดมากกว่า|ทุก\s*ๆ?\s*การอั[พป]เกรดที่มากกว่าระดับ\s*\+?|เมื่ออั[พป]เกรด(?:ถึง)?(?:ขั้น|ตั้งแต่)?|อั[พป]เกรดตั้งแต่(?:ขั้น)?|เมื่อขั้นอั[พป]เกรด(?:ตั้งแต่)?|เมื่อ(?:ตีบวก)?(?:ตั้งแต่)?\s*\+|ที่ระดับ\s*\+|ถ้า\S*ตีบวกตั้งแต่\s*\+?|ตีบวก(?:ถึง|ตั้งแต่)\s*\+?)\s*\+?\s*(\d+)')
P_COND_EACH = re.compile(r'ทุก\s*ๆ?\s*(?:การ)?(?:อั[พป]เกรด|ตีบวก)\s*(\d+)\s*ขั้น|ต่อ(?:ระดับ|ขั้น)?(?:การ)?(?:อั[พป]เกรด|ตีบวก)(?:\s*(?:ทุก\s*ๆ?)?\s*(\d+)\s*(?:Lv\.?|ขั้น|ระดับ)?)?')
P_COND_STAT = re.compile(r'ทุก\s*ๆ?\s*(?:Base\s*)?(\d+)?\s*(?:Base\s*)?(STR|AGI|VIT|INT|DEX|LUK)\s*(\d+)?', re.I)
P_STAT_CAP = re.compile(r'Base\s*(STR|AGI|VIT|INT|DEX|LUK)\s*สูงสุด.*?(\d+)', re.I)
# "เมื่อ Base STR ตั้งแต่ 90 ขึ้นไป", "หาก Base AGI ตั้งแต่108 ขึ้นไป", "เมื่อ Base VIT 99 ขึ้นไป", "เมื่อ Base INT 90,"
P_COND_STATMIN = re.compile(r'(?:เมื่อ|หาก|ถ้า)?\s*Base\s*(STR|AGI|VIT|INT|DEX|LUK)\s*(ตั้งแต่|มากกว่า|>=|≥)?\s*(\d+)\s*(ขึ้นไป|ขี้นไป)?', re.I)
_BLV = r'(?:Base\s*(?:Level|Lv|LV)\s*\.?|BaseLv\s*\.?|BaseLV|BaseLevel|ตัวละครเลเวล|เลเวลตัวละคร|ตัวละครมี\s*Lv\.?)'
# "ทุก ๆ 2 Base Level", "ทุกๆ 10 BaseLv.", "ทุก ๆ การเพิ่ม 2 Base Level"
P_PER_LEVEL_A = re.compile(r'ทุก\s*ๆ?\s*(?:การเพิ่ม(?:ขึ้น)?(?:ของ)?\s*)?(\d+)\s*' + _BLV, re.I)
# "ทุกๆ Base Level 2", "ทุก ๆ Base Lv.1", "ทุกการเพิ่มขึ้นของ Base Lv. 10 ขั้น", "ทุกครั้งที่ BaseLv เพิ่มขึ้น 10 เลเวล"
P_PER_LEVEL_B = re.compile(r'ทุก\s*ๆ?\s*(?:ครั้งที่|การเพิ่มขึ้นของ)?\s*' + _BLV + r'\s*(?:เพิ่มขึ้น)?\s*(\d+)\s*(?:ขั้น|เลเวล|Lv\.?)?', re.I)
# "... 1% ต่อ BaseLevel ตัวละคร"
P_PER_LEVEL_C = re.compile(r'ต่อ\s*' + _BLV + r'(?:\s*ตัวละคร)?', re.I)
# "(ปริมาณการเพิ่มขึ้นจะสูงสุดจนถึง Base Lv. 90)", "(สูงสุดจนถึง Base Lv.200)", "(Max.Lv 99)"
P_LEVEL_CAP = re.compile(r'สูงสุด.*?' + _BLV + r'\s*(\d+)|Max\.?\s*Lv\.?\s*(\d+)', re.I)
# "หาก Base Lv.80 ขึ้นไป", "เมื่อตัวละครเลเวลมากกว่า 20 :", "หากตัวละครมี Lv. ตั้งแต่ 70 ขึ้นไป :", "เมื่อ Base Lv.88"
P_LEVEL_MIN = re.compile(r'(?:เมื่อ|หาก|ถ้า|ในกรณีที่)?\s*' + _BLV + r'\s*(ตั้งแต่|มากกว่า|>=|≥)?\s*(\d+)\s*(ขึ้นไป)?', re.I)
# "Base Lv 50 ~ 99"
P_LEVEL_RANGE = re.compile(_BLV + r'\s*(\d+)\s*[~\-–]\s*(\d+)', re.I)
# "เมื่อเลเวลตัวละครน้อยกว่า 100 :", "ในกรณีที่ Base Level ต่ำกว่า Level79"
P_LEVEL_MAX = re.compile(r'(?:เมื่อ|หาก|ถ้า|ในกรณีที่)?\s*' + _BLV + r'\s*(?:น้อยกว่า|ต่ำกว่า)\s*(?:Level\s*)?(\d+)', re.I)
# "Max HP เพิ่มขึ้น 3 เท่าของ Base Lv", "Max SP เพิ่มขึ้น 1/2 เท่าของ Base Lv", "เท่ากับ 5 เท่าของ Base Level"
P_TIMES_LEVEL = re.compile(r'(\d+)(?:\s*/\s*(\d+))?\s*เท่า(?:ของ|ตัว)\s*' + _BLV, re.I)
# "เพิ่ม DEF เท่ากับ Base STR" → +1 per point of base STR
P_EQUALS_STAT = re.compile(r'เพิ่ม\s*(?:ค่า)?\s*(' + _STAT_RE + r')\s*(?:ขึ้น)?\s*เท่ากับ\s*(?:ค่า)?\s*Base\s*(STR|AGI|VIT|INT|DEX|LUK)', re.I)
_BLV_LOOSE = r'(?:' + _BLV + r'|เลเวล(?!\s*ที่ต้องการ))'
P_LEVEL_MIN_LOOSE = re.compile(r'(?:เมื่อ|หาก|ถ้า|ในกรณีที่)\s*' + _BLV_LOOSE + r'\s*(ตั้งแต่|มากกว่า)\s*(\d+)\s*(ขึ้นไป)?', re.I)
P_LEVEL_MAX_LOOSE = re.compile(r'(?:เมื่อ|หาก|ถ้า|ในกรณีที่)\s*' + _BLV_LOOSE + r'\s*(?:น้อยกว่า|ต่ำกว่า)\s*(?:Level\s*)?(\d+)', re.I)
# "(เมื่ออั[พป]เกรดตั้งแต่ขั้น 7 ขึ้นไป เพิ่มอีก 3%)", "(หากอั[พป]เกรดถึงขั้น 7 เพิ่มอีก 10)" nested inside a stat-threshold line
P_NESTED_REFINE = re.compile(r'\(\s*(?:เมื่อ|หาก)?\s*อั[พป]เกรด(?:ตั้งแต่|ถึง)?\s*(?:ขั้น|ระดับ)?\s*\+?\s*(\d+)\s*(?:ขึ้นไป)?\s*(.*?)\)')
P_SET = re.compile(r'(?:(?:เมื่อ|หาก|ถ้า)\s*(?:สวม)?(?:ใส่|ติดตั้ง)\s*(?:ร่วมกัน)?\s*(?:กับ|คู่กับ|ร่วมกับ|รวมกันกับ|รวมกับ)?|(?:สวม)?(?:ใส่|ติดตั้ง|ใช้)\s*(?:ร่วมกัน)?\s*(?:กับ|คู่กับ|ร่วมกับ|รวมกันกับ|รวมกับ)|\[Set\])\s*(.+?)\s*(?:ร่วมกัน|ด้วยกัน|ทั้งหมดด้วยกัน|ทั้งหมด|,\s*$|$|(?=\s*(?:ลด|เพิ่ม|[A-Z][A-Za-z]+\s*[+\-]\s*\d)))', re.I)
P_SET_TRIGGER = re.compile(r'\[Set\]|ร่วมกัน|ด้วยกัน|ร่วมกับ|รวมกันกับ|รวมกับ|คู่กับ|(?:เมื่อ|หาก|ถ้า)\s*(?:สวม)?(?:ใส่|ติดตั้ง)\s+(?=[A-Z\[\"])', re.I)

# lines that carry no stat effect (so they are not reported as unparsed)
P_NOISE = re.compile(r'แลกเปลี่ยน|ไอเทมเช่า|Item เช่า|ระยะเวลาเช่า|ไม่สามารถ|ไม่มีวัน|ไม่เสียหาย|Ban Guild|WoE|PvP|PVP|Raid|Enchant Stone Box|Stone Box|<NAVI>|^[_―\-\s]*$|หมายเหตุ|ระวัง|Sillit|คลังเก็บ|ดูกลมกลืน|\*\*\*|Zodiac|มีโอกาส|โอกาส|สุ่ม|Autospell|Auto Spell|เมื่อฆ่า|เมื่อกำจัด|เมื่อสังหาร|ทุกครั้งที่|ทุก\s*ๆ?\s*\d+\s*วินาที|ทุก\s*\d+\s*วินาที|ถอด|เท่ากับ\s*(?:\d+\s*เท่าของ\s*)?Base|ขึ้นอยู่กับ\s*Base|ตาม\s*Base|ระดับ Refine\*', re.I)
P_SKIP_EFFECT = re.compile(r'Global Cooldown|หลังโจมตี|ผลรวม|ค่าตีบวกของทั้งเซ็ต|ของเซ็ต|ของเซต|อั[พป]เกรดรวมกัน|เมื่อช่อง\s*Enchant', re.I)


def _num(v):
    f = float(v)
    return int(f) if f.is_integer() else f

def _add(out, key, val):
    out[key] = _num(out.get(key, 0) + val)

def _kind(line):
    """physical / magic / both for damage-type lines."""
    magic = re.search(r'เวทมนตร์|เวทย์|magic', line, re.I)
    # "โจมตี" alone is generic; only count it as physical when no magic wording is present
    phys = re.search(r'กายภาพ|physical', line, re.I) or (not magic and re.search(r'โจมตี', line))
    if magic and phys: return 'both'
    if magic: return 'magic'
    return 'phys'

def _target(line):
    m = P_SKILL.search(line)
    if m and not re.search(r'สามารถใช้', line):
        return 'skill', m.group(1).strip()
    m = P_ELEMENT.search(line)
    if m: return 'element', ELEMENT[m.group(1).lower()]
    m = P_SIZE.search(line)
    if m: return 'size', SIZE[(m.group(1) or m.group(2)).lower()]
    if re.search(r'\bboss\b|บอส', line, re.I): return 'race', 'boss'
    m = P_RACE.search(line)
    if m: return 'race', RACE[m.group(1).lower()]
    if re.search(r'ระยะไกล', line): return 'range', 'ranged'
    if re.search(r'ระยะประชิด|ระยะใกล้', line): return 'range', 'melee'
    if re.search(r'ทุกธาตุ', line): return 'element', 'all'
    if re.search(r'ศัตรู|เป้าหมาย|มอนสเตอร์', line): return 'race', 'all'
    return None, None

def _targets(line):
    """All targets named in one line, e.g. "เผ่า Demon, Undead และธาตุ Undead, Shadow" →
    [race:demon, race:undead, element:undead, element:shadow]. Falls back to _target()."""
    out = []
    if P_SKILL.search(line) and not re.search(r'สามารถใช้', line):
        # "สกิล A, B และ C" → one entry per skill
        m = re.search(r'(?:สกิล|skill)\s*(.+?)\s*(?=\d+(?:\.\d+)?\s*%|ลง\s*\d|เพิ่ม|ลด|$)', line, re.I)
        names = re.split(r',|และ|หรือ|/', m.group(1)) if m else []
        for n in names:
            n = re.sub(r'\[|\]|Lv\.?\s*\d+', '', n).strip(' .')
            if re.match(r'^[A-Z][A-Za-z\'\-\. ]+$', n): out.append(('skill', n))
        if out: return out
    rest = line
    for m in P_ELEMENT.finditer(line):
        out.append(('element', ELEMENT[m.group(1).lower()]))
    # "ธาตุ Undead ธาตุ Shadow" / "ธาตุ Fire, Water" — elements listed after one "ธาตุ"
    m = re.search(r'ธาตุ\s*((?:(?:' + _alt(ELEMENT) + r')\s*[,/และ]*\s*)+)', line, re.I)
    if m:
        for e in re.findall(_alt(ELEMENT), m.group(1), re.I):
            t = ('element', ELEMENT[e.lower()])
            if t not in out: out.append(t)
        rest = line.replace(m.group(0), ' ')
    for m in P_SIZE.finditer(rest):
        t = ('size', SIZE[(m.group(1) or m.group(2)).lower()])
        if t not in out: out.append(t)
    m = re.search(r'ขนาด\s*((?:(?:' + _alt(SIZE) + r')\s*[,/และ]*\s*)+)', rest, re.I)
    if m:
        for e in re.findall(_alt(SIZE), m.group(1), re.I):
            t = ('size', SIZE[e.lower()])
            if t not in out: out.append(t)
    if re.search(r'\bboss\b|บอส', rest, re.I): out.append(('race', 'boss'))
    for m in P_RACE.finditer(rest):
        t = ('race', RACE[m.group(1).lower()])
        if t not in out and t[1] != 'boss': out.append(t)
    if not out:
        k, v = _target(line)
        if k: out.append((k, v))
    return out

def _pct(line):
    m = P_PCT.search(line)
    return float(m.group(1).replace(' ', '')) if m else None


def parse_line(line):
    """Extract effects from one line → dict of key: value (may be empty)."""
    out = {}
    text = line.strip()
    if not text or P_SKIP_EFFECT.search(text) or P_NOISE.search(text):
        return out

    # --- plain stats "X + N" / "+X N" / "เพิ่ม X N" -----------------------
    consumed = []
    def overlaps(m): return any(a < m.end() and m.start() < b for a, b in consumed)
    for m in P_STAT.finditer(text):
        # "ใช้ SP - 20", "เสีย HP 100": a cost, not a max-HP/SP bonus
        if m.group(1).lower() in ('hp', 'sp') and re.search(r'(?:ใช้|เสีย|สูญเสีย|ฟื้นฟู|ดูด)\s*$', text[max(0, m.start() - 12):m.start()]): continue
        key = STAT_ALIASES[m.group(1).lower()]
        val = float(m.group(3)) * (-1 if m.group(2) == '-' else 1)
        if m.group(4): key = key + 'Percent' if not key.endswith('Percent') else key
        if key == 'maxHpSp': _add(out, 'maxHp', val); _add(out, 'maxSp', val)
        elif key == 'maxHpSpPercent': _add(out, 'maxHpPercent', val); _add(out, 'maxSpPercent', val)
        else: _add(out, key, val)
        consumed.append(m.span())
    for m in P_STAT_PRE.finditer(text):
        if overlaps(m): continue
        key = STAT_ALIASES[m.group(2).lower()]
        val = float(m.group(3)) * (-1 if m.group(1) == '-' else 1)
        if m.group(4) and not key.endswith('Percent'): key += 'Percent'
        _add(out, key, val); consumed.append(m.span())
    for m in P_STAT_TH.finditer(text):
        if overlaps(m): continue
        if re.search(r'ต่อ|เผ่า|ธาตุ|ขนาด|ศัตรู|Player|Boss|สกิล', text[m.end():m.end() + 40], re.I): continue  # targeted, handled below
        key = STAT_ALIASES[m.group(1).lower()]
        if m.group(3) and not key.endswith('Percent'): key += 'Percent'
        _add(out, key, float(m.group(2))); consumed.append(m.span())
    for m in P_STAT_POST.finditer(text):
        if overlaps(m): continue
        key = STAT_ALIASES[m.group(1).lower()]
        if key in ('maxHp', 'maxSp', 'maxHpSp') and P_HPSP_CONTEXT.search(text): continue  # "อัตราการฟื้นฟู SP เพิ่มขึ้น 9%", "ใช้ SP เพิ่มขึ้น 50"
        if m.group(3) and not key.endswith('Percent'): key += 'Percent'
        _add(out, key, float(m.group(2))); consumed.append(m.span())
    # "ATK, MATK + 1": every stat in the list takes the value of the last one
    for m in P_STAT_LIST.finditer(text):
        if overlaps(m): continue
        nxt = P_STAT.search(text, m.end())
        if not nxt or re.search(r'[^\sA-Za-z,/]', text[m.end():nxt.start()]): continue
        key = STAT_ALIASES[m.group(1).lower()]
        val = float(nxt.group(3)) * (-1 if nxt.group(2) == '-' else 1)
        if nxt.group(4): key = key + 'Percent' if not key.endswith('Percent') else key
        _add(out, key, val); consumed.append(m.span())

    # --- cast / delay --------------------------------------------------------
    if re.search(r'ของสกิล|ให้กับสกิล|สกิล\s*\[', text):
        kind, name = _target(text)
        if kind == 'skill':
            pct = _pct(text)
            if pct is not None:
                if P_VCT_DOWN.search(text) or re.search(r'VCT|ร่าย', text): _add(out, f'skillVct:{name}', pct)
                elif P_ACD_DOWN.search(text) or re.search(r'delay|ดีเลย์', text, re.I): _add(out, f'skillDelay:{name}', pct)
    else:
        for m in P_VCT_DOWN.finditer(text): _add(out, 'variableCastPercent', float(m.group(1)))
        for m in P_VCT_UP.finditer(text): _add(out, 'variableCastPercent', -float(m.group(1)))
        for m in P_FCT_DOWN.finditer(text):
            _add(out, 'fixedCastPercent' if m.group(2) == '%' else 'fixedCastSeconds', float(m.group(1)))
        for m in P_ACD_DOWN.finditer(text): _add(out, 'afterCastDelayPercent', float(m.group(1)))
        for m in P_ACD_UP.finditer(text): _add(out, 'afterCastDelayPercent', -float(m.group(1)))
        if P_VCT_PER_REFINE.search(text): _add(out, 'variableCastPercent:perRefine', 1)

    # --- SP cost / recovery / exp --------------------------------------------
    # "ลดอัตราการฟื้นฟู SP 100%", "เพิ่มความเร็วในการฟื้นฟู HP 10%", "HP Recovery + 10%" — each with its own number and sign
    for m in P_RECOV.finditer(text):
        which = (m.group(2) or m.group(4)).upper()
        val = float(m.group(3) or m.group(5)) * (-1 if m.group(1) == 'ลด' else 1)
        _add(out, 'hpRecoveryPercent' if which == 'HP' else 'spRecoveryPercent', val)
    pct = _pct(text)
    if pct is not None and ('hpRecoveryPercent' in out or 'spRecoveryPercent' in out):
        pct = None  # handled above; keep the generic branches from re-reading the same number
    if pct is not None:
        if re.search(r'SP\s*(?:ที่ใช้|ในการ(?:ร่าย|ใช้))|การใช้\s*SP|ใช้\s*SP', text) and re.search(r'ลด', text): _add(out, 'spCostPercent', pct)
        elif re.search(r'SP\s*(?:ที่ใช้|ในการ(?:ร่าย|ใช้))|การใช้\s*SP|ใช้\s*SP', text) and re.search(r'เพิ่ม|เสีย', text): _add(out, 'spCostPercent', -pct)
        elif re.search(r'ฟื้นฟู\s*HP.*ตามธรรมชาติ|(?:ความเร็ว|อัตรา)(?:ใน)?การฟื้น(?:ฟู)?\s*HP|HP\s*Recovery', text, re.I): _add(out, 'hpRecoveryPercent', pct)
        elif re.search(r'ฟื้นฟู\s*SP.*ตามธรรมชาติ|(?:ความเร็ว|อัตรา)(?:ใน)?การฟื้น(?:ฟู|ค่า)?\s*SP|SP\s*Recovery', text, re.I): _add(out, 'spRecoveryPercent', pct)
        elif re.search(r'ปริมาณการฟื้นฟูของ\s*Skill|พลังฮีล|Heal(?:ing)?\s*(?:Power|Effect)|ฟื้นฟู.*ที่ตนเองใช้|ปริมาณการรักษา|ให้กับ\s*Heal|ค่า\s*Heal|สกิลประเภท\s*Heal|Heal\s*แรงขึ้น', text, re.I): _add(out, 'healPowerPercent', pct)
        elif re.search(r'ประสิทธิภาพการฟื้นฟู|การฟื้นฟูที่ได้รับ|ไอเท็มฟื้นฟู|ไอเทมฟื้นฟู', text): _add(out, 'healReceivedPercent', pct)
        elif re.search(r'EXP|ค่าประสบการณ์', text, re.I):
            kind, tgt = _target(text)
            _add(out, f'exp:{kind}:{tgt}' if kind == 'race' and tgt != 'all' else 'expPercent', pct)

    # --- damage / resist / ignore def (targeted) -----------------------------
    if pct is not None and not out.get('variableCastPercent') and not out.get('afterCastDelayPercent') and not re.search(r'EXP|ค่าประสบการณ์', text, re.I):
        targets = _targets(text)
        kind, tgt = targets[0] if targets else (None, None)
        dk = _kind(text)
        is_resist = re.search(r'ที่ได้รับ|ได้รับจาก|ความเสียหายจาก|ทนทาน|ต้านทาน|ลด\s*Damage\s*(?:จาก|ที่)|Damage\s*ที่ได้รับ|ลดค่าความเสียหาย|ลดความเสียหาย|ลดพลังโจมตีจาก|ป้องกันการโจมตี|ลดดาเมจ', text)
        is_ignore = re.search(r'เพิกเฉย|ไม่สนใจ|ลดค่าพลังป้องกัน|ลดพลังป้องกัน|ทะลุ(?:ทะลวง)?พลังป้องกัน|Ignore', text, re.I)
        is_dmg = re.search(r'เพิ่ม.*(?:Damage|ดาเมจ|ความเสียหาย|ความแรง|ความรุนแรง|พลังโจมตี)|โจมตี.*แรงขึ้น|(?:Damage|ดาเมจ|ความเสียหาย|พลังโจมตี).*เพิ่มขึ้น|(?:Damage|ความเสียหาย)\s*\+', text, re.I)
        if is_ignore and re.search(r'ป้องกัน|def', text, re.I):
            for k2, t2 in (targets or [('race', 'all')]):
                if dk in ('phys', 'both'): _add(out, f'ignoreDef:{k2}:{t2}', pct)
                if dk in ('magic', 'both'): _add(out, f'ignoreMdef:{k2}:{t2}', pct)
        elif is_resist and 'critDamagePercent' in out:
            pass  # "ความเสียหายจาก Critical Damage เพิ่มขึ้น 20%"
        elif is_resist:
            if re.search(r'ระยะไกล', text): _add(out, 'resist:range:ranged', pct)
            elif targets:
                for k2, t2 in targets: _add(out, f'resist:{k2}:{t2}', pct)
            elif re.search(r'ศัตรู|มอนสเตอร์|ทุกชนิด|ทั้งหมด|Damage', text): _add(out, 'resist:race:all', pct)
        elif is_dmg and 'critDamagePercent' not in out:
            if re.search(r'Critical', text, re.I) and not kind: _add(out, 'critDamagePercent', pct)
            elif kind == 'skill':
                for _, name in targets: _add(out, f'skillDamage:{name}', pct)
            elif kind == 'range': _add(out, 'rangedDamagePercent' if tgt == 'ranged' else 'meleeDamagePercent', pct)
            elif kind:
                for k2, t2 in targets:
                    if k2 == 'range': continue
                    if dk in ('phys', 'both'): _add(out, f'physDamage:{k2}:{t2}', pct)
                    if dk in ('magic', 'both'): _add(out, f'magicDamage:{k2}:{t2}', pct)
            elif re.search(r'ทางกายภาพ|physical', text, re.I) and not re.search(r'เวทมนตร์', text): _add(out, 'atkPercent', pct)
            elif re.search(r'เวทมนตร์|magic', text, re.I): _add(out, 'matkPercent', pct)

    # --- "โจมตีโดยไม่สนใจค่า MDEF ของศัตรู" — full ignore, no number in the text ---
    if pct is None and not out:
        m = re.search(r'(?:ไม่สนใจ|เพิกเฉยต่อ|ทะลุ)\s*(?:ค่า)?\s*(?:พลังป้องกันทาง)?\s*(MDEF|DEF|เวทมนตร์|กายภาพ)', text, re.I)
        if m and not re.search(r'\d', text):
            k2, t2 = _target(text)
            if not k2: k2, t2 = 'race', 'all'
            kind = 'ignoreMdef' if m.group(1).upper() in ('MDEF', 'เวทมนตร์') else 'ignoreDef'
            _add(out, f'{kind}:{k2}:{t2}', 100)

    # --- granted skill "สามารถใช้ [X] Lv.N ได้" -------------------------------
    m = re.search(r'สามารถใช้\s*(?:สกิล)?\s*\[?([A-Z][A-Za-z\'\-\. ]+?)\]?\s*Lv\.?\s*(\d+)', text)
    if m: out[f'skill:{m.group(1).strip()}'] = int(m.group(2))

    # --- status resistance "ป้องกันอาการ Curse 10%" ---------------------------
    m = re.search(r'(?:ป้องกัน|ต้านทาน)(?:อาการ|สถานะ)?\s*\[?([A-Za-z ]+?)\]?\s*\+?\s*(\d+(?:\.\d+)?)\s*%', text)
    if m and 'resist:race:all' not in out: _add(out, f'statusResist:{m.group(1).strip().lower()}', float(m.group(2)))

    return out


def _norm_name(s):
    s = re.sub(r'\[\d+\]', '', s)
    return re.sub(r'[\s\'\-\.]', '', s).lower()

def _set_names(cond_line):
    m = P_SET.search(cond_line)
    if not m: return []
    raw = m.group(1)
    raw = re.split(r'\s+(?:ลด|เพิ่ม|จะ|ATK|MATK|STR|AGI|VIT|INT|DEX|LUK|MDEF|DEF|HIT|FLEE|ASPD|MaxHP|MHP|MaxSP)\b', raw)[0]
    names = [n.strip(' ,.') for n in re.split(r',|และ|/', raw)]
    names = [n for n in names if n and not re.search(r'Lv\.?\s*\d|เมื่อ|ถึง', n) and re.search(r'[A-Za-z]', n)]
    return names


def _cond_statmin(line):
    """('statmin', stat, min) for "เมื่อ Base STR ตั้งแต่ 90 ขึ้นไป" style lines, else None."""
    if re.search(r'สูงสุด|รวมกัน|เท่ากับ|ตาม\s*Base|ยิ่ง\s*Base', line): return None, None
    m = P_COND_STATMIN.search(line)
    if not m: return None, None
    if not (m.group(2) or m.group(4) or re.match(r'\s*,', line[m.end():])): return None, None
    return ('statmin', m.group(1).lower(), int(m.group(3))), m


def _cond_level(line):
    """Base-level conditions. Returns (cond, spans) where cond is
    ('perlevel', every, min, max) or ('level', min, max), spans = text ranges to remove before parsing effects."""
    spans = []
    every = lo = hi = None
    for pat in (P_PER_LEVEL_A, P_PER_LEVEL_B):
        m = pat.search(line)
        if m:
            every = int(m.group(1)); spans.append(m.span()); break
    if every is None:
        m = P_PER_LEVEL_C.search(line)
        if m: every = 1; spans.append(m.span())
    if every is None:
        m = P_TIMES_LEVEL.search(line)
        if m:
            # keep the multiplier as the effect's number: "Max HP เพิ่มขึ้น 3 เท่าของ Base Lv" → "Max HP เพิ่มขึ้น 3"
            every = int(m.group(2) or 1)
            line = line[:m.start()] + m.group(1) + ' ' * (len(m.group(0)) - len(m.group(1))) + line[m.end():]
            spans.append((m.start() + len(m.group(1)), m.end()))
    m = P_LEVEL_CAP.search(line)
    if m:
        hi = int(m.group(1) or m.group(2))
        # drop the whole parenthetical if the cap sits in one
        a, b = m.span()
        if a > 0 and line.rfind('(', 0, a) >= 0 and line.find(')', b) >= 0:
            a, b = line.rfind('(', 0, a), line.find(')', b) + 1
        spans.append((a, b))
    m = P_LEVEL_RANGE.search(line)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2)); spans.append(m.span())
    else:
        m = P_LEVEL_MAX.search(line) or P_LEVEL_MAX_LOOSE.search(line)
        if m:
            hi = int(m.group(1)) - 1; spans.append(m.span())
        else:
            for m in P_LEVEL_MIN.finditer(line):
                if any(a <= m.start() < b for a, b in spans): continue
                bare = not (m.group(1) or m.group(3))
                if bare and not re.match(r'\s*(?:,|:|$|จะ|ได้รับ)', line[m.end():]): continue
                lo = int(m.group(2)); spans.append(m.span()); break
            if lo is None:
                m = P_LEVEL_MIN_LOOSE.search(line)
                if m: lo = int(m.group(2)); spans.append(m.span())
    if every is not None: return ('perlevel', every, lo, hi), spans, line
    if lo is not None or hi is not None: return ('level', lo, hi), spans, line
    return None, spans, line


def _strip(line, spans):
    out = line
    for a, b in sorted(spans, reverse=True): out = out[:a] + ' ' + out[b:]
    return re.sub(r'^\s*[:,\.]\s*', '', out).strip()


def parse_effects(lines):
    plain = {}
    buckets = {}           # (kind, params..., gate) -> bonuses ; gate = (refineMin|None, requires|None)
    unparsed, parsed, conditional = [], [], []
    active = None          # current block condition: (kind, params..., gate)
    active_block = False   # True while the header's block continues on following lines

    def target_for(cond):
        if cond is None: return plain
        return buckets.setdefault(cond, {})

    def with_gate(cond, gate):
        return cond + (gate,)

    expanded = []
    for raw in lines:
        ms = list(P_COND_MIN.finditer(raw))
        if len(ms) > 1 and all(re.search(r'\d\s*%|[+\-]\s*\d', raw[a.end():(b.start() if b else len(raw))]) for a, b in zip(ms, ms[1:] + [None])):
            cuts = [0] + [m.start() for m in ms[1:]] + [len(raw)]
            expanded.extend(raw[a:b].strip(' ,') for a, b in zip(cuts, cuts[1:]))
        else:
            expanded.append(raw)
    for raw in expanded:
        line = raw.strip()
        if not line or re.match(r'^[_―\-=\s]+$', line):
            active = None; active_block = False
            continue
        if re.match(r'^(ประเภท|ตำแหน่ง|น้ำหนัก|เลเวล|Lv|อาชีพ|ใช้กับ|ใช้สำหรับ|ธาตุ|ใส่กับ|ติดตั้ง|ต้องการ)', line):
            active = None; active_block = False
            continue

        # ---- detect a condition on this line ----
        cond = None
        body = line           # the part of the line that carries the effects
        prefix = ''           # unconditional text before an inline condition ("FLEE + 10, เมื่อ Base VIT 99 ขึ้นไป FLEE + 10")
        nested = None         # (refine_min, text) from "(เมื่ออั[พป]เกรดตั้งแต่ขั้น 7 ขึ้นไป เพิ่มอีก 3%)"
        m_set = P_SET.search(line) if P_SET_TRIGGER.search(line) else None
        m_stat = P_COND_STAT.search(line)
        m_each = P_COND_EACH.search(line)
        m_min = P_COND_MIN.search(line)
        c_statmin, m_statmin = _cond_statmin(line)
        c_level, level_spans, level_line = _cond_level(line)
        m_eq = P_EQUALS_STAT.search(line)
        if m_set:
            names = _set_names(line)
            cond = ('set', tuple(names)) if names else ('skip',)
        elif m_stat and (m_stat.group(1) or m_stat.group(3)) and not (c_statmin and m_statmin.start() < m_stat.start()):
            every = int(m_stat.group(1) or m_stat.group(3))
            cond = ('stat', m_stat.group(2).lower(), every, None)
        elif c_statmin:
            cond = c_statmin
            prefix, body = line[:m_statmin.start()], line[m_statmin.end():]
            m_n = P_NESTED_REFINE.search(body)
            if m_n:
                nested = (int(m_n.group(1)), m_n.group(2))
                body = body[:m_n.start()] + body[m_n.end():]
        elif m_eq:
            cond = ('stat', m_eq.group(2).lower(), 1, None)
            body = m_eq.group(1) + ' + 1'
        elif c_level:
            cond = c_level
            body = _strip(level_line, level_spans)
            if c_level[0] == 'perlevel' and m_each: cond = ('each', int(m_each.group(1) or m_each.group(2) or 1)); body = line
        elif m_stat and (m_stat.group(1) or m_stat.group(3)):
            every = int(m_stat.group(1) or m_stat.group(3))
            cond = ('stat', m_stat.group(2).lower(), every, None)
        elif m_each:
            cond = ('each', int(m_each.group(1) or m_each.group(2) or 1))
        elif m_min:
            cond = ('min', int(m_min.group(1)))

        # text left once the condition wording is removed — used to tell a header line from a failed parse
        rest = body if body is not line else line
        for mm in (m_set, m_min, m_each, m_stat):
            if cond is not None and mm and rest is line: rest = line[:mm.start()] + ' ' + line[mm.end():]
        # a refine / set block wraps the conditions found inside it ("both must hold");
        # a condition of the same kind as the open block replaces it instead
        outer = active if (active_block and active and active[0] in ('min', 'set')) else None
        gate = (None, None)
        if cond is not None and cond[0] != 'skip':
            if outer and cond[0] != outer[0]:
                gate = (outer[1], None) if outer[0] == 'min' else (None, outer[1])
            else:
                outer = None
            cond = with_gate(cond, gate)

        cap = P_STAT_CAP.search(line)
        if cap and active and active[0] == 'stat' and active[1] == cap.group(1).lower():
            b = buckets.pop(active, {})
            active = ('stat', active[1], active[2], int(cap.group(2)), active[4])
            if b: buckets.setdefault(active, {}).update(b)
            continue
        lcap = P_LEVEL_CAP.search(line)
        if lcap and cond is None and active and active[0] == 'perlevel' and not P_STAT.search(line):
            b = buckets.pop(active, {})
            active = ('perlevel', active[1], active[2], int(lcap.group(1) or lcap.group(2)), active[4])
            if b: buckets.setdefault(active, {}).update(b)
            continue

        effects = parse_line(body if cond is not None else line)
        # per-refine cast reduction detected inside parse_line
        if 'variableCastPercent:perRefine' in effects:
            v = effects.pop('variableCastPercent:perRefine')
            _add(buckets.setdefault(('each', 1, (None, None)), {}), 'variableCastPercent', v)
            conditional.append(line)

        if cond is not None:
            if cond[0] == 'skip':
                active = None; active_block = False
                continue
            pre = parse_line(prefix) if prefix.strip() else {}
            if pre:
                tgt = target_for(active) if active_block else plain
                for k, v in pre.items(): _add(tgt, k, v)
            if nested:
                # the parenthetical adds to the same effect once the refine is reached
                extra = parse_line(nested[1])
                if not extra and len(effects) == 1:
                    m_v = re.search(r'\+?\s*(\d+(?:\.\d+)?)\s*(%?)', nested[1])
                    if m_v:
                        k = next(iter(effects))
                        extra = {k: float(m_v.group(1))}
                if extra:
                    tgt = target_for(with_gate(cond[:-1], (nested[0], gate[1])))
                    for k, v in extra.items(): _add(tgt, k, v)
                else:
                    unparsed.append(f'{line[:m_statmin.end()].strip()} (+{nested[0]}) {nested[1]}')
            after = (outer, True) if outer else (None, False)   # back to the enclosing block once this line is done
            if effects:
                # condition + bonus on the same line; block continues only if the line ends with ','
                tgt = target_for(cond)
                for k, v in effects.items(): _add(tgt, k, v)
                conditional.append(line)
                active, active_block = (cond, True) if line.rstrip().endswith(',') else after
            elif nested and not body.strip(' ,.'):
                conditional.append(line); active, active_block = after
            elif re.search(r'\d\s*%|[+\-]\s*\d', rest):
                # the line carried its own effect text but nothing was read: report it, never open a block
                if not P_NOISE.search(line) and not P_SKIP_EFFECT.search(line): unparsed.append(line)
                active, active_block = after
            else:
                active, active_block = cond, True  # header line: following lines belong to it
                conditional.append(line)
            continue

        if effects:
            tgt = target_for(active) if active_block else plain
            for k, v in effects.items(): _add(tgt, k, v)
            (conditional if active_block else parsed).append(line)
        else:
            if not P_NOISE.search(line) and re.search(r'\d', line) and re.search(r'%|\+|ลด|เพิ่ม', line):
                unparsed.append(line)

    cond = {}
    def gated(entry, gate):
        if gate[0]: entry['refine'] = gate[0]
        if gate[1]: entry['requires'] = list(gate[1])
        return entry
    for key, v in buckets.items():
        if not v: continue
        kind, gate = key[0], key[-1]
        if kind == 'min':      cond.setdefault('refine', []).append({'min': key[1], 'bonuses': v} | ({'requires': list(gate[1])} if gate[1] else {}))
        elif kind == 'each':   cond.setdefault('perRefine', []).append(gated({'every': key[1]}, gate) | {'bonuses': v})
        elif kind == 'stat':   cond.setdefault('perStat', []).append(gated({'stat': key[1], 'every': key[2], 'max': key[3]}, gate) | {'bonuses': v})
        elif kind == 'statmin': cond.setdefault('statMin', []).append(gated({'stat': key[1], 'min': key[2]}, gate) | {'bonuses': v})
        elif kind == 'level':  cond.setdefault('level', []).append(gated({'min': key[1], 'max': key[2]}, gate) | {'bonuses': v})
        elif kind == 'perlevel': cond.setdefault('perLevel', []).append(gated({'every': key[1], 'min': key[2], 'max': key[3]}, gate) | {'bonuses': v})
        elif kind == 'set':    cond.setdefault('set', []).append(gated({'requires': list(key[1])}, (gate[0], None)) | {'bonuses': v})
    if 'refine' in cond:
        cond['refine'].sort(key=lambda e: e['min'])
        # Sealed-card style penalties: "เพิ่มระยะเวลาร่าย 150%" then "เมื่ออัพเกรด +15 เพิ่มระยะเวลาร่าย 120%" — the refine line
        # *replaces* the penalty with a milder one; store the difference so the sum comes out at -120, not -270.
        for e in cond['refine']:
            if e.get('requires'): continue
            replaced = False
            for k, v in list(e['bonuses'].items()):
                base = plain.get(k, 0)
                if base < 0 and v < 0 and abs(v) < abs(base): e['bonuses'][k] = _num(v - base); replaced = True
            if replaced:
                # the same block restates the unchanged bonuses too ("MHP -50%, MSP +50%") — they are not added again
                for k, v in list(e['bonuses'].items()):
                    if plain.get(k) == v: del e['bonuses'][k]
        cond['refine'] = [e for e in cond['refine'] if e['bonuses']]
    if 'perRefine' in cond: cond['perRefine'].sort(key=lambda e: e['every'])
    return plain, cond, unparsed, parsed, conditional
