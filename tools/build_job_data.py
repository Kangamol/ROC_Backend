#!/usr/bin/env python3
"""Build data/jobs.json from rAthena's pre-renewal job tables (job data only —
item data always comes from the client).

Sources (db/pre-re/): job_basepoints.yml (base HP/SP per level),
job_aspd.yml (base ASPD per weapon type), job_stats.yml (max weight,
job-level stat bonuses). Downloaded on demand into the scratch dir.

Output: { "<Job Name>": { key, maxWeight, hp: [lv1..], sp: [lv1..],
                          aspd: {weaponType: delay}, bonusStats: [{level, str..luk}] } }
"""
import json, re, sys, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'jobs.json'
CACHE = Path('/private/tmp/claude-501/-Users-ton-it-Desktop-Project-ProductList/0b466053-85b8-4f9f-aa33-4de4cf87699f/scratchpad')
BASE = 'https://raw.githubusercontent.com/rathena/rathena/master/db/pre-re/'

# Simulator job name -> rAthena job key
JOBS = {
    'Novice': 'Novice', 'Swordman': 'Swordman', 'Magician': 'Mage', 'Archer': 'Archer', 'Acolyte': 'Acolyte',
    'Merchant': 'Merchant', 'Thief': 'Thief',
    'Knight': 'Knight', 'Priest': 'Priest', 'Wizard': 'Wizard', 'Blacksmith': 'Blacksmith', 'Hunter': 'Hunter', 'Assassin': 'Assassin',
    'Crusader': 'Crusader', 'Monk': 'Monk', 'Sage': 'Sage', 'Rogue': 'Rogue', 'Alchemist': 'Alchemist', 'Bard': 'Bard', 'Dancer': 'Dancer',
    'Lord Knight': 'Lord_Knight', 'High Priest': 'High_Priest', 'High Wizard': 'High_Wizard', 'Whitesmith': 'Whitesmith',
    'Sniper': 'Sniper', 'Assassin Cross': 'Assassin_Cross', 'Paladin': 'Paladin', 'Champion': 'Champion', 'Professor': 'Professor',
    'Stalker': 'Stalker', 'Creator': 'Creator', 'Clown': 'Clown', 'Gypsy': 'Gypsy',
    'Super Novice': 'Super_Novice', 'Taekwon': 'Taekwon', 'Star Gladiator': 'Star_Gladiator', 'Soul Linker': 'Soul_Linker',
    'Ninja': 'Ninja', 'Gunslinger': 'Gunslinger',
}
# rAthena weapon keys -> simulator subTypes
ASPD_MAP = {
    'Fist': ['NONE'], 'Dagger': ['DAGGER'], '1hSword': ['SWORD_1H'], '2hSword': ['SWORD_2H'], '1hSpear': ['SPEAR_1H'], '2hSpear': ['SPEAR_2H'],
    '1hAxe': ['AXE_1H'], '2hAxe': ['AXE_2H'], 'Mace': ['MACE'], '2hMace': ['MACE_2H'], 'Staff': ['STAFF_1H'], '2hStaff': ['STAFF_2H'],
    'Bow': ['BOW'], 'Knuckle': ['KNUCKLE'], 'Musical': ['INSTRUMENT'], 'Whip': ['WHIP'], 'Book': ['BOOK'], 'Katar': ['KATAR'],
    'Revolver': ['REVOLVER'], 'Rifle': ['RIFLE'], 'Gatling': ['GATLING'], 'Shotgun': ['SHOTGUN'], 'Grenade': ['GRENADE_LAUNCHER'],
    'Huuma': ['HUUMA'], 'Shield': ['SHIELD'],
}


def fetch(name):
    p = CACHE / name
    if not p.exists() or p.stat().st_size < 100:
        urllib.request.urlretrieve(BASE + name, p)
    return p.read_text(encoding='utf-8')


def blocks(text):
    """Split the YAML Body into '- Jobs:' blocks (tiny hand parser — the files are regular)."""
    body = text.split('\nBody:\n', 1)[1]
    for raw in re.split(r'\n  - Jobs:\n', '\n' + body)[1:]:
        jobs = re.findall(r'^      (\w+): true', raw, re.M)
        yield jobs, raw


def parse_levels(raw, key, field):
    """Values of `field` under the `key:` section, indexed by level (level 1 → index 0)."""
    m = re.search(rf'^    {key}:\n(.*?)(?=^    \w+:|\Z)', raw, re.M | re.S)
    if not m: return None
    pairs = re.findall(rf'- Level: (\d+)\s+{field}: (\d+)', m.group(1))
    if not pairs: return None
    out = [0] * max(int(l) for l, _ in pairs)
    for l, v in pairs: out[int(l) - 1] = int(v)
    return out


def main():
    base = {j: {'key': k} for j, k in JOBS.items()}
    by_key = {k: j for j, k in JOBS.items()}
    by_key['Supernovice'] = 'Super Novice'  # job_basepoints.yml spelling

    for jobs, raw in blocks(fetch('job_basepoints.yml')):
        hp, sp = parse_levels(raw, 'BaseHp', 'Hp'), parse_levels(raw, 'BaseSp', 'Sp')
        for k in jobs:
            if k in by_key:
                if hp: base[by_key[k]]['hp'] = hp
                if sp: base[by_key[k]]['sp'] = sp

    for jobs, raw in blocks(fetch('job_aspd.yml')):
        m = re.search(r'^    BaseASPD:\n((?:      \w+: \d+\n?)+)', raw, re.M)
        if not m: continue
        aspd = {}
        for w, v in re.findall(r'(\w+): (\d+)', m.group(1)):
            for sub in ASPD_MAP.get(w, [w]): aspd[sub] = int(v)
        for k in jobs:
            if k in by_key: base[by_key[k]]['aspd'] = aspd

    for jobs, raw in blocks(fetch('job_stats.yml')):
        mw = re.search(r'^    MaxWeight: (\d+)', raw, re.M)
        bonus = []
        for lvl, body in re.findall(r'      - Level: (\d+)\n((?:        \w+: \d+\n)+)', raw):
            entry = {'level': int(lvl)}
            for stat, v in re.findall(r'(\w+): (\d+)', body): entry[stat.lower()] = int(v)
            bonus.append(entry)
        for k in jobs:
            if k in by_key:
                if mw: base[by_key[k]]['maxWeight'] = int(mw.group(1))
                if bonus: base[by_key[k]]['bonusStats'] = bonus

    missing = [j for j, d in base.items() if 'hp' not in d or 'aspd' not in d]
    json.dump(base, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print(f'{len(base)} jobs -> {OUT} ({OUT.stat().st_size / 1024:.0f} KB); missing hp/aspd: {missing}')
    k = base['Knight']
    print('Knight: hp lv99', k['hp'][98], 'sp lv99', k['sp'][98], 'aspd', {w: k['aspd'][w] for w in ('SWORD_1H', 'SWORD_2H', 'SPEAR_2H')}, 'weight', k['maxWeight'], 'bonus entries', len(k['bonusStats']))


if __name__ == '__main__':
    main()
