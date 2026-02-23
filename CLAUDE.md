# CLAUDE.md — BIO Dashboard
# Version: 3.1

---

## 1. Project

- **App**: BIO Unified Report Dashboard — วิเคราะห์ข้อมูล Bio card issuance & SLA tracking
- **Stack**: Streamlit 1.33+ / SQLAlchemy ORM / Supabase PostgreSQL / Plotly / ECharts
- **Hosting**: Streamlit Cloud (auto-deploy on push to main)
- **Supabase MCP**: ใช้ `list_projects` ก่อนเสมอ ห้าม hardcode project_id (อาจเปลี่ยน)
- **Repo**: https://github.com/ytsp18/bio-dashboard.git
- **Version file**: `__version__.py` (ปัจจุบัน 2.3.4)
- **Data update**: วันละครั้ง — ไม่ใช่ realtime → cache ttl ควรเป็น 1 ชั่วโมงขึ้นไป

---

## 2. Language & Commits

- สื่อสารกับผู้ใช้เป็น **ภาษาไทย**
- Code, comments, commit messages → **ภาษาอังกฤษ**
- Commit format: action-oriented (เช่น `Fix SLA calculation`, `Add forecast page`)
- ทุก release: bump `__version__.py` + อัปเดต `Documentation/CHANGELOG.md`

---

## 3. Code Rules

### Security (ห้ามข้าม)
- ทุก user input ต้องผ่าน `utils/security.py` (sanitize + validate)
- SQL: ใช้ **SQLAlchemy parameterized queries เท่านั้น** ห้ามเขียน raw SQL string
- Credentials: ใช้ `st.secrets` หรือ environment variables ห้าม hardcode
- Audit: ทุก action สำคัญ (login, upload, delete) ต้อง log ผ่าน `AuditLog` model

### Database
- แก้ schema → ต้องอัปเดต `database/models.py` + เพิ่ม migration ใน `database/connection.py`
- ใช้ connection pooling (Supabase Session Pooler) อย่าสร้าง connection ใหม่เอง

### Streamlit
- ใช้ `@st.cache_data(ttl=3600)` สำหรับ data queries (ข้อมูลอัปเดตวันละครั้ง → ttl 1 ชั่วโมงขึ้นไป)
- ใช้ `@st.cache_resource` สำหรับ DB connections
- ใช้ `@st.fragment` สำหรับ component ที่ update บ่อยเพื่อลด full rerun
- Import ORM models ใน cached function ต้องใช้ **local import** (ไม่งั้น cache จะ break)

### Branch Display Names
- ใช้ `utils/branch_display.py` → `get_branch_short_name(branch_code, branch_name)` แทน truncation ทุกที่
- ห้าม truncate ชื่อศูนย์ (`branch_name[:50]`) — ใช้ short name แทนเสมอ
- `get_branch_short_name_map()` = cached dict {branch_code: short_name} ดึงจาก DB
- BKK มี 10 ศูนย์ SC — ต้องจำแนกด้วยเลข + สถานที่ + Non-B tag
- จังหวัดที่มีหลายศูนย์ SC: BKK(10), CBI(3), RNG(2), TAK(2)

### Page Order (v2.3.4+)
| # | Page | File |
|---|------|------|
| 0 | Register | `0_📝_Register.py` |
| 1 | Upload | `1_📤_Upload.py` |
| 2 | Overview | `2_📈_Overview.py` |
| 3 | Forecast | `3_📆_Forecast.py` |
| 4 | Queue Slots | `4_🎯_Queue_Slots.py` |
| 5 | Search | `5_🔍_Search.py` |
| 6 | By Center | `6_🏢_By_Center.py` |
| 7 | Anomaly | `7_⚠️_Anomaly.py` |
| 8 | Raw Data | `8_📋_Raw_Data.py` |
| 9 | Complete Diff | `9_📊_Complete_Diff.py` |
| 10 | Admin | `10_👤_Admin.py` |
| 11 | Profile | `11_🔐_Profile.py` |

### General
- อ่าน function ที่เกี่ยวข้องก่อนแก้เสมอ — ห้ามเดา
- ห้ามเปลี่ยน architecture โดยไม่ได้รับอนุมัติ
- ห้าม force push, drop table โดยไม่ถาม
- PII data → ห้าม log, ห้าม hardcode, ห้ามแสดงใน analytics

### File Dependencies (ต้องแก้คู่กัน)
| ถ้าแก้ | ต้องเช็ค |
|--------|---------|
| `database/models.py` | `database/connection.py` (migration), `services/data_service.py` (queries) |
| `services/excel_parser.py` | `pages/1_📤_Upload.py` |
| `auth/*` | `pages/10_👤_Admin.py`, `pages/11_🔐_Profile.py` |
| `utils/metric_cards.py` | `pages/2_📈_Overview.py`, `pages/6_🏢_By_Center.py` |
| `utils/branch_display.py` | ทุก page ที่แสดงชื่อศูนย์ (7 pages) |
| `utils/security.py` | ทุก page ที่รับ input |
| `services/data_service.py` | ทุก page ที่แสดงข้อมูล |
| `pages/4_🎯_Queue_Slots.py` | `database/models.py` (Card, Appointment, BranchMaster), `database/connection.py` (partial index) |

---

## 4. Issue Scanning

เมื่อแตะโค้ด ให้สแกนปัญหาตาม 4 ระดับ:

- 🔴 **Critical** (แจ้งทันที): SQL injection, credential leak, data loss risk
- 🟠 **Performance** (แจ้งพร้อมผลกระทบ): N+1 queries, missing index, no caching, ไม่มี pagination
- 🟡 **Quality** (เสนอเมื่อเหมาะสม): function >50 lines, duplication, empty except blocks
- 🟢 **Minor** (แก้เลยได้): formatting, import order

**Protocol**: ทำงานที่สั่งให้เสร็จก่อน → สแกน → แจ้งสั้นๆ → รออนุมัติก่อนแก้ (ยกเว้น 🟢)

---

## 5. Testing & Deploy

### Local Testing
```bash
cd "/Users/tanapongsophon/Desktop/Claude/Bio merged/bio_dashboard"
streamlit run app.py
```
- ทดสอบผ่าน Chrome (ใช้ Chrome MCP extension)

### Checklist ก่อน Deploy
1. Feature ทำงานถูกต้อง
2. Edge cases ผ่าน (ข้อมูลว่าง, ข้อมูลซ้ำ, file format ผิด)
3. Security — input sanitized, permissions ถูกต้อง
4. ข้อมูลเดิมใน DB ไม่เสียหาย
5. Pages ที่เกี่ยวข้องยังทำงานปกติ

### Deploy
1. Bump version ใน `__version__.py`
2. อัปเดต `Documentation/CHANGELOG.md` + `Documentation/SESSION_LOG.md`
3. `git push origin main` → Streamlit Cloud auto-deploy

---

## 6. Common Mistakes (บทเรียนจริง)

| ผิดพลาด | ผลกระทบ | ป้องกัน |
|---------|---------|---------|
| ลืม bump `__version__.py` | User ไม่รู้ว่า deploy version ไหน | เช็คทุกครั้งก่อน push |
| แก้ `models.py` ไม่เพิ่ม migration | App crash เพราะ column ไม่ตรง | เช็ค `connection.py` ทุกครั้ง |
| ใช้ raw SQL string | SQL injection risk | ใช้ SQLAlchemy ORM เท่านั้น |
| ลืม `@st.cache_data` | Query ซ้ำทุก rerun, app ช้า | เพิ่ม cache ทุก query function |
| Import model ที่ top-level ใน cached fn | Streamlit cache break | ใช้ local import ข้างใน function |
| แก้ page ใหญ่ (By_Center 65K) ไม่ grep ก่อน | แก้ผิดที่, context เต็ม | `grep -n` หา function ก่อน |
| ลืมเช็ค role permission | Feature เปิดให้ role ที่ไม่ควรเห็น | เช็ค `auth/permissions.py` ก่อนเพิ่ม feature |
| ใช้ `JsCode()` ใน `st_echarts` | MarshallComponentException บน Cloud | ใช้ string template (`{b}`, `{c}`) + piecewise visualMap แทน |
| สร้าง HTML จาก DB data ไม่ escape | XSS / HTML injection | ใช้ `html.escape()` กับทุก user data ใน HTML |
| เพิ่ม index ใน Supabase ไม่รัน ANALYZE | Planner เลือก index เก่า, query ช้า | รัน `ANALYZE tablename;` หลังเพิ่ม index |
| ตัดชื่อศูนย์ `branch_name[:50]` | ชื่อจังหวัดหายไป อ่านไม่ออก | ใช้ `get_branch_short_name()` จาก `utils/branch_display.py` |
| ตั้ง cache ttl สั้นเกินไป (เช่น 300s) | Query DB บ่อยเกินจำเป็น (ข้อมูลอัปเดตวันละครั้ง) | ใช้ `ttl=3600` (1 ชั่วโมง) ขึ้นไป |
| ECharts visualMap ทับกราฟ | Legend ซ้อนทับ chart content | ใช้ `"show": False` + HTML legend แยกด้านล่าง |
| ย้ายหน้า page ไม่อัปเดต File Dependencies | CLAUDE.md อ้างถึง file number เก่า | อัปเดตทุกที่ที่อ้างชื่อไฟล์ page |
