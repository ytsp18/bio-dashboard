# Bio Dashboard Project Documentation

## Project Overview

**Bio Dashboard** เป็น Streamlit Dashboard สำหรับจัดการและแสดงผลข้อมูล Bio Unified Report (รายงานการออกบัตรประจำตัว)

### Tech Stack
- **Frontend**: Streamlit
- **Backend**: Python 3.9+
- **Database**: SQLite with SQLAlchemy ORM
- **Data Processing**: Pandas, OpenPyXL

---

## Project Structure

```
bio_dashboard/
├── app.py                      # Main Streamlit application
├── requirements.txt            # Python dependencies
├── database/
│   ├── __init__.py
│   ├── connection.py           # Database connection management
│   ├── models.py               # SQLAlchemy models
│   └── bio_data.db             # SQLite database file
├── services/
│   ├── __init__.py
│   ├── data_service.py         # Data import/export operations
│   └── excel_parser.py         # Excel file parsing
├── pages/
│   ├── 1_📤_Upload.py          # Upload page
│   ├── 2_📊_Reports.py         # Reports page
│   ├── 3_🔍_Search.py          # Search page
│   ├── 4_📈_Analytics.py       # Analytics page
│   ├── 5_🏢_Centers.py         # Centers page
│   └── 6_⚙️_Settings.py        # Settings page
└── utils/
    └── helpers.py              # Utility functions
```

---

## Database Models

### Report
รายงานหลัก (ต่อไฟล์ Excel 1 ไฟล์)
- `id`: Primary key
- `filename`: ชื่อไฟล์
- `report_date`: วันที่รายงาน
- `upload_date`: วันที่ upload
- `total_good`: จำนวนบัตรดี
- `total_bad`: จำนวนบัตรเสีย
- `total_records`: จำนวนรายการทั้งหมด

### Card
ข้อมูลบัตร (จาก Sheet 2, 3, 13)
- `id`: Primary key
- `report_id`: Foreign key to Report
- `appointment_id`: รหัสนัดหมาย
- `serial_number`: หมายเลข Serial
- `print_status`: สถานะการพิมพ์ (G/B)
- `print_date`: วันที่พิมพ์
- `branch_code`: รหัสศูนย์
- `branch_name`: ชื่อศูนย์
- `region`: ภูมิภาค
- `sla_minutes`: เวลา SLA (นาที)
- และอื่นๆ...

### DeliveryCard
บัตรจัดส่ง (จาก Sheet 7)
- `id`: Primary key
- `report_id`: Foreign key to Report
- `appointment_id`: รหัสนัดหมาย
- `serial_number`: หมายเลข Serial
- `print_status`: สถานะการพิมพ์

### CenterStat
สถิติตามศูนย์ (จาก Sheet 4)

### AnomalySLA
รายการ SLA ผิดปกติ (จาก Sheet 15)

---

## Excel File Structure (Bio Unified Report)

ไฟล์ Excel มี 23 Sheets:

| Sheet | Name | Description |
|-------|------|-------------|
| 1 | สรุปภาพรวม | Summary statistics |
| 2 | รายการบัตรดี | Good cards list |
| 3 | รายการบัตรเสีย | Bad cards list |
| 4 | สรุปตามศูนย์ | Stats by center |
| 5 | สรุปตามภูมิภาค | Stats by region |
| 6 | SLA เกิน 12 นาที | SLA > 12 minutes |
| 6.5 | SLA รอคิวเกิน 1 ชม. | Wait time > 1 hour |
| 7 | บัตรจัดส่ง | Delivery cards |
| 8 | ออกบัตรหลายใบ | Multiple cards per appointment |
| 9 | ออกบัตรผิดศูนย์ | Wrong center issuance |
| 10 | นัดหมายผิดวัน | Wrong appointment date |
| 11 | Serial ซ้ำ | Duplicate serial numbers |
| 13 | ข้อมูลทั้งหมด | All data (raw) |
| 14 | ตรวจสอบความถูกต้อง | Validation |
| 15 | Anomaly SLA Time | Anomaly SLA records |
| 16 | ออกบัตรเกินเที่ยงคืน | After midnight issuance |
| 17 | Reissue(มีB) | Reissued cards |
| 18 | ผลต่างCardID-SN | Card ID - Serial diff |
| 19 | AnomalyG>1 | Anomaly G > 1 |
| 20 | ApptID_G>1 | Appointment with G > 1 |
| 21 | บัตรสมบูรณ์ | Complete cards |
| 22 | ส่วนต่างบัตรสมบูรณ์ | Complete cards diff |

---

## Key Statistics Explained

### จาก Sheet 1 (สรุปภาพรวม):

| Metric | Description |
|--------|-------------|
| จำนวนทั้งหมด (BIO) | Total records in BIO system |
| G (บัตรดี) - รับที่ศูนย์ | Good cards - Pickup at center |
| G (บัตรดี) - จัดส่ง | Good cards - Delivery |
| G (บัตรดี) - รวม | Total good cards |
| G (บัตรดี) - Unique Serial | Unique good serial numbers (pickup only) |
| รวม Unique Serial Number (G) | Total unique good serial (pickup + delivery) |
| B (บัตรเสีย) - รวม | Total bad cards |

### Good Rate Calculation
```
Good Rate = (Good Cards) / (Good Cards + Bad Cards) × 100
```
**Note**: ไม่รวมบัตรที่ยังไม่พิมพ์ (NULL status) ในการคำนวณ

---

## Development Log

### Session 1 - Initial Setup (Jan 28, 2026)

#### Tasks Completed:
1. **Created basic Streamlit dashboard structure**
2. **Implemented database models** with SQLAlchemy
3. **Created Excel parser** for Bio Unified Report files
4. **Built Upload page** with file preview

### Session 2 - Bug Fixes and Enhancements

#### Issue 1: Delivery Cards Not Displayed
**Problem**: บัตรจัดส่ง (Sheet 7) ไม่แสดงในการ preview ก่อนนำเข้า

**Solution**:
- Added `DeliveryCard` model to `models.py`
- Added delivery card import logic to `data_service.py`
- Updated Upload page to show delivery count

**Files Modified**:
- `database/models.py`
- `services/data_service.py`
- `pages/1_📤_Upload.py`

---

#### Issue 2: Incorrect Good Rate Calculation
**Problem**: Good rate คำนวณผิด (94.67% แทนที่จะเป็น 98.32%)

**Root Cause**: คำนวณ good_rate โดยหารด้วย total_records ซึ่งรวมบัตรที่ยังไม่พิมพ์ (NULL status)

**Solution**:
```python
# Before (incorrect)
good_rate = good / total * 100

# After (correct)
printed_total = good + bad
good_rate = good / printed_total * 100
```

**Files Modified**:
- `services/data_service.py`
- `app.py`

---

#### Issue 3: Wrong Card Count in Preview
**Problem**: Preview แสดง 2,881 บัตรดี แต่ Excel Summary แสดง 2,884

**Root Cause**:
- Sheet 2 มีเฉพาะบัตรรับที่ศูนย์ (2,881)
- Sheet 7 มีบัตรจัดส่ง (3)
- รวม = 2,884

**Solution**:
Modified `get_summary_stats()` in `excel_parser.py` to:
1. Read directly from Sheet 1 Summary
2. Include delivery cards in calculation
3. Read "G (บัตรดี) - รวม" which includes both pickup and delivery

**Files Modified**:
- `services/excel_parser.py`

---

#### Issue 4: Unique Serial Number Mismatch
**Problem**: User expected Unique Serial (G) = 2,883 but dashboard showed 2,880

**Root Cause**:
- Reading "G (บัตรดี) - Unique Serial" (2,880) - pickup only
- Should read "รวม Unique Serial Number (G)" (2,883) - includes delivery

**Solution**:
Updated `get_summary_stats()` to prioritize "รวม Unique Serial Number (G)"

---

#### Issue 5: Date Parsing Error (Day/Month Swap)
**Problem**: Chart showed Jan 12, 2025 data that shouldn't exist

**Root Cause**:
Excel file had inconsistent date formats:
- Some cells: string `"20-11-2025"` (DD-MM-YYYY) ✅
- Some cells: datetime `2025-05-11` (interpreted as YYYY-MM-DD) ❌
  - Excel stored it incorrectly, pandas read it as May 11 instead of Nov 5

**Investigation**:
```python
# Raw Excel data showed:
Row 2: 20-11-2025 (type: str)  # Correct
Row 9: 2025-05-11 (type: datetime)  # Wrong - should be Nov 5, not May 11
```

**Solution**:
Enhanced `parse_date_value()` with day/month swap detection:

```python
def parse_date_value(self, value, report_month: int = None):
    """Parse date with day/month swap detection."""
    if isinstance(value, datetime):
        result_date = value.date()

        # Detect day/month swap
        if report_month is not None:
            if result_date.month != report_month and result_date.day == report_month:
                # Swap day and month
                if result_date.month <= 12:
                    corrected = date(result_date.year, result_date.day, result_date.month)
                    return corrected

        return result_date
```

**Files Modified**:
- `services/excel_parser.py` - Added `report_month` parameter
- `services/data_service.py` - Pass `report_month` to all `parse_date_value()` calls

**Data Re-import**:
Cleared database and re-imported all 3 reports with corrected date parsing.

---

## Statistics Summary (After Fixes)

### October 2568 (2025) Report
| Metric | Value |
|--------|-------|
| Total Records | 3,022 |
| Good Cards (Total) | 2,884 |
| - Pickup | 2,881 |
| - Delivery | 3 |
| Bad Cards | 132 |
| Unique Serial (G) | 2,883 |
| Good Rate | 95.63% |

### November 2568 (2025) Report
| Metric | Value |
|--------|-------|
| Total Records | 22,020 |
| Good Cards | 21,586 |
| Bad Cards | 434 |
| Good Rate | 98.03% |

### December 2568 (2025) Report
| Metric | Value |
|--------|-------|
| Total Records | 56,299 |
| Good Cards | 55,407 |
| Bad Cards | 892 |
| Good Rate | 98.42% |

---

## Running the Application

### Prerequisites
```bash
pip install -r requirements.txt
```

### Start Server
```bash
streamlit run app.py --server.port 8501
```

### Access Dashboard
Open browser: http://localhost:8501

---

## Known Issues & Limitations

1. **Date Format Inconsistency**: Excel files may have mixed date formats. The parser now handles day/month swaps for monthly reports.

2. **Large File Processing**: Monthly reports with 50K+ records may take time to import.

3. **Duplicate Detection**: Currently based on filename. Same data with different filename will be re-imported.

---

## Future Enhancements

- [ ] Add data export functionality
- [ ] Implement data comparison between periods
- [x] Add user authentication
- [ ] Create automated report generation
- [ ] Add email notifications for anomalies

---

## Authentication System

### Overview
ระบบ Authentication ใช้ `streamlit-authenticator` library รองรับ:
- Username/Password login
- Password hashing (bcrypt)
- Cookie-based session management (30 วัน)
- Multi-user support

### Setup
1. ติดตั้ง dependencies:
```bash
pip install streamlit-authenticator pyyaml
```

2. รัน setup script:
```bash
cd bio_dashboard/config
python setup_auth.py
```

3. รัน Dashboard:
```bash
streamlit run app.py
```

### Default Credentials
| Username | Password | Role |
|----------|----------|------|
| admin | admin123 | Administrator |
| operator | operator123 | Operator |

**สำคัญ**: เปลี่ยน password ก่อนใช้งานจริง!

### Configuration Files
- `config/config.yaml` - User credentials และ cookie settings
- `config/setup_auth.py` - Script สำหรับ generate password hash
- `auth/authenticator.py` - Authentication logic

### เพิ่ม User ใหม่
1. Generate password hash:
```python
import streamlit_authenticator as stauth
hashed = stauth.Hasher(['your_password']).generate()[0]
print(hashed)
```

2. แก้ไข `config/config.yaml`:
```yaml
credentials:
  usernames:
    newuser:
      email: newuser@example.com
      name: New User
      password: <hashed_password>
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | Jan 28, 2026 | Initial release |
| 1.0.1 | Jan 28, 2026 | Fixed delivery card display |
| 1.0.2 | Jan 28, 2026 | Fixed good rate calculation |
| 1.0.3 | Jan 28, 2026 | Fixed summary stats reading |
| 1.0.4 | Jan 28, 2026 | Fixed date parsing (day/month swap) |
| 1.1.0 | Jan 28, 2026 | Added user authentication system |

---

## Contact

Project maintained by: Bio Dashboard Team
