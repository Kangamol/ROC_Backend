# Ragnarok Online Equipment Simulator Project Specifications

## Project Overview
This document outlines the technical architecture, database schema, data extraction pipeline, and implementation guide for building a custom **Ragnarok Online (RO) Visual & Equipment Simulator** tailored to official server databases (such as Gnjoy Classic).

---

## Tech Stack Summary

| Layer | Technology / Tool | Usage Description |
| :--- | :--- | :--- |
| **Frontend Framework** | **Vue.js 3** (Composition API) | Reactive UI components, state management for gear slots |
| **UI Library** | **Vuetify 3** | Material Design components, layout grids, dialogs, sliders |
| **Styling** | **CSS / SCSS** | Custom RO theme styling, slot overlays, item card tooltips |
| **Backend Framework** | **ElysiaJS** (Node.js/Bun) | High-performance RESTful API endpoints and WebSocket links |
| **Database ORM** | **Prisma ORM** | Type-safe query building, migrations, and schema definitions |
| **Database System** | **PostgreSQL** | Relational storage for Items, Cards, Stats, Builds, and Users |
| **Data Extraction** | **Python Scripting** | Extracting and parsing `.grf` and `iteminfo.lua` to JSON/SQL |

---

## 1. System Architecture Diagram

```
+-----------------------------------------------------------------------+
|                             CLIENT / BROWSER                          |
|  +-----------------------------------------------------------------+  |
|  |                 Vue 3 + Vuetify 3 Frontend App                   |  |
|  |  - Character Sheet / Equipment Slots                                |  |
|  |  - Stat Calculation Engine (ATK, DEF, ASPD, Cast Time)            |  |
|  |  - Item Picker & Search Dialog (with RO Icons & Tooltips)         |  |
|  |  - Build Saver / Shareable URLs                                     |  |
|  +-----------------------------------------------------------------+  |
+----------------------------------+------------------------------------+
                                   | HTTP REST / JSON
                                   v
+-----------------------------------------------------------------------+
|                          BACKEND SERVER (ElysiaJS)                    |
|  +---------------------+  +--------------------+  +-----------------+  |
|  | Item & Card Router  |  | Build Share Router |  | Auth / User     |  |
|  +---------------------+  +--------------------+  +-----------------+  |
|                                  | Prisma ORM                         |
+----------------------------------+------------------------------------+
                                   v
+-----------------------------------------------------------------------+
|                          DATABASE (PostgreSQL)                        |
|  - Items (ID, Name, Slots, Icon, Image, Script, ParsedStats)          |
|  - Cards (ID, Name, SlotType, ParsedStats)                            |
|  - ItemLocations (Equip location bitmasks)                            |
|  - SavedBuilds (Build JSON, Share Code, User Reference)               |
+-----------------------------------------------------------------------+
```

---

## 2. Local RO Client Data Extraction Pipeline

To populate your database with Gnjoy Classic client items:

```
+------------------+      +-------------------+      +-------------------+
|  Gnjoy RO Client | ---> |   GRF Editor      | ---> | Extracted Assets  |
|  (data.grf)      |      |   (GUI / CLI)     |      | - Icons (.png)    |
+------------------+      +-------------------+      | - iteminfo.lua    |
                                                     +---------+---------+
                                                               |
                                                               v
+------------------+      +-------------------+      +-------------------+
|  PostgreSQL      | <--- | Prisma Seed       | <--- | Python Parser     |
|  Database        |      | (Import DB Script)|      | (iteminfo.json)   |
+------------------+      +-------------------+      +-------------------+
```

### Extraction Steps:
1. **Extract Client Archive:** Use **GRF Editor** to unpack `data.grf` and patch `.gpf` files.
   - **Icons:** `data\texture\userinterface\item\*.bmp` (Convert to `.png`)
   - **Illustrations:** `data\texture\userinterface\collection\*.bmp`
   - **Metadata & Script:** `System\iteminfo.lua` (or `iteminfo.lub` using `unluac` decompiler).
2. **Execute Python Parser:** Read `iteminfo.lua`, extract Item IDs, names, resource icon names, and descriptions into a unified `items.json`.
3. **Execute Prisma Seed:** Load JSON into PostgreSQL database.

---

## 3. Database Schema (`schema.prisma`)

```prisma
datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

generator client {
  provider = "prisma-client-js"
}

enum EquipLocation {
  HEAD_TOP
  HEAD_MID
  HEAD_LOW
  ARMOR
  WEAPON
  SHIELD
  GARMENT
  SHOES
  ACCESSORY_1
  ACCESSORY_2
  AMMO
}

enum ItemType {
  WEAPON
  ARMOR
  CARD
  AMMO
  CONSUMABLE
  ETC
}

model Item {
  id              Int            @id
  identifiedName  String
  unidentifiedName String?
  resourceName    String
  slotCount       Int            @default(0)
  itemType        ItemType
  equipLocations  EquipLocation[]
  minLevel        Int            @default(1)
  weaponLevel     Int?
  atk             Int?
  matk            Int?
  def             Int?
  mdef            Int?
  description     String         @db.Text
  parsedStats     Json?          // E.g., {"str": 2, "atkPercent": 5}
  
  // Relations
  equipmentSlots  EquipmentSlot[]
  
  createdAt       DateTime       @default(now())
  updatedAt       DateTime       @updatedAt
}

model Card {
  id           Int      @id
  name         String
  resourceName String
  description  String   @db.Text
  parsedStats  Json?    // E.g., {"crit": 10, "raceBonus": {"demihuman": 20}}
  
  createdAt    DateTime @default(now())
}

model CharacterBuild {
  id          String   @id @default(uuid())
  shareCode   String   @unique
  title       String
  jobClass    String
  baseLevel   Int      @default(99)
  jobLevel    Int      @default(50)
  
  // Base Stats
  str         Int      @default(1)
  agi         Int      @default(1)
  vit         Int      @default(1)
  int         Int      @default(1)
  dex         Int      @default(1)
  luk         Int      @default(1)

  // Equipment Relations
  slots       EquipmentSlot[]

  createdAt   DateTime @default(now())
  updatedAt   DateTime @updatedAt
}

model EquipmentSlot {
  id          String        @id @default(uuid())
  buildId     String
  build       CharacterBuild @relation(fields: [buildId], references: [id], onDelete: Cascade)
  
  location    EquipLocation
  refineLevel Int           @default(0)
  
  itemId      Int?
  item        Item?         @relation(fields: [itemId], references: [id])
  
  card1Id     Int?
  card2Id     Int?
  card3Id     Int?
  card4Id     Int?

  @@unique([buildId, location])
}
```

---

## 4. Python Data Extraction Script (`parse_iteminfo.py`)

This script parses `iteminfo.lua` and exports structured `items.json` for database ingestion.

```python
import re
import json

def parse_iteminfo(file_path):
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    # Regex block pattern matching lua table entries
    item_blocks = re.findall(r'\[(\d+)\]\s*=\s*\{([^}]+)\}', content, re.DOTALL)
    
    items = []
    
    for item_id, body in item_blocks:
        unidentified_name = re.search(r'unidentifiedDisplayName\s*=\s*"([^"]+)"', body)
        identified_name = re.search(r'identifiedDisplayName\s*=\s*"([^"]+)"', body)
        resource_name = re.search(r'identifiedResourceName\s*=\s*"([^"]+)"', body)
        slot_count = re.search(r'slotCount\s*=\s*(\d+)', body)
        
        # Extract description lines
        desc_matches = re.findall(r'"([^"]+)"', re.search(r'identifiedDescriptionName\s*=\s*\{([^}]+)\}', body, re.DOTALL).group(1) if re.search(r'identifiedDescriptionName\s*=\s*\{([^}]+)\}', body, re.DOTALL) else "")
        description = "\n".join(desc_matches)

        items.append({
            "id": int(item_id),
            "identifiedName": identified_name.group(1) if identified_name else "Unknown",
            "unidentifiedName": unidentified_name.group(1) if unidentified_name else "",
            "resourceName": resource_name.group(1) if resource_name else "",
            "slotCount": int(slot_count.group(1)) if slot_count else 0,
            "description": description
        })

    with open('items.json', 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    print(f"Successfully extracted {len(items)} items to items.json")

if __name__ == "__main__":
    parse_iteminfo("iteminfo.lua")
```

---

## 5. Backend Server Implementation (`ElysiaJS`)

### API Route Setup (`src/index.ts`)

```typescript
import { Elysia, t } from 'elysia';
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();
const app = new Elysia();

// Search Items API
app.get('/api/items', async ({ query }) => {
  const { search, type, limit = '20' } = query;

  return await prisma.item.findMany({
    where: {
      AND: [
        search ? { identifiedName: { contains: search, mode: 'insensitive' } } : {},
        type ? { itemType: type as any } : {}
      ]
    },
    take: parseInt(limit),
    orderBy: { id: 'asc' }
  });
});

// Get Item Details by ID
app.get('/api/items/:id', async ({ params, error }) => {
  const item = await prisma.item.findUnique({
    where: { id: parseInt(params.id) }
  });
  if (!item) return error(404, 'Item not found');
  return item;
});

// Save Character Build API
app.post('/api/builds', async ({ body }) => {
  const { title, jobClass, baseLevel, jobLevel, stats, slots } = body;
  const shareCode = Math.random().toString(36).substring(2, 8);

  const build = await prisma.characterBuild.create({
    data: {
      shareCode,
      title,
      jobClass,
      baseLevel,
      jobLevel,
      str: stats.str,
      agi: stats.agi,
      vit: stats.vit,
      int: stats.int,
      dex: stats.dex,
      luk: stats.luk,
      slots: {
        create: slots.map((s: any) => ({
          location: s.location,
          refineLevel: s.refineLevel,
          itemId: s.itemId,
          card1Id: s.card1Id,
          card2Id: s.card2Id,
          card3Id: s.card3Id,
          card4Id: s.card4Id
        }))
      }
    },
    include: { slots: true }
  });

  return { shareCode: build.shareCode };
});

app.listen(3000, () => {
  print("ElysiaJS Backend running on port 3000");
});
```

---

## 6. Frontend Implementation (`Vue 3 + Vuetify 3`)

### Item Slot Component (`EquipmentSlot.vue`)

```vue
<template>
  <v-card class="equipment-slot pa-2" variant="outlined">
    <div class="d-flex align-center gap-3">
      <!-- Item Icon Box -->
      <div class="icon-box elevation-2">
        <v-img
          v-if="item"
          :src="`/assets/items/${item.resourceName}.png`"
          width="24"
          height="24"
          alt="Item Icon"
        />
        <v-icon v-else color="grey-lighten-1">mdi-shield-outline</v-icon>
      </div>

      <!-- Item Info -->
      <div class="flex-grow-1">
        <div class="text-caption font-weight-bold text-grey">{{ label }}</div>
        <div class="text-body-2 text-truncate font-weight-medium">
          <span v-if="refine > 0" class="text-amber-darken-2">+{{ refine }} </span>
          {{ item ? item.identifiedName : 'Empty' }}
        </div>
      </div>

      <!-- Actions -->
      <v-btn icon size="small" variant="text" @click="$emit('select-item')">
        <v-icon>mdi-pencil</v-icon>
      </btn>
    </div>
  </v-card>
</template>

<script setup lang="ts">
defineProps<{
  label: string;
  item?: { id: number; identifiedName: string; resourceName: string };
  refine?: number;
}>();

defineEmits(['select-item']);
</script>

<style scoped lang="scss">
.equipment-slot {
  border-color: rgba(255, 255, 255, 0.12);
  background: rgba(30, 30, 40, 0.6);
  backdrop-filter: blur(8px);

  .icon-box {
    width: 36px;
    height: 36px;
    background: #141419;
    border: 1px solid #3a3a4c;
    border-radius: 4px;
    display: flex;
    align-items: center;
    justify-content: center;
  }
}
</style>
```

---

## 7. Custom Styling & Theme (SCSS)

```scss
// styles/ro-theme.scss
$ro-primary: #3f51b5;
$ro-accent: #ffd54f;
$ro-bg-dark: #121218;
$ro-card-bg: #1e1e28;

body {
  background-color: $ro-bg-dark;
  color: #e0e0e0;
  font-family: 'Roboto', sans-serif;
}

// Custom RO Item Tooltip Style
.ro-item-tooltip {
  background: rgba(16, 16, 24, 0.95) !important;
  border: 1px solid #4a4a60 !important;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5);
  border-radius: 6px;
  padding: 12px;

  .item-title {
    color: $ro-accent;
    font-weight: 700;
    font-size: 1rem;
  }

  .item-desc {
    color: #b0b0c0;
    font-size: 0.85rem;
    white-space: pre-line;
  }
}
```

---

## 8. Development Roadmap

1. **Phase 1: Assets & Data Extraction**
   - Unpack `data.grf` from local client using GRF Editor.
   - Run `parse_iteminfo.py` to extract all item data.
   - Set up PostgreSQL and seed initial items and cards.
2. **Phase 2: Core Backend Engine**
   - Implement ElysiaJS REST API for item query and character build saving.
   - Setup Prisma schema migrations.
3. **Phase 3: Frontend Interactive Simulator**
   - Build Vue 3 + Vuetify 3 gear slots and stat calculation sheet.
   - Add item selection dialogs with search and slot filtering.
   - Implement stat calculation logic (ATK, DEF, Hit, Flee, ASPD).
4. **Phase 4: Optimization & Deployment**
   - WebP image compression for extracted item icons.
   - Docker containerization for ElysiaJS and PostgreSQL.
