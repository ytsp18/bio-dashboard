# Bio Dashboard - Excel Import Template Guide

## สรุป Templates ที่สร้าง

| Template | ไฟล์ | คำอธิบาย |
|----------|------|----------|
| **Full Template** | `Bio_import_template.xlsx` | Template เต็มรูปแบบ รองรับทุก Sheet |
| **Simple Template** | `Bio_simple_import.xlsx` | Template แบบง่าย มี Sheet เดียว |

---

## 1. Simple Template (แนะนำ)

**ไฟล์:** `Bio_simple_import.xlsx`

### รูปแบบข้อมูล

| Column | Required | Type | ตัวอย่าง | คำอธิบาย |
|--------|----------|------|----------|----------|
| Appointment ID | ✅ | Text | `1-TRT001012600040` | รหัสนัดหมาย |
| Branch Code | ✅ | Text | `TRT-SC-S-001` | รหัสศูนย์ |
| Branch Name | | Text | `ศูนย์บริการฯ จ.ตราด` | ชื่อศูนย์ |
| Card ID | ✅ | Text (13) | `6923000000006` | เลขทะเบียนบัตร |
| Serial Number | ✅ | Text (13) | `0099004524052` | หมายเลขบัตร |
| Work Permit No | | Text (13) | `0769230000001` | เลขใบอนุญาตทำงาน |
| Print Status | ✅ | G/B | `G` | สถานะบัตร |
| Reject Reason | | Text | `พิมพ์ผิด` | สาเหตุบัตรเสีย |
| Operator | | Text | `apisara.yus` | ผู้ให้บริการ |
| SLA Minutes | | Number | `5.5` | เวลาออกบัตร (นาที) |
| Print Date | ✅ | Date | `2026-01-06` | วันที่พิมพ์ |
| Region | | Text | `ภาคตะวันออก` | ภูมิภาค |

### ข้อดี
- ใช้งานง่าย มี Sheet เดียว
- รวมบัตรดี (G) และบัตรเสีย (B) ไว้ด้วยกัน
- ลดความซับซ้อนในการเตรียมข้อมูล

---

## 2. Full Template

**ไฟล์:** `Bio_import_template.xlsx`

### Sheets ที่รองรับ

| Sheet | คำอธิบาย |
|-------|----------|
| `2.รายการบัตรดี` | รายละเอียดบัตรดี (G) |
| `3.รายการบัตรเสีย` | รายละเอียดบัตรเสีย (B) |
| `4.สรุปตามศูนย์` | สถิติแยกตามศูนย์บริการ |
| `7.บัตรจัดส่ง` | รายการบัตรจัดส่ง |
| `9.ออกบัตรผิดศูนย์` | รายที่ออกบัตรผิดศูนย์นัด |
| `13.ข้อมูลทั้งหมด` | ข้อมูล Raw ทั้งหมด |
| `22.ส่วนต่างบัตรสมบูรณ์` | ส่วนต่างบัตรสมบูรณ์ |

---

## วิธีใช้งาน

### ขั้นตอนที่ 1: เตรียมข้อมูล

1. เปิดไฟล์ Template
2. **ลบแถวตัวอย่าง** (แถว 2 สีเขียว)
3. กรอกข้อมูลตาม format ที่กำหนด

### ขั้นตอนที่ 2: ตรวจสอบข้อมูล

**สิ่งที่ต้องตรวจสอบ:**

1. **ตัวเลข 13 หลัก** (Card ID, Serial Number, Work Permit No)
   - ต้องใส่เป็น Text ไม่ใช่ Number
   - ถ้า Excel แปลงเป็น Number ให้ใส่ `'` นำหน้า เช่น `'0099004524052`
   - หรือ Format cell เป็น Text ก่อนกรอกข้อมูล

2. **วันที่** (Print Date)
   - ใช้ format: `YYYY-MM-DD` (เช่น `2026-01-06`)
   - หรือใช้ format Excel Date ปกติ

3. **Column ที่ Required**
   - ต้องมีข้อมูลครบทุก row
   - ถ้าขาดจะ import ไม่ได้

### ขั้นตอนที่ 3: Import เข้าระบบ

1. เปิด Bio Dashboard
2. ไปที่หน้า "นำเข้าข้อมูล"
3. Upload ไฟล์ Excel
4. ตรวจสอบ Preview ก่อนยืนยัน

---

## ข้อควรระวัง

### ปัญหาที่พบบ่อย

| ปัญหา | สาเหตุ | วิธีแก้ไข |
|-------|--------|----------|
| `StringDataRightTruncation` | ข้อมูลยาวเกินกำหนด | ตรวจสอบ column ที่ใส่ข้อมูลผิด |
| เลข 0 นำหน้าหาย | Excel แปลงเป็น Number | Format cell เป็น Text |
| วันที่ผิด format | ใช้ format ไม่ถูก | ใช้ YYYY-MM-DD |
| Column สลับกัน | Header ไม่ตรง | ตรวจสอบ Header row |

### Column Mapping ที่ระบบรองรับ

**Sheet 22.ส่วนต่างบัตรสมบูรณ์:**
```
'ลำดับ': 'row_num'
'Appointment ID': 'appointment_id'
'จำนวน G': 'g_count'
'รหัสศูนย์': 'branch_code'
'ชื่อศูนย์': 'branch_name'
'ภูมิภาค': 'region'
'Card ID': 'card_id'
'Serial Number': 'serial_number'
'Work Permit No': 'work_permit_no'
'SLA (นาที)': 'sla_minutes'
'ผู้ให้บริการ': 'operator'
'วันที่พิมพ์': 'print_date'
```

---

## สร้าง Template ใหม่

```bash
cd bio_dashboard/templates
python3 excel_import_template.py
```

จะสร้างไฟล์:
- `Bio_import_template.xlsx` (Full)
- `Bio_simple_import.xlsx` (Simple)

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-01-29 | Initial release |
