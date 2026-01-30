# Session Log - 31 Jan 2026

## สิ่งที่ทำเสร็จแล้ว (31 Jan 2026 - Session 5: Workload Forecast)

### 14. Workload Forecast Feature (นัดหมายล่วงหน้า)

**ความต้องการ:**
- แสดงปริมาณการนัดหมายล่วงหน้าเพื่อเตรียมรับมือ
- เปรียบเทียบกับ Capacity จาก BranchMaster

**สิ่งที่พัฒนา:**

1. **Function `get_upcoming_appointments()`** (Overview.py)
   - Query นัดหมายที่มี `appt_date >= today` และ `appt_status IN ('SUCCESS', 'WAITING')`
   - รวม `total_capacity` จาก `BranchMaster.max_capacity`
   - คำนวณ usage_pct และ status (over/warning/normal)

2. **Summary Section ใน Overview**
   - Metrics: วันนี้, พรุ่งนี้, 7 วัน, 30 วัน
   - กราฟแท่งรายวัน + เส้น Capacity (เขียว) + เส้นค่าเฉลี่ย (แดง)
   - Link ไปหน้ารายละเอียด

3. **หน้า "ปริมาณการนัดหมาย"** (3_📆_Forecast.py)
   - Tab รายวัน: กราฟแยก OB และ SC พร้อม Capacity line แยก
   - Tab รายศูนย์: Treemap + Horizontal bar chart + ตาราง Capacity
   - Tab ตารางรายละเอียด: Pivot table (ศูนย์ × วัน) + Export CSV

4. **Treemap Visualization**
   - ขนาดกล่อง = ปริมาณนัดหมาย
   - สี = สถานะ (🟢 ปกติ, 🟡 ใกล้เต็ม, 🔴 เกิน, ⚫ ไม่มี Capacity)
   - แสดง branch_code ในกล่อง
   - Tooltip แสดงรายละเอียดครบ (ชื่อเต็ม, นัดหมาย, Capacity, %)
   - สลับ มุมมองรายวัน/รายเดือน
   - กรองตามประเภทศูนย์ (ทั้งหมด, OB, SC)

5. **แยกกราฟตามประเภทศูนย์**
   - Chart 1: ศูนย์แรกรับ (OB) - สีม่วง + Capacity OB (เขียว)
   - Chart 2: ศูนย์บริการ (SC) - สีฟ้า + Capacity SC (เขียว)
   - แต่ละกราฟมีเส้นค่าเฉลี่ย (แดงประ)

**Bug Fix:**
- JSON Serialization Error: ลบ lambda formatter ใน ECharts tooltip
- Mobile Unit Detection: เปลี่ยนจาก `startswith('MB-')` เป็น `'-MB-' in branch_code`
- Total Capacity: 24,860 → 12,540 (ไม่รวม 77 หน่วยเคลื่อนที่)

**Menu Reorder:**
- เปลี่ยน Forecast จาก 2.5_ เป็น 3_ ให้อยู่หลัง Overview
- Rename ไฟล์ทั้งหมด: Search (4_), By Center (5_), Anomaly (6_), etc.

**Git Commits:**
| Commit | Description |
|--------|-------------|
| `1d42cfd` | Add Workload Forecast feature |
| `7552cc8` | Fix WAITING status for upcoming appointments |
| `7e3f5bf` | Rename Forecast page, change title |
| `de16482` | Add capacity limit line to charts, reorder menu |
| `ea86d21` | Split daily chart into separate OB and SC charts |
| `f2d3038` | Treemap: show branch_code in box, full name in tooltip |

**Version:** 1.3.8

---

## สิ่งที่ทำเสร็จแล้ว (31 Jan 2026 - Session 4: Security Audit)

### 13. Security Audit & SQL Injection Fix

**ปัญหาที่พบ:**
1. **SQL Injection Vulnerability (HIGH RISK)**
   - ไฟล์: `database/connection.py`
   - ใช้ f-string สร้าง SQL queries กับ user input โดยตรง
   - ตัวอย่างโค้ดที่มีปัญหา:
   ```python
   # ❌ Vulnerable
   query = f"SELECT * FROM cards WHERE serial_number LIKE '%{search_term}%'"
   ```

2. **Credential Exposure**
   - รหัสผ่าน database ควรถูก rotate หลังพบ vulnerability

**วิธีแก้ไข:**
1. **SQL Injection Fix**
   - เปลี่ยนเป็น parameterized queries ด้วย SQLAlchemy `text()` และ `:param`
   ```python
   # ✅ Safe
   query = text("SELECT * FROM cards WHERE serial_number LIKE :search")
   result = session.execute(query, {"search": f"%{search_term}%"})
   ```
   - Commit: `afdeb03`

2. **Credential Rotation**
   - รหัส database เปลี่ยนจาก `kadxa1-Pupfyv-tajgyd` → `qiqma7-baKzax-wetbeh`
   - Cookie key ใหม่: 64-char hex
   - อัปเดต Streamlit Cloud secrets

**ปัญหาที่เจอระหว่างแก้ไข:**
- "Circuit breaker open" error - IP ถูก ban จาก Supabase
- แก้โดย Unban IP จาก Network Bans + รอ circuit breaker reset
- Restart database เพื่อ clear connection pool

**ผลลัพธ์:**
- ✅ SQL Injection fixed
- ✅ Credentials rotated
- ✅ Database connection restored
- ✅ App ใช้งานได้ปกติ

---

## สิ่งที่ทำเสร็จแล้ว (31 Jan 2026 - Session 3)

### 9. PostgreSQL COPY Protocol สำหรับ Upload เร็วขึ้น 10-50x

**ปัญหา:** Upload ไฟล์ 6.4MB ช้ามาก (stuck ที่ 30%)

**สาเหตุ:** SQLAlchemy `insert()` มี overhead จาก parameter binding

**วิธีแก้ไข:** เปลี่ยนเป็น PostgreSQL `COPY FROM STDIN WITH CSV`

```python
from io import StringIO
buffer = StringIO()
import_df[columns].to_csv(buffer, index=False, header=False, na_rep='\\N')
buffer.seek(0)
cursor.copy_expert("""
    COPY table_name (columns...)
    FROM STDIN WITH (FORMAT CSV, NULL '\\N')
""", buffer)
```

**ผลลัพธ์:**
| ไฟล์ | Records | สถานะ |
|------|---------|-------|
| 6.4MB | 24K | ✅ เร็วขึ้นมาก |
| 17MB | 66K | ✅ สำเร็จ |
| 31MB | 130K | ✅ สำเร็จ |

---

### 10. Card Delivery Upload Support

**เพิ่ม Tab ใหม่:** 📦 Card Delivery

**รูปแบบข้อมูล:**
- Appointment ID ขึ้นต้นด้วย 68/69 (ไม่ใช่รูปแบบปกติ)
- ไม่มี SLA time data
- มี `alien_card_id` แทน `card_id`

**Database Models:**
- `CardDeliveryUpload` - metadata การ upload
- `CardDeliveryRecord` - ข้อมูลการจัดส่งบัตร

**ทดสอบ:** 196 records (G: 191, B: 5) ✅ สำเร็จ

---

### 11. Duplicate Data Check

**กฎการตรวจสอบ:**

| ประเภท | Unique Key | พบซ้ำ |
|--------|------------|-------|
| Appointment | `appointment_id` | ❌ บล็อก + ปุ่ม disabled |
| QLog | `qlog_id` | ❌ บล็อก + ปุ่ม disabled |
| Card Delivery | `serial_number` | ❌ บล็อก + ปุ่ม disabled |
| Bio Raw | `serial_number + print_status` | ⚠️ Warning เท่านั้น |

**หมายเหตุ:** Bio Raw อนุญาตซ้ำเพราะ serial เดียวกันอาจมีหลาย status (G→B, B→G) สำหรับ verify

---

### 12. Bug Fix: emergency column type error

**อาการ:** `invalid input syntax for type integer: "0.0"`

**สาเหตุ:** Excel data มี float (0.0) แต่ PostgreSQL COPY ต้องการ integer

**วิธีแก้ไข:**
```python
copy_df['emergency'] = copy_df['emergency'].apply(lambda x: int(x) if pd.notna(x) else None)
```

---

### Version Update: 1.3.6

**ไฟล์ที่แก้ไข:**
- `pages/1_📤_Upload.py` - COPY protocol, duplicate check, Card Delivery tab
- `database/models.py` - CardDeliveryUpload, CardDeliveryRecord
- `database/connection.py` - ลบ unique constraint migrations
- `__version__.py` - 1.3.6
- `CHANGELOG.md` - บันทึกการเปลี่ยนแปลง

---

## สิ่งที่ทำเสร็จแล้ว (31 Jan 2026 - Session 2)

### 7. แก้ไข FK Violation และเพิ่มความเร็ว Upload

#### ปัญหา: ForeignKeyViolation
**อาการ:** `psycopg2.errors.ForeignKeyViolation: Key (upload_id)=(X) is not present in table`

**สาเหตุ:** การใช้ `to_sql()` หรือ `COPY` command สร้าง connection ใหม่ที่มองไม่เห็น uncommitted FK rows

**วิธีแก้ไข:** กลับไปใช้ `session.execute(insert(Model), batch)` ซึ่งทำงานใน transaction เดียวกัน

```python
from sqlalchemy import insert
session.execute(insert(Appointment), batch)
session.commit()
```

---

#### การปรับปรุง Performance

| Tab | Batch Size เดิม | Batch Size ใหม่ | รอบ insert (3000 records) |
|-----|-----------------|-----------------|---------------------------|
| Appointment | 100 → 1000 | **5,000** | 1 รอบ |
| QLog | 100 → 500 | **4,000** | 1 รอบ |
| Bio Raw | 100 → 400 | **3,000** | 1 รอบ |

---

### 8. รองรับไฟล์ขนาดใหญ่ 30MB+

**การปรับปรุง:**
- เพิ่ม `gc.collect()` ทุก 10 batches เพื่อคืน memory
- ใช้ `low_memory=False` สำหรับไฟล์ใหญ่
- ใช้ `iloc` slicing แทนการแปลง dict ทั้งหมดในครั้งเดียว
- ลบ DataFrame หลัง import เสร็จ

```python
for batch_num in range(total_batches):
    batch_df = import_df.iloc[start_idx:end_idx]
    batch = batch_df.to_dict('records')
    session.execute(insert(Model), batch)

    if batch_num % 10 == 0:
        gc.collect()

# Free memory after import
del import_df, df
gc.collect()
```

**Config:**
- `maxUploadSize = 200 MB` ใน `.streamlit/config.toml`

---

### Git Commits (31 Jan 2026 - Session 2)
| Commit | Description |
|--------|-------------|
| `fbf9cbe` | Optimize upload for large files 30MB+ |
| `306435d` | Increase batch sizes significantly for faster uploads |
| `449d240` | Increase batch sizes for faster upload |
| `dd692eb` | Revert to session-based insert to fix FK violation |
| `ecace76` | Switch to pandas to_sql (caused FK error - reverted) |
| `a01520c` | Increase batch_size from 100 to 500 |

---

## สิ่งที่ทำเสร็จแล้ว (31 Jan 2026 - Session 1)

### 6. ทดสอบ Upload ทุก Tab สำเร็จ

| Tab | ไฟล์ | จำนวน Records | สถานะ |
|-----|------|---------------|-------|
| Appointment | appointment-october.csv | 3,117 | ✅ สำเร็จ |
| QLog | qlog-october.csv | 3,018 | ✅ สำเร็จ |
| Bio Raw | ALL-OCT-2025-V1.csv | 3,022 (G: 2,881, B: 132) | ✅ สำเร็จ |

---

### 5. แก้ไข Bug ใน Upload

#### Bug 1: Column Mapping ไม่ตรงกัน (Appointment)
**อาการ:** APPOINTMENT_CODE แสดงค่าของ GROUP_ID แทน (ข้อมูล shift ไป 1 column)

**สาเหตุ:** ไฟล์ CSV มี data columns (28) มากกว่า header columns (27) ทำให้ pandas ใช้ column แรกของ data เป็น index โดยอัตโนมัติ

**วิธีแก้ไข:** ใช้ `pd.read_csv(uploaded_file, index_col=False)` เพื่อป้องกันไม่ให้ pandas ใช้ column แรกเป็น index

---

#### Bug 2: StringDataRightTruncation
**อาการ:** `psycopg2.errors.StringDataRightTruncation: value too long for type character varying(20)`

**สาเหตุ:** column `form_type` ใน PostgreSQL กำหนดเป็น `VARCHAR(20)` แต่ค่าจริงเป็นภาษาไทยยาวมาก

**วิธีแก้ไข:**
- แก้ไข model ใน `database/models.py`: form_type VARCHAR(255), card_id VARCHAR(30), work_permit_no VARCHAR(30)
- เพิ่ม migration script ใน `database/connection.py` เพื่อ ALTER table ที่มีอยู่แล้ว

---

#### Bug 3: Import ช้ามาก (Performance)
**อาการ:** การนำเข้า 3,000+ รายการใช้เวลานานมาก

**สาเหตุ:** ใช้ `df.iterrows()` + ORM objects ทีละตัว

**วิธีแก้ไข:**
- ใช้ vectorized pandas operations + SQLAlchemy bulk insert
- ใช้ batch_size = 100 เพื่อหลีกเลี่ยง PostgreSQL parameter limit

---

#### Bug 4: numpy.int64 compatibility
**อาการ:** `psycopg2.ProgrammingError: can't adapt type 'numpy.int64'`

**สาเหตุ:** `value_counts()` return numpy.int64 ซึ่ง psycopg2 ไม่รองรับ

**วิธีแก้ไข:** แปลงเป็น Python int ก่อนใส่ database
```python
good = int(status_counts.get('G', 0))
bad = int(status_counts.get('B', 0))
```

---

#### Bug 5: Encoding ภาษาไทย (Bio Raw)
**อาการ:** ภาษาไทยแสดงเป็นตัวอักษรอ่านไม่ออก เช่น `¡Ôล¾Ôล¾!ก็มล่Ô»NË0...`

**สาเหตุ:** ใช้ encoding ผิด (cp1252/latin1 แทน windows-874/tis-620)

**วิธีแก้ไข:**
- เพิ่ม Thai encodings: `windows-874`, `tis-620`, `cp874`
- ตรวจสอบ encoding โดยเช็ค Thai unicode range (0E00-0E7F)
- ตรวจจับ garbage characters จาก wrong encoding

```python
encodings = ['utf-8', 'utf-8-sig', 'windows-874', 'tis-620', 'cp874', 'cp1252', 'latin1']
for enc in encodings:
    df = pd.read_csv(file, encoding=enc, low_memory=False)
    # Verify Thai characters
    has_thai = any('\u0e00' <= c <= '\u0e7f' for c in sample_str)
    has_garbage = any(ord(c) > 127 and not ('\u0e00' <= c <= '\u0e7f') for c in sample_str)
    if has_thai or not has_garbage:
        break
```

---

### Git Commits (31 Jan 2026 - Session 1)
| Commit | Description |
|--------|-------------|
| `33e6b28` | Update SESSION_LOG with all bug fixes and test results |
| `7051c5b` | Fix Thai encoding detection for CSV uploads |
| `ad445a8` | Fix numpy.int64 compatibility with psycopg2 |
| `b300290` | Fix encoding issue for CSV uploads - support multiple encodings |
| `f235ee7` | Fix PostgreSQL parameter limit error in bulk insert |
| `ecc7f69` | Optimize Appointment import performance with bulk insert |
| `32eb3f1` | Fix StringDataRightTruncation for appointments table |
| `9af44de` | Fix CSV column alignment using index_col=False |
| `7cb1691` | Fix CSV column mismatch bug in Appointment upload |

---

## สิ่งที่ทำเสร็จแล้ว (30 Jan 2026)

### 1. ปรับปรุง Overview Dashboard
- เปลี่ยน Daily Chart จาก Line เป็น Bar + Line (stacked)
- เพิ่ม Pie Chart สำหรับสัดส่วนบัตรดี/เสีย
- เพิ่ม Gauge Charts สำหรับ SLA Performance
- เพิ่ม Branch/Center Filter (multiselect)
- เพิ่มปุ่ม Reset Filter
- แสดงชื่อศูนย์แทนรหัสใน Filter

### 2. สร้างระบบ Upload Raw Data ใหม่
- สร้างตารางใหม่ใน `database/models.py`:
  - `AppointmentUpload` + `Appointment` - ข้อมูลนัดหมาย
  - `QLogUpload` + `QLog` - ข้อมูล Check-in
  - `BioUpload` + `BioRecord` - ข้อมูลการพิมพ์บัตร

- ปรับหน้า Upload (`pages/1_📤_Upload.py`) เป็น 4 tabs:
  - 📊 Bio Unified Report - ไฟล์ join แล้ว
  - 📅 Appointment - appointment-*.csv
  - ⏱️ QLog - qlog-*.csv
  - 🖨️ Bio Raw - ALL-*.csv, BIO_*.xlsx

### 3. เพิ่มการวิเคราะห์ No-Show ใน Overview
- เพิ่ม function `get_noshow_stats()` สำหรับคำนวณ No-show
- คำนวณ No-show = Appointment (STATUS='SUCCESS') - QLog (QLOG_STATUS='S')
- เพิ่ม Metrics: นัดหมายทั้งหมด, มา Check-in, No-Show, อัตรา Check-in
- เพิ่ม Bar Chart แสดงรายวัน: นัดหมาย vs มา Check-in vs No-Show
- เพิ่ม Pie Chart สัดส่วน Check-in / No-Show

---

## ไฟล์ที่เกี่ยวข้อง
| ไฟล์ | คำอธิบาย |
|------|----------|
| `database/models.py` | ตาราง Appointment, QLog, BioRecord |
| `database/connection.py` | Migration scripts สำหรับ ALTER columns |
| `pages/1_📤_Upload.py` | หน้า Upload 4 tabs + encoding detection + large file support |
| `pages/2_📈_Overview.py` | Dashboard หลัก + No-Show Analysis |
| `.streamlit/config.toml` | maxUploadSize = 200 MB |

## Column Mapping ที่ใช้
**Appointment:**
- APPOINTMENT_CODE → appointment_id
- APPOINTMENT_DATE → appt_date
- BRANCH_ID → branch_code
- STATUS → appt_status (ใช้ 'SUCCESS' สำหรับนัดที่ยืนยันแล้ว)

**QLog:**
- QLOG_ID, BRANCH_ID, QLOG_DATE, QLOG_TIMEIN
- APPOINTMENT_CODE → appointment_code
- QLOG_STATUS (S=Success - มาแล้ว)

**Bio Raw:**
- Appointment ID, Serial Number, Print Status, Print Date
- SLA Start, SLA Stop, SLA Duration

## Git Status
- Version: 1.3.8
- Branch: main
- Remote: https://github.com/ytsp18/bio-dashboard.git
- Latest Commit: `f2d3038` - Treemap: show branch_code in box, full name in tooltip

## วิธีทดสอบ No-Show Analysis
1. อัพโหลดไฟล์ Appointment (appointment-*.csv) ในหน้า Upload > Tab "📅 Appointment"
2. อัพโหลดไฟล์ QLog (qlog-*.csv) ในหน้า Upload > Tab "⏱️ QLog"
3. ไปที่หน้า Overview จะเห็น Section "📅 การวิเคราะห์ No-Show" แสดงขึ้นมา

## Batch Size Configuration
| Tab | Columns | Batch Size | Params per Batch |
|-----|---------|------------|------------------|
| Appointment | 8 | 5,000 | 40,000 |
| QLog | 14 | 4,000 | 56,000 |
| Bio Raw | 17 | 3,000 | 51,000 |

(PostgreSQL limit: 65,535 params per query)
