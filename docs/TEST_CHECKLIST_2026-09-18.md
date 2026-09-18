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
| 1.13 | ใส่ **Drake Card** (#4137) ในอาวุธ | Equipment Status กลุ่ม Combat แสดง `✓ ยกเลิกโทษขนาดอาวุธ (ตีทุกขนาด 100%)` — เป็นธงแสดงผล ยังไม่ถูกใช้คำนวณดาเมจ (โปรแกรมยังไม่มีเป้าหมาย) · Madogum +9 / Piamette Hood +12 / Queen Anz Revenge ให้ธงเดียวกัน · Purified Knight's Shield แถว 3 มีตัวเลือก "Negates size penalty" |
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
| 2.7b | Zodiac Manteau +9 ใส่ **Spirit of Knight Lv.5** ในช่อง 2 | Combo ของผ้าคลุมเอง "เมื่อสวมใส่คู่กับ Spirit of Knight Lv.5" ทำงาน: Damage กายภาพ/เวท ทุกเผ่า = 7 (SoK) + **4** (combo) = 11% · ถ้าเป็น Lv.4 ได้แค่ 5% |
| 2.8 | **Infinity Boots** ทั้ง 6 | ช่อง 4: FS/EA/Spell/Vitality/Attack Speed/Lucky Lv.1–4 · ช่อง 3: Special 6 แบบ เปิดเมื่อช่อง 4 Lv.4 (Special ไม่รวมในผลรวม) |
| 2.9 | **4th ROC Anniversary Ring** | ช่อง 4/3: STR–LUK +3~+5 · ช่อง 2: Spell/Expert Archer/Fighting Spirit Lv.4–10 ไม่มีลำดับบังคับ |
| 2.10 | ถุงมือ/แหวนอื่นที่ไม่อยู่ในตาราง | **ไม่มี**ช่อง enchant |
| 2.11 | **Karasu / Crow Tengu Mask** (Middle) | 2 แถว Random Option: แถว 1 (8 ตัวเลือก), แถว 2 (เจาะเกราะ/โจมตี ทั่วไป/MVP) · เลือก "ลดระยะเวลาร่าย" พิมพ์ 25 → ถูกจำกัดเป็น 10 |
| 2.13 | **Incursion Temporal Manteau** (#480076) | 2 แถว Random Option (17 ตัวเลือก/แถว) ค่าอยู่ในช่วง เช่น ลดเวลาร่าย 3–10%, ATK 5–40 |
| 2.14 | **Incursion Temporal Boots** (#22202) | ช่อง 4: FS/EA/Spell/Vitality/Attack Speed/Lucky Lv.1–4 (เหมือน Infinity Boots) · ช่อง 3: Special เปิดเมื่อช่อง 4 Lv.4 |
| 2.15 | **Temporal Str Boots** ไม่มีช่อง (#22000 / #470159) | ช่อง 4 ครั้งที่ 1–4: FS ATK+15/18/21/24, Archery 2–8%, Spell MATK 9–18, Vital VIT+2/+3/MHP+1%/+2%, Attack Speed 4–10%, Lucky LUK+3–6 · ช่อง 3: Special · รุ่นมี [1] (#22006) **ไม่มี**ช่อง enchant (Socket แล้ว enchant ไม่ได้) |
| 2.16 | **Diabolus Boots** (#2433) | ช่อง 4 ครั้งที่ 1–4 (Lucky = CRI+1/2/5/7) · ช่อง 3 Special เมื่อช่อง 4 ครั้งที่ 4 |
| 2.17 | **Diabolus Ring** (#2729) | ช่อง 4: DEX+1~4 / INT+1~4 · ช่อง 3 (Archbishop 4Lv / ATK 7% / MATK 7%) ล็อกจนช่อง 4 เป็น +4 |
| 2.18 | **Diabolus Manteau** (#2537) +0 / +7 / +9 | ช่อง 4 → 3 → 2 เปิดตามตีบวก ชุดเดียวกับ Fallen Angel Wing (ช่อง 2 มี FS 6, Spell 7, EA 4, Fatal 4, MHP 4%, MSP 100, ASPD+1) |
| 2.19 | **Cursed / Bloody Knight's Shield** (#28942 / #28945) | 2 แถว Random Option (ลด Damage เผ่า 2–7%, Damage เผ่า 1–5%, VCT หรือ ASPD 1–5%, MaxHP 100–1000 …) · **Purified** (#28946) 3 แถว แถว 3 มีเจาะเกราะเผ่า 30–60% |
| 2.20 | **Ancient Hero weapons** (เช่น Awakened Narcissus Bow #700013, Royal Bow #18117) | 2 แถว Random Option แต่ละแถวมีตัวเลือก [Bravery] (กายภาพ) และ [Wisdom] (เวท) ตามหน้าโปรโมชัน |
| 2.21 | Archbishop 4Lv (enchant Diabolus Ring) | Heal +20% และใช้ SP เพิ่ม 15% (แดง) — เดิมอ่านผิดเป็น SP −20 |
| 2.12 | Save & Share แล้วเปิดลิงก์ใหม่ | การ์ด + enchant ทุกช่อง + Random Option กลับมาครบ |

แก้ตารางกฎได้ที่ `data/enchant_pools.json` เห็นผลทันทีโดยไม่ต้องรีสตาร์ท API (รีเฟรชหน้าเว็บ)

## 3. Awakened Class

| # | ทำอะไร | ที่คาดหวัง |
|---|---|---|
| 3.1 | เลือก **Awakened High Wizard** | Base Lv กรอกได้ถึง 120, Job 75 (hint "สูงสุด 120/75"), sprite = High Wizard |
| 3.2 | Base Lv 100 ขึ้นไป | slider สเตตัสไปถึง **120** (ตามที่พี่แจ้ง — หน้าเว็บพิมพ์ 130 ถ้าในเกมเป็น 130 บอกได้ แก้ตัวเลขเดียว); ลดเป็น Lv 99 → cap กลับเป็น 99 และค่าที่เกินถูกดึงลง |
| 3.2b | เลือก **Kagerou / Oboro / Rebellion** (2nd Extended) | Base Lv ถึง 120, Job 60, สเตตัสถึง 120 เมื่อ Lv ≥ 100 · Rebellion มี sprite ของตัวเอง, Kagerou/Oboro ใช้ sprite Ninja (client ไม่มี) · HP/SP ช่วง 100–120 เป็นค่าประมาณจาก Ninja/Gunslinger |
| 3.3 | สลับกลับเป็น High Wizard ขณะ Lv 120 | Lv ถูกดึงลง 99 / Job 70 |
| 3.4 | Awakened HW Lv120 AGI/DEX/INT 120 มือเปล่า | ASPD ≈ 184 (cap 193), HP ≈ 4,880 / SP ≈ 2,570 โดยประมาณ ก่อนใส่ของ — **HP/SP ช่วง Lv 100–120 เป็นค่าประมาณ** โปรดเทียบกับในเกมแล้วจดค่าจริงมา (บอก Lv, VIT, INT, MaxHP, MaxSP ถอดของ) |
| 3.5 | แถบแต้มสเตตัส | Lv99 อาชีพ High "มี 1,325", อาชีพอื่น/Awakened "มี 1,273", Awakened Lv120 "มี 1,765" — เกินแล้วเป็นสีแดง |
| 3.6 | Awakened Whitesmith / Creator | ASPD ยังใช้ตารางอาชีพฐาน (หน้าเว็บไม่มีรูป) |

## 4. สิ่งที่รอข้อมูลจากในเกม

- HP/SP จริงของ Awakened ที่ Lv 100 / 110 / 120 (สัก 1–2 อาชีพ)
- Job bonus stat ที่ Job 71–75 (Awakened) และ 51–60 ของ Kagerou/Oboro/Rebellion
- ยืนยัน: 1st Extended (Ninja, Gunslinger, Taekwon, Soul Linker, Star Gladiator, Super Novice) ยังเป็น Lv 99 / สเตตัส 99 ใช่ไหม และมี Star Emperor / Soul Reaper / Expanded Super Novice บน Gnjoy ไหม (client มี sprite ของ Star Emperor, Soul Reaper)
- Fallen Angel Wing: ตาราง Diabolus Manteau ยืนยันโครงสร้างเดียวกันแล้ว (ASPD 1–3 = Attack Delay) เหลือแค่ "MATK+30" ในช่อง 3 คือไอเทมตัวไหน
- Knight's Shield แถว 3: "Negates size penalty" ยังไม่รองรับ (ไม่มี key)
- Awakened Whitesmith/Creator: ตาราง ASPD จากในเกม
