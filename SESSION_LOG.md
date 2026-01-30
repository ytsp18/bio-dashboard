# Session Log - 31 Jan 2026

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
- Last commit: `fbf9cbe` - Optimize upload for large files 30MB+
- Branch: main
- Remote: https://github.com/ytsp18/bio-dashboard.git

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
