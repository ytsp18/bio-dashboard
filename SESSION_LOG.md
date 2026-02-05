# Session Log - Bio Dashboard

## สิ่งที่ทำเสร็จแล้ว (5 Feb 2026 - Session 7: SLA & Daily Summary Improvements)

### 16. SLA Calculation Fix & Daily Summary Enhancement

**ความต้องการ:**
- แก้ไข SLA รอคิว ให้นับเฉพาะนัดหมายที่ออกบัตรแล้ว
- แก้ไข SLA ออกบัตร ให้ดึงข้อมูลครบถ้วน
- แยกแสดงข้อมูลศูนย์บริการ (SC) และแรกรับ (OB) ในกราฟรายวัน
- แยกแสดง CardDeliveryRecord (บัตรจัดส่ง 68/69)

**สิ่งที่พัฒนา:**

1. **SLA รอคิว - เงื่อนไขใหม่**
   - นับเฉพาะนัดหมายที่มีการออกบัตร (G) แล้ว
   - JOIN QLog กับ BioRecord ที่ print_status='G'
   - Type A (OB): นับทุกรายการ, ตก SLA ถ้ารอ > 60 นาที
   - Type B (SC): นับเฉพาะ EI และ T, ตก SLA ถ้า TimeCall > SLA_TimeEnd

2. **SLA ออกบัตร - เปลี่ยนไปใช้ BioRecord**
   - เดิม: ดึงจาก Card table (มีข้อมูลแค่ 46%)
   - ใหม่: ดึงจาก BioRecord (มีข้อมูล 99.9%)
   - ข้อมูล SLA ครบถ้วนมากขึ้น

3. **สรุปจำนวนบัตรรายวัน - แยกตามประเภทศูนย์**
   - SC ศูนย์บริการ (G) - สีเขียว
   - OB แรกรับ (G) - สีน้ำเงิน
   - บัตรจัดส่ง (G) - สีม่วง (จาก CardDeliveryRecord)
   - บัตรเสีย SC/OB/จัดส่ง - แยกสีชัดเจน
   - รวมบัตรดี (Line) - รวมทั้ง 3 ประเภท

4. **QLog Upload - เพิ่ม columns ใหม่**
   - `sla_time_start`, `sla_time_end` - สำหรับคำนวณ SLA Type B
   - `qlog_train_time` - สำหรับคำนวณ SLA Type A
   - `appointment_time` - เวลานัดหมาย
   - `qlog_typename`, `qlog_counter` - ข้อมูลเพิ่มเติม
   - ลบการเช็ค duplicate QLog ID (อนุญาตซ้ำได้)

5. **Auto Migration**
   - เพิ่ม migration สำหรับ QLog columns ใหม่ใน connection.py
   - รันอัตโนมัติเมื่อ app startup

**เงื่อนไข SLA (ตาม Logic Documentation):**

| SLA | เงื่อนไข | ตก SLA |
|-----|---------|--------|
| **ออกบัตร** | SLA Stop - SLA Start | > 12 นาที |
| **รอคิว Type A (OB)** | ทุกรายการที่ออกบัตรแล้ว | TimeCall - Train_Time > 60 นาที |
| **รอคิว Type B (SC)** | เฉพาะ EI และ T ที่ออกบัตรแล้ว | TimeCall > SLA_TimeEnd |

**SLA_STATUS (เฉพาะ Type B):**
| Status | ความหมาย | นำมาคิด SLA |
|--------|----------|-------------|
| EI | Early In - มาก่อนเวลา | ✅ |
| T | On Time - มาตรงเวลา | ✅ |
| LO | Late within condition | ❌ |
| LI | Late beyond condition | ❌ |

**ไฟล์ที่แก้ไข:**
- `pages/2_📈_Overview.py` - SLA query จาก BioRecord, daily chart แยก SC/OB
- `pages/1_📤_Upload.py` - เพิ่ม QLog columns, ลบ duplicate check
- `database/models.py` - เพิ่ม qlog_train_time
- `database/connection.py` - auto migration สำหรับ QLog columns

**Git Commits:**
| Commit | Description |
|--------|-------------|
| `46fee3a` | Add SLA time columns to QLog and remove duplicate check |
| `689c96d` | Add auto-migration for QLog new columns |
| `a3d8a3a` | Fix daily summary chart - separate Card and CardDeliveryRecord |
| `dfd51ae` | Fix SLA รอคิว - only count appointments with printed cards |
| `5458309` | Separate daily summary by center type (SC/OB) |
| `76e628a` | Fix SLA ออกบัตร - use BioRecord instead of Card |
| `b9f1762` | Fix BioRecord import - use local import in cached function |

**Version:** 1.4.0

---

## สิ่งที่ทำเสร็จแล้ว (5 Feb 2026 - Session 7: Forecast Page Improvements)

### 15.5 Forecast Page - Date Range & Check-in Progress Bar

**สิ่งที่พัฒนา:**

1. **Date Range Picker**
   - 3 View Modes: Future (อนาคต), History (ย้อนหลัง), Custom (กำหนดเอง)
   - Future: แสดงนัดหมายตั้งแต่วันนี้ถึง 30 วันข้างหน้า
   - History: แสดงข้อมูลย้อนหลัง 7/30/90 วัน
   - Custom: กำหนดช่วงวันที่เอง

2. **Check-in Progress Bar**
   - แสดงเปรียบเทียบ นัดหมาย vs Check-in รายศูนย์
   - Progress bar พร้อม % และตัวเลข
   - สีตามสถานะ: เขียว (≥80%), เหลือง (50-79%), แดง (<50%)
   - ใช้ `components.html()` สำหรับ render HTML/CSS

3. **Fix 7/30 Day Metrics**
   - เปลี่ยนจากใช้ `today` เป็น `start_date`
   - ทำให้ค่า 7 วัน และ 30 วันแตกต่างกันถูกต้อง

**Git Commits:**
| Commit | Description |
|--------|-------------|
| `ea969fe` | Add date range picker to Forecast page |
| `b35d526` | Add 3 view modes: Future, History, Custom |
| `c202a85` | Fix 7/30 day metrics and add Check-in Progress Bar |
| `93915fe` | Fix Check-in Progress Bar display formatting |
| `622855d` | Fix Check-in Progress Bar not rendering - use components.html |

---

## สิ่งที่ทำเสร็จแล้ว (31 Jan 2026 - Session 6: Metric Cards Redesign)

### 15. Metric Cards Redesign for Operations

**ความต้องการ:**
- ปรับปรุง Metric Cards ให้เน้นการใช้งานเชิง Operation
- เพิ่ม Status badges, Progress bars, Quick actions

**สิ่งที่พัฒนา:**

1. **Operation Summary Panel** (ใหม่)
   - แสดงสถานะรวมของระบบ (ปกติ/เตือน/วิกฤต)
   - Quick Metrics: บัตรดี, บัตรเสีย, สมบูรณ์, Anomaly, SLA, Work Permit
   - Alert banners สำหรับรายการที่ต้องตรวจสอบ
   - แสดงเวลาอัปเดตล่าสุด

2. **Enhanced Metric Cards**
   - **Status Badge**: ปกติ (✓ เขียว), เตือน (! เหลือง), วิกฤต (!! แดง)
   - **Progress Bar**: แสดง % เทียบกับเป้าหมาย
   - **Subtitle**: ข้อมูลเพิ่มเติม เช่น Good Rate %
   - **Alert Mode**: Highlight cards ที่ต้องแก้ไข
   - **Trend Indicators**: ▲▼ เปรียบเทียบ วัน/สัปดาห์/เดือน

3. **Action Cards** (ใหม่)
   - แสดงรายการที่ต้องตรวจสอบเป็นการ์ดแยก
   - มี icon, ชื่อ, คำอธิบาย, จำนวน
   - ปุ่ม Quick Action "➡️ ดูรายละเอียด" ไปหน้าที่เกี่ยวข้อง

4. **Mini Metric Cards**
   - การ์ดขนาดเล็กสำหรับ SLA Summary
   - แสดง trend indicator

5. **KPI Gauge Component**
   - Progress bar พร้อม threshold สี
   - Status badge อัตโนมัติตามค่า

**ไฟล์ที่แก้ไข:**
- `utils/metric_cards.py` - เพิ่ม functions ใหม่
- `pages/2_📈_Overview.py` - ใช้ components ใหม่

**Version:** 1.3.9

---

## สิ่งที่ทำเสร็จแล้ว (31 Jan 2026 - Session 5: Workload Forecast)

### 14. Workload Forecast Feature (นัดหมายล่วงหน้า)

**ความต้องการ:**
- แสดงปริมาณการนัดหมายล่วงหน้าเพื่อเตรียมรับมือ
- เปรียบเทียบกับ Capacity จาก BranchMaster

**สิ่งที่พัฒนา:**

1. **Function `get_upcoming_appointments()`** (Overview.py)
2. **Summary Section ใน Overview**
3. **หน้า "ปริมาณการนัดหมาย"** (3_📆_Forecast.py)
4. **Treemap Visualization**
5. **แยกกราฟตามประเภทศูนย์**

**Version:** 1.3.8

---

## สิ่งที่ทำเสร็จแล้ว (31 Jan 2026 - Session 4: Security Audit)

### 13. Security Audit & SQL Injection Fix

- SQL Injection Fix - เปลี่ยนเป็น parameterized queries
- Credential Rotation

---

## สิ่งที่ทำเสร็จแล้ว (31 Jan 2026 - Session 3)

### 9-12. PostgreSQL COPY Protocol, Card Delivery Upload, Duplicate Check, Bug Fixes

**Version:** 1.3.6

---

## สิ่งที่ทำเสร็จแล้ว (31 Jan 2026 - Session 2)

### 7-8. FK Violation Fix, Large File Support

---

## สิ่งที่ทำเสร็จแล้ว (31 Jan 2026 - Session 1)

### 5-6. Upload Bug Fixes, All Tabs Tested

---

## สิ่งที่ทำเสร็จแล้ว (30 Jan 2026)

### 1-4. Overview Dashboard, Upload System, No-Show Analysis

---

## Git Status
- **Version:** 1.4.0
- **Branch:** main
- **Remote:** https://github.com/ytsp18/bio-dashboard.git
- **Latest Commit:** `b9f1762` - Fix BioRecord import - use local import in cached function

## QLog Upload - Column Mapping

| DB Column | CSV Column |
|-----------|------------|
| qlog_id | QLOG_ID |
| branch_code | BRANCH_ID |
| qlog_type | QLOG_TYPE |
| qlog_typename | QLOG_TYPENAME |
| qlog_num | QLOG_NUM |
| qlog_counter | QLOG_COUNTER |
| qlog_user | QLOG_USER |
| qlog_date | QLOG_DATE / QLOG_DATEIN |
| qlog_time_in | QLOG_TIMEIN |
| qlog_time_call | QLOG_TIMECALL |
| qlog_time_end | QLOG_TIMEEND |
| qlog_train_time | QLOG_TRAIN_TIME |
| wait_time_seconds | QLOG_COUNTWAIT |
| appointment_code | APPOINTMENT_CODE |
| appointment_time | APPOINTMENT_TIME |
| qlog_status | QLOG_STATUS |
| sla_status | SLA_STATUS |
| sla_time_start | SLA_TIMESTART |
| sla_time_end | SLA_TIMEEND |

## หมายเหตุ
- QLog ID สามารถซ้ำได้ (คนเดียวอาจมา check-in หลายครั้ง/วัน)
- ต้อง re-import QLog หลังจากแก้ไข upload เพื่อให้มีข้อมูล sla_time_end
