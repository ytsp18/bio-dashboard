# Bug Fixes Log

รายละเอียด bugs ที่พบและแก้ไขใน Bio Dashboard project

---

## Bug #001: Delivery Cards Not Displayed in Preview

### Reported
- **Date**: 2026-01-28
- **Severity**: Medium
- **Status**: ✅ Fixed

### Description
เมื่อ upload ไฟล์ Excel, หน้า preview ไม่แสดงจำนวนบัตรจัดส่ง (บัตรจัดส่ง) ให้ตรวจสอบก่อนนำเข้า

### Steps to Reproduce
1. Upload Bio_unified_report file
2. Check preview statistics
3. Notice: no delivery card count shown

### Root Cause
- ไม่มี DeliveryCard model ในระบบ
- ไม่มี logic สำหรับ parse และ import ข้อมูลจาก Sheet 7 (บัตรจัดส่ง)

### Solution
1. สร้าง DeliveryCard model ใน `database/models.py`:
```python
class DeliveryCard(Base):
    __tablename__ = 'delivery_cards'
    id = Column(Integer, primary_key=True, autoincrement=True)
    report_id = Column(Integer, ForeignKey('reports.id'), nullable=False)
    appointment_id = Column(String(50), index=True)
    serial_number = Column(String(20), index=True)
    print_status = Column(String(10))
    card_id = Column(String(20))
    work_permit_no = Column(String(20))
```

2. เพิ่ม `parse_delivery_cards()` ใน `excel_parser.py`
3. เพิ่ม delivery import logic ใน `data_service.py`
4. อัพเดท Upload page ให้แสดง delivery count

### Files Changed
- `database/models.py`
- `services/excel_parser.py`
- `services/data_service.py`
- `pages/1_📤_Upload.py`

---

## Bug #002: Incorrect Good Rate Calculation

### Reported
- **Date**: 2026-01-28
- **Severity**: High
- **Status**: ✅ Fixed

### Description
Good rate แสดง 94.67% แต่ค่าที่ถูกต้องควรเป็น 98.32%

### Steps to Reproduce
1. Import October 2568 report
2. View dashboard statistics
3. Good rate shows ~94.67%
4. Manual calculation: 2884/(2884+132) = 95.63% (not 94.67%)

### Investigation
```sql
-- Check data
SELECT print_status, COUNT(*) FROM cards GROUP BY print_status;
-- Result:
-- G: 2,881
-- B: 132
-- NULL: 4,263 (appointments without print yet)
```

### Root Cause
คำนวณ good_rate โดยหารด้วย total_records ซึ่งรวมบัตรที่ยังไม่พิมพ์ (NULL status):
```python
# Wrong calculation
good_rate = 2884 / (2884 + 132 + 4263) * 100 = 39.6%  # Even worse!
```

จริงๆ แล้วระบบแสดง:
```python
good_rate = 2884 / 3022 * 100 = 95.43%  # Close but still wrong
```

### Solution
แก้ไขให้คำนวณจากบัตรที่พิมพ์แล้วเท่านั้น (G + B):
```python
# Correct calculation
printed_total = good + bad  # 2884 + 132 = 3016
good_rate = good / printed_total * 100  # 2884 / 3016 = 95.63%
```

### Files Changed
- `services/data_service.py` - `get_dashboard_stats()`
- `app.py` - Dashboard display logic

---

## Bug #003: Preview Card Count Mismatch

### Reported
- **Date**: 2026-01-28
- **Severity**: High
- **Status**: ✅ Fixed

### Description
หน้า Preview แสดงบัตรดี 2,881 แต่ Excel Summary แสดง:
- รวม Unique Serial Number (G) = 2,883
- G (บัตรดี) - รวม = 2,884

### Steps to Reproduce
1. Upload Bio_unified_report_ตุลาคม_2568
2. Preview shows: Good Cards = 2,881
3. Excel Sheet 1 Summary shows: G รวม = 2,884

### Investigation
```python
# Sheet 1 Summary data:
# G (บัตรดี) - รับที่ศูนย์: 2,881
# G (บัตรดี) - จัดส่ง: 3
# G (บัตรดี) - รวม: 2,884
# G (บัตรดี) - Unique Serial: 2,880 (pickup only, 1 duplicate)
# รวม Unique Serial Number (G): 2,883 (2,880 + 3)
```

### Root Cause
`get_summary_stats()` อ่านจาก Sheet 2 (บัตรดี - รับที่ศูนย์) เท่านั้น ไม่รวม Sheet 7 (บัตรจัดส่ง)

### Solution
แก้ไข `get_summary_stats()` ให้อ่านจาก Sheet 1 Summary โดยตรง:
```python
def get_summary_stats(self):
    # Read from Sheet 1 Summary
    summary_df = self.read_sheet('1.สรุปภาพรวม')

    for idx, row in summary_df.iterrows():
        cell = str(row.iloc[0])
        value = row.iloc[1]

        if 'G (บัตรดี) - รวม' in cell:
            good = int(str(value).replace(',', ''))
        elif 'รวม Unique Serial Number (G)' in cell:
            unique_serial_g = int(str(value).replace(',', ''))
        # ... etc
```

### Files Changed
- `services/excel_parser.py` - `get_summary_stats()`
- `pages/1_📤_Upload.py` - Added more stats display

---

## Bug #004: Date Parsing Error (Critical)

### Reported
- **Date**: 2026-01-28
- **Severity**: Critical
- **Status**: ✅ Fixed

### Description
กราฟแสดงข้อมูลวันที่ 12 Jan 2025 ซึ่งไม่มีข้อมูลที่ upload (upload เฉพาะ Oct, Nov, Dec 2025)

### Screenshot Evidence
Chart showed data point on Jan 12, 2025 with:
- Unique Serial: 1,644
- รับที่ศูนย์: 1,644
- จัดส่ง: 0
- บัตรเสีย: 29

### Investigation

#### Step 1: Check database
```sql
SELECT print_date, COUNT(*) FROM cards
WHERE print_date LIKE '2025-01%'
GROUP BY print_date;
-- Result: 2025-01-12: 1,673 cards
```

#### Step 2: Check raw Excel with openpyxl
```python
# Sheet 2 (Good Cards), Column 12 (วันที่พิมพ์)
Row 2: 20-11-2025 (type: str, format: General)
Row 9: 2025-05-11 00:00:00 (type: datetime, format: yyyy-mm-dd h:mm:ss)
```

### Root Cause
Excel ไฟล์มี date format ไม่สม่ำเสมอ:

| Cell Type | Raw Value | Pandas Reads As | Actual Date |
|-----------|-----------|-----------------|-------------|
| String | "20-11-2025" | Nov 20, 2025 ✅ | Nov 20, 2025 |
| Datetime | 2025-05-11 | May 11, 2025 ❌ | Nov 5, 2025 |

ปัญหา: Excel บันทึก datetime ผิด (สลับ day/month) ทำให้:
- 2025-05-11 → ควรเป็น Nov 5, 2025 (05-11-2025)
- 2025-03-11 → ควรเป็น Nov 3, 2025 (03-11-2025)
- 2025-01-12 → ควรเป็น Dec 1, 2025 (01-12-2025) *ในรายงานธันวาคม*

### Solution
เพิ่ม logic ตรวจจับ day/month swap ใน `parse_date_value()`:

```python
def parse_date_value(self, value, report_month: int = None):
    """Parse date with day/month swap detection."""
    if isinstance(value, (datetime, date)):
        result_date = value.date() if isinstance(value, datetime) else value

        # Check for day/month swap
        if report_month is not None:
            # If month doesn't match report but day equals report_month
            if result_date.month != report_month and result_date.day == report_month:
                # Likely swapped - correct it
                if result_date.month <= 12:  # Only if swap is valid
                    try:
                        corrected = date(result_date.year, result_date.day, result_date.month)
                        return corrected
                    except ValueError:
                        pass

        return result_date
```

### Test Cases
```python
# All tests pass:
(datetime(2025, 5, 11), 11) => 2025-11-05 ✅  # Swapped
(datetime(2025, 3, 11), 11) => 2025-11-03 ✅  # Swapped
(datetime(2025, 11, 5), 11) => 2025-11-05 ✅  # Already correct
("20-11-2025", 11) => 2025-11-20 ✅           # String format
(datetime(2025, 1, 12), 12) => 2025-12-01 ✅  # December report
```

### Data Re-import
```python
# Clear and re-import all 3 reports
DELETE FROM cards;
DELETE FROM delivery_cards;
DELETE FROM reports;

# Re-import with fixed parser
DataService.import_excel("ตุลาคม_2568.xlsx")    # Oct
DataService.import_excel("พฤศจิกายน_2568.xlsx") # Nov
DataService.import_excel("ธันวาคม_2568.xlsx")   # Dec
```

### Verification
```sql
-- Before fix:
SELECT print_date FROM cards WHERE print_date LIKE '2025-01%';
-- Result: 1,673 records (WRONG!)

-- After fix:
SELECT print_date FROM cards WHERE print_date LIKE '2025-01%';
-- Result: 0 records (CORRECT!)

-- November dates now correct:
SELECT DISTINCT print_date FROM cards
WHERE report_id = (SELECT id FROM reports WHERE filename LIKE '%พฤศจิกายน%')
ORDER BY print_date;
-- Result: All dates in 2025-11-XX range ✅
```

### Files Changed
- `services/excel_parser.py` - Added `report_month` parameter to `parse_date_value()`
- `services/data_service.py` - Pass `report_month` to all date parsing calls

### Lessons Learned
1. Excel date formats can be inconsistent within the same file
2. Always validate date ranges against expected report period
3. Consider adding date validation in import preview

---

## Summary Statistics

| Metric | Value |
|--------|-------|
| Total Bugs Fixed | 4 |
| Critical Bugs | 1 |
| High Severity | 2 |
| Medium Severity | 1 |
| Files Modified | 5 |
| Lines Changed | ~300 |

### Files Most Frequently Modified
1. `services/excel_parser.py` - 3 bugs
2. `services/data_service.py` - 3 bugs
3. `database/models.py` - 1 bug
4. `pages/1_📤_Upload.py` - 2 bugs
5. `app.py` - 1 bug
