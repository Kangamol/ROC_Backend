#!/usr/bin/env python3
"""Export items whose structural fields could not be read from the client text
to an Excel workbook for manual review, and read the corrections back.

  python3 tools/export_review.py            → data/review_items.xlsx
  python3 tools/export_review.py --import   → data/manual_overrides.json (used by convert_items.py)

Sheets: weapons (subType / weaponLevel / atk), armor (def / jobs). The FIX_*
columns are dropdowns (Thai labels); everything else is read-only context.
"""
import json, sys
from pathlib import Path
from openpyxl import Workbook, load_workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = Path(__file__).resolve().parent.parent
ITEMS = ROOT / 'data' / 'items.json'
XLSX = ROOT / 'data' / 'review_items.xlsx'
OVERRIDES = ROOT / 'data' / 'manual_overrides.json'

# Dropdown label (what the user sees) -> value stored in the data
WEAPON_TYPES = {
    'ดาบมือเดียว (1H Sword)': 'SWORD_1H', 'ดาบสองมือ (2H Sword)': 'SWORD_2H',
    'มีด (Dagger)': 'DAGGER', 'หอกมือเดียว (1H Spear)': 'SPEAR_1H', 'หอกสองมือ (2H Spear)': 'SPEAR_2H',
    'ขวานมือเดียว (1H Axe)': 'AXE_1H', 'ขวานสองมือ (2H Axe)': 'AXE_2H', 'กระบอง (Mace)': 'MACE',
    'ไม้เท้ามือเดียว (Rod/Staff)': 'STAFF_1H', 'ไม้เท้าสองมือ (2H Staff)': 'STAFF_2H',
    'ธนู (Bow)': 'BOW', 'คาตาร์ (Katar)': 'KATAR', 'หนังสือ (Book)': 'BOOK', 'สนับมือ (Knuckle)': 'KNUCKLE',
    'เครื่องดนตรี (Instrument)': 'INSTRUMENT', 'แส้ (Whip)': 'WHIP', 'ดาวกระจาย (Huuma)': 'HUUMA',
    'ปืนพก (Revolver)': 'REVOLVER', 'ไรเฟิล (Rifle)': 'RIFLE', 'ลูกซอง (Shotgun)': 'SHOTGUN',
    'แกตลิ่ง (Gatling)': 'GATLING', 'เครื่องยิงระเบิด (Grenade Launcher)': 'GRENADE_LAUNCHER',
}
WEAPON_LEVELS = {'Lv 1': 1, 'Lv 2': 2, 'Lv 3': 3, 'Lv 4': 4}
JOBS = [
    'ทุกอาชีพ', 'ทุกอาชีพ ยกเว้น Novice Cls', 'Novice Cls', 'Swordman Cls', 'Magician Cls', 'Archer Cls', 'Acolyte Cls',
    'Merchant Cls', 'Thief Cls', 'Swordman Cls/Merchant Cls/Thief Cls', 'Swordman Cls/Merchant Cls',
    'Knight Cls', 'Priest Cls', 'Wizard Cls', 'Blacksmith Cls', 'Hunter Cls', 'Assassin Cls',
    'Crusader Cls', 'Monk Cls', 'Sage Cls', 'Rogue Cls', 'Alchemist Cls', 'Bard Cls/Dancer Cls',
    'Hi-Class ทุกอาชีพ ยกเว้น Novice Cls', 'High-Class ขั้นสอง', 'Super Novice', 'Taekwon Cls', 'Ninja Cls', 'Gunslinger Cls',
    'อื่นๆ (พิมพ์เองในช่อง FIX_jobs_other)',
]

YELLOW = PatternFill('solid', fgColor='FFF2CC')
GREY = PatternFill('solid', fgColor='EFEFEF')


def add_dropdown(ws, col_letter, first_row, last_row, options, title):
    """Excel in-cell dropdown. Long lists live on the 'lists' sheet (formula limit is 255 chars)."""
    lists = ws.parent['lists'] if 'lists' in ws.parent.sheetnames else ws.parent.create_sheet('lists')
    c = lists.max_column + 1 if lists.max_row > 1 or lists['A1'].value else 1
    lists.cell(row=1, column=c, value=title).font = Font(bold=True)
    for i, o in enumerate(options, 2):
        lists.cell(row=i, column=c, value=o)
    lists.column_dimensions[get_column_letter(c)].width = 36
    ref = f"lists!${get_column_letter(c)}$2:${get_column_letter(c)}${len(options) + 1}"
    dv = DataValidation(type='list', formula1=ref, allow_blank=True, showDropDown=False)
    dv.error = 'เลือกจากรายการเท่านั้น'; dv.errorTitle = 'ค่าไม่ถูกต้อง'; dv.prompt = f'เลือก {title}'; dv.promptTitle = title
    ws.add_data_validation(dv)
    dv.add(f'{col_letter}{first_row}:{col_letter}{last_row}')


def number_validation(ws, col_letter, first_row, last_row, lo, hi, title):
    dv = DataValidation(type='whole', operator='between', formula1=str(lo), formula2=str(hi), allow_blank=True)
    dv.error = f'ใส่ตัวเลข {lo}–{hi}'; dv.errorTitle = 'ค่าไม่ถูกต้อง'; dv.prompt = f'ตัวเลข {lo}–{hi}'; dv.promptTitle = title
    ws.add_data_validation(dv)
    dv.add(f'{col_letter}{first_row}:{col_letter}{last_row}')


def make_sheet(wb, title, headers, rows, examples, notes):
    ws = wb.create_sheet(title)
    ws.append(headers)
    ws.append(examples)  # row 2 = example row (ignored on import)
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = YELLOW if str(cell.value).startswith('FIX_') else GREY
        if cell.value in notes:
            cell.comment = Comment(notes[cell.value], 'ROC')
    for cell in ws[2]:
        cell.font = Font(italic=True, color='888888')
    for r in rows: ws.append(r)
    for i, h in enumerate(headers, 1):
        ws.column_dimensions[get_column_letter(i)].width = 70 if h == 'description' else 30 if h.startswith('FIX_') else 18
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical='top', wrap_text=cell.column_letter == get_column_letter(len(headers)))
    ws.freeze_panes = 'C3'
    return ws


def export():
    items = json.load(open(ITEMS, encoding='utf-8'))
    wb = Workbook(); wb.remove(wb.active)

    weapons = [i for i in items if i['itemType'] == 'WEAPON' and (i['subType'] == 'UNKNOWN' or i['weaponLevel'] is None or i['atk'] is None)]
    ws = make_sheet(
        wb, 'weapons',
        ['id', 'name', 'ประเภท(ตอนนี้)', 'Lv อาวุธ(ตอนนี้)', 'ATK(ตอนนี้)', 'FIX_subType', 'FIX_weaponLevel', 'FIX_atk', 'description'],
        [[i['id'], i['name'], i['subType'], i['weaponLevel'], i['atk'], '', '', '', i['description']] for i in weapons],
        ['(ตัวอย่าง)', 'Sword', 'UNKNOWN', None, None, 'ดาบมือเดียว (1H Sword)', 'Lv 1', 25, 'ดาบธรรมดาแบบถือมือเดียว …'],
        {'FIX_subType': 'เลือกชนิดอาวุธจาก dropdown — ปล่อยว่างถ้าค่าตอนนี้ถูกแล้ว',
         'FIX_weaponLevel': 'เลือก Lv 1–4 ของอาวุธ (ไม่ใช่เลเวลที่ต้องการ)',
         'FIX_atk': 'พิมพ์ตัวเลข ATK ที่แสดงในเกม'},
    )
    n = len(weapons) + 2
    add_dropdown(ws, 'F', 3, n, list(WEAPON_TYPES), 'ชนิดอาวุธ')
    add_dropdown(ws, 'G', 3, n, list(WEAPON_LEVELS), 'Lv อาวุธ')
    number_validation(ws, 'H', 3, n, 0, 9999, 'ATK')

    armor = [i for i in items if i['itemType'] == 'ARMOR' and (i['def'] is None or not i['jobs'])]
    ws = make_sheet(
        wb, 'armor',
        ['id', 'name', 'ตำแหน่ง', 'DEF(ตอนนี้)', 'อาชีพ(ตอนนี้)', 'FIX_def', 'FIX_jobs', 'FIX_jobs_other', 'description'],
        [[i['id'], i['name'], i['subType'], i['def'], i['jobs'], '', '', '', i['description']] for i in armor],
        ['(ตัวอย่าง)', 'Cotton Shirts', 'ARMOR', None, None, 10, 'ทุกอาชีพ', '', 'เสื้อธรรมดาที่เหมาะสำหรับใส่ในทุกโอกาส …'],
        {'FIX_def': 'พิมพ์ตัวเลข DEF ที่แสดงในเกม',
         'FIX_jobs': 'เลือกอาชีพจาก dropdown — ถ้าไม่มีในรายการ เลือก "อื่นๆ" แล้วพิมพ์ในช่อง FIX_jobs_other',
         'FIX_jobs_other': 'พิมพ์เองเมื่อเลือก "อื่นๆ" เช่น "Assassin Cross" หรือ "Rebellion, Kagerou, Oboro"'},
    )
    n = len(armor) + 2
    number_validation(ws, 'F', 3, n, 0, 999, 'DEF')
    add_dropdown(ws, 'G', 3, n, JOBS, 'อาชีพ')

    ws = wb.create_sheet('README', 0)
    for line in [
        'วิธีกรอก',
        '1. กรอกเฉพาะคอลัมน์สีเหลือง (FIX_...) — คอลัมน์อื่นเป็นข้อมูลประกอบ ไม่ต้องแก้',
        '2. แถวที่ 2 ของแต่ละ sheet เป็นตัวอย่าง (ตัวเอียงสีเทา) ไม่ถูกนำเข้า',
        '3. ช่องที่มี dropdown: คลิกช่อง → กดลูกศรขวาของช่อง → เลือก  (พิมพ์เองไม่ได้ ระบบจะเตือน)',
        '4. ปล่อยว่างถ้าค่า "ตอนนี้" ถูกอยู่แล้ว หรือไม่แน่ใจ',
        '5. เซฟไฟล์ชื่อเดิม (data/review_items.xlsx) แล้วส่งกลับ หรือรัน:',
        '   python3 tools/export_review.py --import && python3 tools/convert_items.py && (cd server && bun run db:seed)',
        '',
        'sheet weapons: FIX_subType = ชนิดอาวุธ, FIX_weaponLevel = Lv 1–4 ของอาวุธ, FIX_atk = ATK',
        'sheet armor:   FIX_def = DEF, FIX_jobs = อาชีพที่ใส่ได้ (เลือก "อื่นๆ" แล้วพิมพ์ใน FIX_jobs_other ถ้าไม่มีในรายการ)',
    ]:
        ws.append([line])
    ws.column_dimensions['A'].width = 110
    ws['A1'].font = Font(bold=True, size=13)
    wb.move_sheet('lists', offset=len(wb.sheetnames))
    wb.save(XLSX)
    print(f'weapons {len(weapons)}, armor {len(armor)} → {XLSX}')


def import_fixes():
    wb = load_workbook(XLSX)
    overrides = json.load(open(OVERRIDES, encoding='utf-8')) if OVERRIDES.exists() else {}
    n = 0
    for name in ('weapons', 'armor'):
        ws = wb[name]
        headers = [c.value for c in ws[1]]
        for row in ws.iter_rows(min_row=3, values_only=True):  # row 2 is the example
            rec = dict(zip(headers, row))
            if not isinstance(rec.get('id'), int): continue
            fix = {}
            if rec.get('FIX_subType'): fix['subType'] = WEAPON_TYPES.get(str(rec['FIX_subType']).strip(), str(rec['FIX_subType']).strip().upper())
            if rec.get('FIX_weaponLevel') not in (None, ''):
                v = rec['FIX_weaponLevel']; fix['weaponLevel'] = WEAPON_LEVELS.get(str(v).strip(), int(str(v).strip().replace('Lv', '').strip()))
            if rec.get('FIX_atk') not in (None, ''): fix['atk'] = int(rec['FIX_atk'])
            if rec.get('FIX_def') not in (None, ''): fix['def'] = int(rec['FIX_def'])
            jobs = rec.get('FIX_jobs')
            if jobs:
                jobs = str(jobs).strip()
                fix['jobs'] = str(rec.get('FIX_jobs_other') or '').strip() if jobs.startswith('อื่นๆ') else jobs
                if not fix['jobs']: fix.pop('jobs')
            if not fix: continue
            overrides.setdefault(str(rec['id']), {}).update(fix); n += 1
    json.dump(overrides, open(OVERRIDES, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'{n} rows imported → {OVERRIDES} ({len(overrides)} items total)')


if __name__ == '__main__':
    import_fixes() if '--import' in sys.argv else export()
