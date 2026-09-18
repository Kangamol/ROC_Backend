# รายการทดสอบ — งานวันที่ 18 ก.ย. 2026

ใช้ทดสอบบนเครื่องอื่นหลัง `git pull` ทั้ง 2 repo (backend = root, frontend = `web/`)

## 0. เตรียมเครื่อง (ครั้งแรกหลัง pull)

```bash
docker compose up -d
cd server
cp .env.example .env            # ถ้ายังไม่มี — ถ้าลงเกมไว้ให้เพิ่ม GRF_PATH="…/data.grf"
bun install
bunx prisma migrate dev         # มี migration ใหม่: add_random_options
bun run db:seed                 # โหลด items.json รอบล่าสุด
bun run setup:check             # ต้อง ✔ ทุกข้อ (sprite ⚠ ได้ถ้าไม่มี data.grf)
bun run dev
cd ../web && bun install && bun run dev
```

- [ ] `setup:check` ผ่าน: .env, DB มี 11,154 items, ไอคอน 11,117 ไฟล์ (มาจาก git แล้ว ไม่ต้องแตกจาก client)
- [ ] ถ้าตั้ง `GRF_PATH` → รัน `python3 tools/build_grf_index.py` แล้ว log server ขึ้น `sprites: serving from …` และ Preview ตัวละครขึ้น
- [ ] เปิด http://localhost:5173 รูปไอเทมใน picker ขึ้นครบ

## 1. เงื่อนไขไอเทม (parser + engine)

| # | ทำอะไร | ที่คาดหวัง |
|---|---|---|
| 1.1 | ใส่ **Magician's Gloves [1]** (#490829) ที่ Accessory, Base Lv 99 | Equipment Status: MATK +30, ลดร่าย 10%, เพิกเฉย MDEF ทุกเผ่า 50%, Damage เวท Fire/Water/Wind **+49%** (floor(99/2)) |
| 1.2 | ตีบวกถุงมือ +5 / +7 / +9 | +5: MDEF +30, SP Recovery 200% · +7: Damage เวททุกเผ่า +10% · +9: Damage เวท Boss +20% |
| 1.3 | ใส่ **High Wizard Card** ใน**หมวก** (ไม่ใช่ที่ถุงมือ) | Set bonus "Magician's Gloves + High Wizard Card" ทำงาน: INT +10 และลดร่ายรวม 10+30−100 = **เพิ่มระยะเวลาร่าย 60%** (แดง), ฟื้น SP −100% (แดง), เพิกเฉย MDEF = **100%** (ไม่เกิน 100) |
| 1.4 | ใส่ **4th ROC Anniversary Ring** (#490826) Base STR 89 → 90 | 89: ไม่มี Damage ทุกขนาด · 90: Damage กายภาพทุกขนาด +8% (ใช้ **Base** STR ไม่รวมโบนัส) |
| 1.5 | แหวน +7, Base LUK 90 | ATK +15+25, MATK +15+25, Crit Damage +10% |
| 1.6 | **Pisces Diadem [1]** (#401288) Base AGI 89 → 90 | 89: ลดร่าย 10% · 90: ลดร่าย **40%** |
| 1.7 | Pisces Diadem +11 | Damage เวท**ไร้ธาตุ** +20% และ ธาตุน้ำ +20% |
| 1.8 | **Sealed High Wizard Card** +0 / +15 | +0: เพิ่มร่าย 150% · +15: เพิ่มร่าย **120%** (แทนที่ ไม่ใช่บวกเพิ่ม) |
| 1.9 | Infinity Intelligence Boots +11 + Costume Garment ใส่ **Casting Stone (Garment)** | Fixed Cast (items) = **−1.0 วินาที** (0.5 + 0.5) |
| 1.10 | Fenrir Card (Fixed 70%) + อีกชิ้นที่มี Fixed % | Fixed Cast % ใช้ค่า**สูงสุด**ตัวเดียว ไม่บวกกัน (วินาทีบวกกันได้) |
| 1.11 | Costume Upper ใส่ **Champion Stone (Upper)** | ไม่รวมในผลรวม แต่โชว์ในกล่อง "โบนัสตามเลเวลสกิล — ยังไม่รวมในผลรวม": `[ทุก ๆ 1 Lv ของ Iron Hand] +2 ATK` |
| 1.12 | ดูสี | ค่าบวก = เขียว, ค่าลบ = แดง ทั้ง Equipment Status, แถว Cast/Delay ใน Stats, และตัวเลขโบนัสข้างสเตตัส |

## 2. Enchant NPC

| # | ทำอะไร | ที่คาดหวัง |
|---|---|---|
| 2.1 | ใส่ Armor ทั่วไป (เช่น Cotton Shirts [1]) | มีชิป enchant 1 ช่อง (Hidden Enchant) picker เสนอ STR–LUK +1~+3, สวิตช์ "แสดง enchant ทั้งหมด" เห็นครบ 330 |
| 2.2 | **Fallen Angel Wing [1]** +0 / +7 / +9 | ช่อง 4 เปิดที่ +0, ช่อง 3 ที่ +7, ช่อง 2 ที่ +9 (แม่กุญแจบอกเหตุผล) — ลดตีบวกลง enchant ช่องที่ไม่ถึงเงื่อนไขหลุดเอง |
| 2.3 | FAW +9 ใส่ Fighting Spirit 5Lv / Spell 6Lv / ATK+5% + การ์ดช่อง 1 | ATK +18 HIT +5, MATK +21 ลดร่าย 10%, ATK +5% และการ์ดยังอยู่ (enchant นับจากช่องท้าย 4→3→2) |
| 2.4 | **Capricorn Crown [1]** (#401198) | ช่อง 4: Mettle/Affection/Magic Essence/Adamantine/Acute/Master Archer Lv.1–4 · ช่อง 3 ล็อกจน**ช่อง 4 เป็น Lv.4** · ช่อง 3 มีแค่ Capricorn Gem |
| 2.5 | Capricorn Crown +7 + Mettle Lv.4 + Capricorn Gem | ATK +16% HIT +40, DEX +2, ASPD +10%, Damage Meteor Storm **+70%** (10%×7) — ตี +10 → +100% |
| 2.6 | **Zodiac Mail** (เช่น Capricorn Mail #450545) +8 → +9 | +8 ล็อกทุกช่อง · +9 เปิดช่อง 4 · ใส่ Hit Plus 2 ช่อง 3 ยังล็อก · Hit Plus 5 เปิด · ช่อง 3 SP+100 → ช่อง 2 เปิด (14 Memory) |
| 2.7 | **Zodiac Manteau** (#480880–480892) +9 | ช่อง 4/3: Expert Archer/Fighting Spirit/Expert Magician/Spell/Attack Delay/LUK สายอัพ · ช่อง 2: Spirit of Knight Lv.1–5 เปิดเมื่อ 4 และ 3 ระดับสูงสุด |
| 2.8 | **Infinity Boots** ทั้ง 6 | ช่อง 4: FS/EA/Spell/Vitality/Attack Speed/Lucky Lv.1–4 · ช่อง 3: Special 6 แบบ เปิดเมื่อช่อง 4 Lv.4 (Special ไม่รวมในผลรวม) |
| 2.9 | **4th ROC Anniversary Ring** | ช่อง 4/3: STR–LUK +3~+5 · ช่อง 2: Spell/Expert Archer/Fighting Spirit Lv.4–10 ไม่มีลำดับบังคับ |
| 2.10 | ถุงมือ/แหวนอื่นที่ไม่อยู่ในตาราง | **ไม่มี**ช่อง enchant |
| 2.11 | **Karasu / Crow Tengu Mask** (Middle) | 2 แถว Random Option: แถว 1 (8 ตัวเลือก), แถว 2 (เจาะเกราะ/โจมตี ทั่วไป/MVP) · เลือก "ลดระยะเวลาร่าย" พิมพ์ 25 → ถูกจำกัดเป็น 10 |
| 2.12 | Save & Share แล้วเปิดลิงก์ใหม่ | การ์ด + enchant ทุกช่อง + Random Option กลับมาครบ |

แก้ตารางกฎได้ที่ `data/enchant_pools.json` เห็นผลทันทีโดยไม่ต้องรีสตาร์ท API (รีเฟรชหน้าเว็บ)

## 3. Awakened Class

| # | ทำอะไร | ที่คาดหวัง |
|---|---|---|
| 3.1 | เลือก **Awakened High Wizard** | Base Lv กรอกได้ถึง 120, Job 75 (hint "สูงสุด 120/75"), sprite = High Wizard |
| 3.2 | Base Lv 100 ขึ้นไป | slider สเตตัสไปถึง **130**; ลดเป็น Lv 99 → cap กลับเป็น 99 และค่าที่เกินถูกดึงลง |
| 3.3 | สลับกลับเป็น High Wizard ขณะ Lv 120 | Lv ถูกดึงลง 99 / Job 70 |
| 3.4 | Awakened HW Lv120 AGI/DEX/INT 130 มือเปล่า | ASPD ≈ 184.9 (cap 193), HP ≈ 4,906 / SP ≈ 2,681 ก่อนใส่ของ — **HP/SP ช่วง Lv 100–120 เป็นค่าประมาณ** โปรดเทียบกับในเกมแล้วจดค่าจริงมา (บอก Lv, VIT, INT, MaxHP, MaxSP ถอดของ) |
| 3.5 | แถบแต้มสเตตัส | Lv99 อาชีพ High "มี 1,325", อาชีพอื่น/Awakened "มี 1,273", Awakened Lv120 "มี 1,765" — เกินแล้วเป็นสีแดง |
| 3.6 | Awakened Whitesmith / Creator | ASPD ยังใช้ตารางอาชีพฐาน (หน้าเว็บไม่มีรูป) |

## 4. สิ่งที่รอข้อมูลจากในเกม

- HP/SP จริงของ Awakened ที่ Lv 100 / 110 / 120 (สัก 1–2 อาชีพ)
- Job bonus stat ที่ Job 71–75
- ยืนยัน Fallen Angel Wing: "ASPD 1–3" = Attack Delay 1–3 (ASPD +4/6/8%) ใช่ไหม และ "MATK+30" ในช่อง 3 คือไอเทมตัวไหน
- Awakened Whitesmith/Creator: ตาราง ASPD จากในเกม
