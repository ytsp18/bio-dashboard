# Session Log - 31 Jan 2026

## สิ่งที่ทำเสร็จแล้ว (31 Jan 2026)

### 5. แก้ไข Bug ใน Appointment Upload

#### Bug 1: Column Mapping ไม่ตรงกัน
**อาการ:** APPOINTMENT_CODE แสดงค่าของ GROUP_ID แทน (ข้อมูล shift ไป 1 column)

**สาเหตุ:** ไฟล์ CSV มี data columns (28) มากกว่า header columns (27) ทำให้ pandas ใช้ column แรกของ data เป็น index โดยอัตโนมัติ

**วิธีแก้ไข:** ใช้ `pd.read_csv(uploaded_file, index_col=False)` เพื่อป้องกันไม่ให้ pandas ใช้ column แรกเป็น index

**ไฟล์ที่แก้:** `pages/1_📤_Upload.py` (line 302-307)

```python
# Read CSV with index_col=False to prevent pandas from using first column as index
import warnings
with warnings.catch_warnings():
    warnings.filterwarnings('ignore', message='Length of header or names does not match')
    df = pd.read_csv(uploaded_appt, index_col=False)
```

---

#### Bug 2: StringDataRightTruncation
**อาการ:** `psycopg2.errors.StringDataRightTruncation: value too long for type character varying(20)`

**สาเหตุ:** column `form_type` ใน PostgreSQL กำหนดเป็น `VARCHAR(20)` แต่ค่าจริงเป็นภาษาไทยยาวมาก เช่น `'ขอใบอนุญาตทำงาน มาตรา 62 BOI Single Window'`

**วิธีแก้ไข:**
1. แก้ไข model ใน `database/models.py`:
   - `form_type`: VARCHAR(20) → VARCHAR(255)
   - `card_id`: VARCHAR(20) → VARCHAR(30)
   - `work_permit_no`: VARCHAR(20) → VARCHAR(30)

2. เพิ่ม migration script ใน `database/connection.py` เพื่อ ALTER table ที่มีอยู่แล้ว

**ไฟล์ที่แก้:**
- `database/models.py` (line 351-353)
- `database/connection.py` (line 165-188)

---

#### Bug 3: Import ช้ามาก (Performance)
**อาการ:** การนำเข้า 3,117 รายการใช้เวลานานกว่าปกติ

**สาเหตุ:**
- ใช้ `df.iterrows()` ซึ่งช้ามากใน Python
- สร้าง ORM objects ทีละตัวใน loop
- ใช้ `bulk_save_objects()` ซึ่งยังไม่เร็วที่สุด

**วิธีแก้ไข:** ใช้ vectorized pandas operations + SQLAlchemy bulk insert

**ไฟล์ที่แก้:** `pages/1_📤_Upload.py` (line 354-378)

```python
# Prepare data using vectorized operations (much faster than iterrows)
import_df = pd.DataFrame()
import_df['upload_id'] = upload.id
import_df['appointment_id'] = df[col_map['appointment_id']].astype(str).str.strip()
# ... other columns ...

# Use bulk insert with executemany (faster than ORM objects)
from sqlalchemy import insert
records = import_df.to_dict('records')

# Insert in batches of 1000 for better performance
batch_size = 1000
for i in range(0, len(records), batch_size):
    batch = records[i:i+batch_size]
    session.execute(insert(Appointment), batch)
```

---

### Git Commits (31 Jan 2026)
| Commit | Description |
|--------|-------------|
| `7cb1691` | Fix CSV column mismatch bug in Appointment upload |
| `9af44de` | Fix CSV column alignment using index_col=False |
| `32eb3f1` | Fix StringDataRightTruncation for appointments table |
| `ecc7f69` | Optimize Appointment import performance with bulk insert |

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
- แสดงข้อความเมื่อยังไม่มีข้อมูล Appointment/QLog

### 4. Bug Fixes
- แก้ปัญหา NaN date ใส่ PostgreSQL ไม่ได้
- แก้ปัญหา `row.get()` เป็น `row[]`

## งานที่ค้าง (Pending)

### 1. ทดสอบ Upload
- ทดสอบ Upload Appointment, QLog, Bio Raw ให้ครบ
- อาจยังมี bug ที่ต้องแก้

### 2. ไฟล์ที่เกี่ยวข้อง
| ไฟล์ | คำอธิบาย |
|------|----------|
| `database/models.py` | ตาราง Appointment, QLog, BioRecord |
| `pages/1_📤_Upload.py` | หน้า Upload 4 tabs |
| `pages/2_📈_Overview.py` | Dashboard หลัก + No-Show Analysis |

### 3. Column Mapping ที่ใช้
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
- Last commit: `ecc7f69` - Optimize Appointment import performance with bulk insert
- Branch: main
- Remote: https://github.com/ytsp18/bio-dashboard.git

## วิธีทดสอบ No-Show Analysis
1. อัพโหลดไฟล์ Appointment (appointment-*.csv) ในหน้า Upload > Tab "📅 Appointment"
2. อัพโหลดไฟล์ QLog (qlog-*.csv) ในหน้า Upload > Tab "⏱️ QLog"
3. ไปที่หน้า Overview จะเห็น Section "📅 การวิเคราะห์ No-Show" แสดงขึ้นมา
