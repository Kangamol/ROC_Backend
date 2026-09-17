#!/usr/bin/env python3
"""Turn the Thai client description of an item into structured effects.

Output of parse_effects(lines):
    bonuses    {key: number}                       unconditional
    cond       {refine:    [{min, bonuses}],       applies once refine >= min
                perRefine: [{every, bonuses}],     bonuses * floor(refine / every)
                perStat:   [{stat, every, max, bonuses}],  bonuses * floor(baseStat / every)
                set:       [{requires: [names], bonuses}]}  all named items must be worn
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
P_STAT_TH = re.compile(r'เพิ่ม\s*(?:ค่า)?\s*(' + _STAT_RE + r')\s*(?:ขึ้น)?\s*(?:อีก)?\s*\+?\s*(\d+(?:\.\d+)?)\s*(%?)', re.I)

RACE = {
    'กึ่งมนุษย์': 'demihuman', 'demi-human': 'demihuman', 'demihuman': 'demihuman', 'demi human': 'demihuman',
    'สัตว์': 'brute', 'brute': 'brute', 'พืช': 'plant', 'plant': 'plant', 'แมลง': 'insect', 'insect': 'insect',
    'ปลา': 'fish', 'fish': 'fish', 'สัตว์น้ำ': 'fish', 'ปีศาจ': 'demon', 'demon': 'demon',
    'อันเดด': 'undead', 'undead': 'undead', 'มังกร': 'dragon', 'dragon': 'dragon',
    'เทพ': 'angel', 'เทวดา': 'angel', 'angel': 'angel', 'ไร้รูปร่าง': 'formless', 'ไร้รูป': 'formless', 'formless': 'formless',
    'player': 'player', 'ผู้เล่น': 'player', 'boss': 'boss', 'บอส': 'boss', 'ทุกเผ่า': 'all', 'ศัตรูทั่วไป': 'normal', 'ศัตรูทั้งหมด': 'all', 'ศัตรูทุกชนิด': 'all',
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
P_SIZE = re.compile(r'(?:ขนาด|size)\s*(' + _alt(SIZE) + r')(?![A-Za-z])', re.I)
P_SKILL = re.compile(r'(?:สกิล|skill)\s*\[?\s*([A-Z][A-Za-z\'\-\. ]+?)\s*\]?\s*(?=\+|\d|Lv|ลง|เพิ่ม|ลด|,|$|ขึ้น|ที่)', re.I)
P_PCT = re.compile(r'([+\-]?\s*\d+(?:\.\d+)?)\s*%')
P_NUM = re.compile(r'(\d+(?:\.\d+)?)')

# cast / delay ----------------------------------------------------------------
_VCT = r'(?:Vari?able\s*Cast(?:ing)?\s*Time|Virable\s*Cast\s*Time|VCT|(?:ระยะ)?เวลา(?:ใน)?(?:การ)?ร่าย(?:เวทย์|เวทมนตร์|สกิล|คาถา)?(?:แบบ)?(?:แปรผัน|ผันแปร)?)'
P_VCT_DOWN = re.compile(r'(?:ลด\s*' + _VCT + r'|' + _VCT + r'\s*ลดลง)\s*(?:ลง)?\s*(?:เพิ่มเติม)?(?:อีก)?\s*(\d+(?:\.\d+)?)\s*%', re.I)
P_VCT_UP = re.compile(r'เพิ่ม\s*' + _VCT + r'\s*(?:ขึ้น)?\s*(\d+(?:\.\d+)?)\s*%', re.I)
P_FCT_DOWN = re.compile(r'ลด\s*(?:Fixed\s*Cast(?:ing)?\s*Time|FCT|ระยะเวลาร่ายแบบคงที่)\s*(?:ลง)?\s*(?:อีก)?\s*(\d+(?:\.\d+)?)\s*(วินาที|%)', re.I)
_ACD = r'(?:After\s*Cast\s*Delay|ACD|(?:สกิล)?\s*(?:Delay|ดีเลย์)(?:\s*หลัง(?:จาก)?(?:การ)?ใช้สกิล)?)'
P_ACD_DOWN = re.compile(r'(?:ลด\s*' + _ACD + r'|' + _ACD + r'\s*ลดลง)\s*(?:ลง)?\s*(?:อีก)?\s*(\d+(?:\.\d+)?)\s*%', re.I)
P_ACD_UP = re.compile(r'เพิ่ม\s*' + _ACD + r'\s*(?:ขึ้น)?\s*(\d+(?:\.\d+)?)\s*%', re.I)
# "ลดระยะเวลาในการร่ายเวทย์คิดเป็น% ตามการอัพเกรดหมวก"  → 1% per refine
P_VCT_PER_REFINE = re.compile(r'ลด\s*' + _VCT + r'.*(?:คิดเป็น|เท่ากับ)\s*%?\s*ตาม(?:การ|ระดับ)?(?:อัพเกรด|ตีบวก|Refine)', re.I)

# conditions ------------------------------------------------------------------
P_COND_MIN = re.compile(r'(?:(?:หาก|เมื่อ)?\s*(?:Item\s*)?อัพเกรดตั้งแต่ระดับ\s*\+?|ตั้งแต่ขั้นอัพเกรดมากกว่า|ทุกการอัพเกรดที่มากกว่าระดับ\s*\+?|เมื่ออัพเกรด(?:ถึง)?(?:ขั้น|ตั้งแต่)?|อัพเกรดตั้งแต่(?:ขั้น)?|เมื่อขั้นอัพเกรด(?:ตั้งแต่)?|เมื่อ(?:ตีบวก)?(?:ตั้งแต่)?\s*\+|ที่ระดับ\s*\+|ถ้า\S*ตีบวกตั้งแต่\s*\+?|ตีบวก(?:ถึง|ตั้งแต่)\s*\+?)\s*(\d+)')
P_COND_EACH = re.compile(r'ทุก\s*ๆ?\s*(?:การ)?(?:อัพเกรด|ตีบวก)\s*(\d+)\s*ขั้น')
P_COND_STAT = re.compile(r'ทุก\s*ๆ?\s*(?:Base\s*)?(\d+)?\s*(?:Base\s*)?(STR|AGI|VIT|INT|DEX|LUK)\s*(\d+)?', re.I)
P_STAT_CAP = re.compile(r'Base\s*(STR|AGI|VIT|INT|DEX|LUK)\s*สูงสุด.*?(\d+)', re.I)
P_SET = re.compile(r'(?:เมื่อ(?:สวม)?ใส่\s*(?:ร่วมกัน)?(?:กับ|คู่กับ|ร่วมกับ|รวมกันกับ|รวมกับ)|\[Set\]|เมื่อสวมใส่)\s*(.+?)\s*(?:ร่วมกัน|ด้วยกัน|ทั้งหมดด้วยกัน|ทั้งหมด|,\s*$|$|(?=\s*(?:ลด|เพิ่ม|[A-Z][A-Za-z]+\s*[+\-]\s*\d)))', re.I)

# lines that carry no stat effect (so they are not reported as unparsed)
P_NOISE = re.compile(r'แลกเปลี่ยน|ไอเทมเช่า|Item เช่า|ระยะเวลาเช่า|ไม่สามารถ|ไม่มีวัน|ไม่เสียหาย|Ban Guild|WoE|PvP|PVP|Raid|Enchant Stone Box|Stone Box|<NAVI>|^[_―\-\s]*$|หมายเหตุ|ระวัง|Sillit|คลังเก็บ|ดูกลมกลืน|\*\*\*|Zodiac|มีโอกาส|โอกาส|สุ่ม|Autospell|Auto Spell|เมื่อฆ่า|เมื่อกำจัด|เมื่อสังหาร|ทุกครั้งที่|ทุก\s*ๆ?\s*\d+\s*วินาที|ทุก\s*\d+\s*วินาที|ถอด|ตัวละครเลเวล|BaseLv|Base\s*Lv|ระดับ Refine\*', re.I)
P_SKIP_EFFECT = re.compile(r'Global Cooldown|หลังโจมตี|ผลรวม|ค่าตีบวกของทั้งเซ็ต|ของเซ็ต|ของเซต', re.I)


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
    if m: return 'size', SIZE[m.group(1).lower()]
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
        t = ('size', SIZE[m.group(1).lower()])
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
    for m in P_STAT.finditer(text):
        key = STAT_ALIASES[m.group(1).lower()]
        val = float(m.group(3)) * (-1 if m.group(2) == '-' else 1)
        if m.group(4): key = key + 'Percent' if not key.endswith('Percent') else key
        if key == 'maxHpSp': _add(out, 'maxHp', val); _add(out, 'maxSp', val)
        elif key == 'maxHpSpPercent': _add(out, 'maxHpPercent', val); _add(out, 'maxSpPercent', val)
        else: _add(out, key, val)
        consumed.append(m.span())
    for m in P_STAT_PRE.finditer(text):
        if any(a <= m.start() < b for a, b in consumed): continue
        key = STAT_ALIASES[m.group(2).lower()]
        val = float(m.group(3)) * (-1 if m.group(1) == '-' else 1)
        if m.group(4): key += 'Percent'
        _add(out, key, val); consumed.append(m.span())
    for m in P_STAT_TH.finditer(text):
        if any(a <= m.start() < b for a, b in consumed): continue
        if re.search(r'ต่อ|เผ่า|ธาตุ|ขนาด|ศัตรู|Player|Boss|สกิล', text[m.end():m.end() + 40], re.I): continue  # targeted, handled below
        key = STAT_ALIASES[m.group(1).lower()]
        if m.group(3): key += 'Percent'
        _add(out, key, float(m.group(2))); consumed.append(m.span())

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
    pct = _pct(text)
    if pct is not None:
        if re.search(r'SP\s*(?:ที่ใช้|ในการ(?:ร่าย|ใช้))|การใช้\s*SP|ใช้\s*SP', text) and re.search(r'ลด', text): _add(out, 'spCostPercent', pct)
        elif re.search(r'SP\s*(?:ที่ใช้|ในการ(?:ร่าย|ใช้))|การใช้\s*SP|ใช้\s*SP', text) and re.search(r'เพิ่ม|เสีย', text): _add(out, 'spCostPercent', -pct)
        elif re.search(r'ฟื้นฟู\s*HP.*ตามธรรมชาติ|ความเร็วในการฟื้น(?:ฟู)?\s*HP|HP\s*Recovery', text, re.I): _add(out, 'hpRecoveryPercent', pct)
        elif re.search(r'ฟื้นฟู\s*SP.*ตามธรรมชาติ|ความเร็วในการฟื้น(?:ฟู|ค่า)?\s*SP|SP\s*Recovery', text, re.I): _add(out, 'spRecoveryPercent', pct)
        elif re.search(r'ปริมาณการฟื้นฟูของ\s*Skill|พลังฮีล|Heal(?:ing)?\s*(?:Power|Effect)|ฟื้นฟู.*ที่ตนเองใช้|ปริมาณการรักษา|ให้กับ\s*Heal|ค่า\s*Heal|สกิลประเภท\s*Heal|Heal\s*แรงขึ้น', text, re.I): _add(out, 'healPowerPercent', pct)
        elif re.search(r'ประสิทธิภาพการฟื้นฟู|การฟื้นฟูที่ได้รับ|ไอเท็มฟื้นฟู|ไอเทมฟื้นฟู', text): _add(out, 'healReceivedPercent', pct)
        elif re.search(r'EXP|ค่าประสบการณ์', text, re.I):
            kind, tgt = _target(text)
            _add(out, f'exp:{kind}:{tgt}' if kind == 'race' and tgt != 'all' else 'expPercent', pct)

    # --- damage / resist / ignore def (targeted) -----------------------------
    if pct is not None and not out.get('variableCastPercent') and not out.get('afterCastDelayPercent'):
        targets = _targets(text)
        kind, tgt = targets[0] if targets else (None, None)
        dk = _kind(text)
        is_resist = re.search(r'ที่ได้รับ|ได้รับจาก|ความเสียหายจาก|ทนทาน|ต้านทาน|ลด\s*Damage\s*(?:จาก|ที่)|Damage\s*ที่ได้รับ|ลดค่าความเสียหาย|ลดความเสียหาย|ลดพลังโจมตีจาก|ป้องกันการโจมตี|ลดดาเมจ', text)
        is_ignore = re.search(r'เพิกเฉย|ไม่สนใจ|ลดค่าพลังป้องกัน|ลดพลังป้องกัน|ทะลุ(?:ทะลวง)?พลังป้องกัน|Ignore', text, re.I)
        is_dmg = re.search(r'เพิ่ม.*(?:Damage|ดาเมจ|ความเสียหาย|ความแรง|ความรุนแรง|พลังโจมตี)|โจมตี.*แรงขึ้น|Damage.*เพิ่มขึ้น|(?:Damage|ความเสียหาย)\s*\+', text, re.I)
        if is_ignore and re.search(r'ป้องกัน|def', text, re.I):
            for k2, t2 in (targets or [('race', 'all')]):
                if dk in ('phys', 'both'): _add(out, f'ignoreDef:{k2}:{t2}', pct)
                if dk in ('magic', 'both'): _add(out, f'ignoreMdef:{k2}:{t2}', pct)
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


def parse_effects(lines):
    plain, by_min, by_each, by_stat, by_set = {}, {}, {}, {}, {}
    unparsed, parsed, conditional = [], [], []
    active = None          # ('min', 5) | ('each', 2) | ('stat', 'VIT', 10, cap) | ('set', names)
    active_block = False   # True while the header's block continues on following lines

    def target_for(cond):
        if cond is None: return plain
        if cond[0] == 'min': return by_min.setdefault(cond[1], {})
        if cond[0] == 'each': return by_each.setdefault(cond[1], {})
        if cond[0] == 'stat': return by_stat.setdefault((cond[1], cond[2], cond[3]), {})
        if cond[0] == 'set': return by_set.setdefault(tuple(cond[1]), {})
        return plain

    for raw in lines:
        line = raw.strip()
        if not line or re.match(r'^[_―\-=\s]+$', line):
            active = None; active_block = False
            continue
        if re.match(r'^(ประเภท|ตำแหน่ง|น้ำหนัก|เลเวล|Lv|อาชีพ|ใช้กับ|ใช้สำหรับ|ธาตุ|ใส่กับ|ติดตั้ง|ต้องการ)', line):
            active = None; active_block = False
            continue

        # ---- detect a condition on this line ----
        cond = None
        m_set = P_SET.search(line) if re.search(r'\[Set\]|ร่วมกัน|ด้วยกัน|ร่วมกับ|รวมกันกับ|รวมกับ|คู่กับ', line) else None
        m_stat = P_COND_STAT.search(line)
        m_each = P_COND_EACH.search(line)
        m_min = P_COND_MIN.search(line)
        if m_set:
            names = _set_names(line)
            cond = ('set', names) if names else ('skip', None)
        elif m_stat and (m_stat.group(1) or m_stat.group(3)):
            every = int(m_stat.group(1) or m_stat.group(3))
            cond = ('stat', m_stat.group(2).lower(), every, None)
        elif m_each:
            cond = ('each', int(m_each.group(1)))
        elif m_min:
            cond = ('min', int(m_min.group(1)))

        cap = P_STAT_CAP.search(line)
        if cap and active and active[0] == 'stat' and active[1] == cap.group(1).lower():
            key = (active[1], active[2], active[3])
            b = by_stat.pop(key, {})
            active = ('stat', active[1], active[2], int(cap.group(2)))
            if b: by_stat.setdefault((active[1], active[2], active[3]), {}).update(b)
            continue

        effects = parse_line(line)
        # per-refine cast reduction detected inside parse_line
        if 'variableCastPercent:perRefine' in effects:
            v = effects.pop('variableCastPercent:perRefine')
            _add(by_each.setdefault(1, {}), 'variableCastPercent', v)
            conditional.append(line)

        if cond is not None:
            if cond[0] == 'skip':
                active = None; active_block = False
                continue
            if effects:
                # condition + bonus on the same line; block continues only if the line ends with ','
                tgt = target_for(cond)
                for k, v in effects.items(): _add(tgt, k, v)
                conditional.append(line)
                active, active_block = (cond, True) if line.rstrip().endswith(',') else (None, False)
            else:
                active, active_block = cond, True  # header line: following lines belong to it
                conditional.append(line)
            continue

        if effects:
            tgt = target_for(active) if active_block else plain
            for k, v in effects.items(): _add(tgt, k, v)
            (conditional if active_block else parsed).append(line)
            if active_block and not line.rstrip().endswith(','):
                # a block line that does not continue with ',' may still be followed by more block
                # lines (Pink Shampoo Hat); keep the block until a new header / blank / type line
                pass
        else:
            if not P_NOISE.search(line) and re.search(r'\d', line) and re.search(r'%|\+|ลด|เพิ่ม', line):
                unparsed.append(line)

    cond = {}
    if by_min: cond['refine'] = [{'min': k, 'bonuses': v} for k, v in sorted(by_min.items()) if v]
    if by_each: cond['perRefine'] = [{'every': k, 'bonuses': v} for k, v in sorted(by_each.items()) if v]
    if by_stat: cond['perStat'] = [{'stat': s, 'every': e, 'max': c, 'bonuses': v} for (s, e, c), v in by_stat.items() if v]
    if by_set: cond['set'] = [{'requires': list(k), 'bonuses': v} for k, v in by_set.items() if v]
    return plain, cond, unparsed, parsed, conditional
