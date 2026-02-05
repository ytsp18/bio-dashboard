# Changelog

All notable changes to Bio Dashboard project are documented in this file.

## [1.4.0] - 2026-02-05

### Added
- **Modern UI Metric Cards** (`utils/metric_cards.py`)
  - `render_metric_card()` - Card พร้อม gradient, shadow, trend indicators
  - `render_operation_summary()` - Panel สรุปสถานะการดำเนินงาน
  - `render_action_card()` - Card แบบ actionable พร้อมปุ่ม
  - `render_kpi_gauge()` - Progress bar พร้อม threshold colors
  - `render_mini_metric()` - Compact metric cards
  - `render_uniform_card()` - Uniform-sized metric cards
  - `render_card_grid()` - Grid layout for cards
  - `inject_metric_cards_css()` - CSS injection for styling
  - `calculate_trend()` - Calculate percentage change

### Changed
- **Overview Page UI Overhaul**
  - Operation Summary Panel แสดงสถานะรวม (ok/warning/critical)
  - Quick metrics row: บัตรดี, บัตรเสีย, สมบูรณ์, Anomaly, SLA, Work Permit
  - Alert banners สำหรับรายการที่ต้องตรวจสอบ
  - Metric cards มี gradient background และ shadow
  - เพิ่ม trend indicators (เทียบ day/week/month)
  - รายละเอียดการออกบัตร ใช้ uniform card layout
  - Anomaly section ใช้ action cards

### Files Added
- `utils/metric_cards.py` - New UI components module

### Files Modified
- `pages/2_📈_Overview.py` - Integrated new metric card components
- `__version__.py` - Bumped to 1.4.0

---

## [1.3.9] - 2026-01-31

### Added
- **Operation Summary Panel**
  - Dashboard-wide status indicator (ok/warning/critical)
  - Quick metrics row: บัตรดี, บัตรเสีย, สมบูรณ์, Anomaly, SLA ผ่าน, Work Permit
  - Alert banners for items requiring attention
  - Last updated timestamp

- **Enhanced Metric Cards for Operations**
  - Status badges: ✓ ปกติ (green), ! เตือน (yellow), !! วิกฤต (red)
  - Progress bars showing % towards target
  - Subtitle line for additional context (e.g., "Good Rate: 98.5%")
  - Alert mode with pulse animation for critical items
  - Improved trend indicators (day/week/month)

- **Action Cards for Anomaly Section**
  - Actionable cards with icon, title, description, count
  - Quick action buttons "➡️ ดูรายละเอียด" linking to relevant pages
  - Status-colored count badges
  - Replaces old simple metrics layout

- **Mini Metric Cards**
  - Compact cards for SLA summary section
  - Trend indicators with color coding

- **KPI Gauge Component**
  - Progress bar with color-coded thresholds
  - Automatic status badge based on value

### Changed
- **Overview Page Layout**
  - Operation Summary Panel at top after filters
  - Metric cards now show status badges and progress bars
  - Anomaly section redesigned with Action Cards
  - SLA summary uses mini metric cards

### Files Modified
- `utils/metric_cards.py` - New components:
  - `render_operation_summary()`
  - `render_action_card()`
  - `render_kpi_gauge()`
  - Enhanced `render_metric_card()` with new parameters
  - Enhanced `render_mini_metric()`
- `pages/2_📈_Overview.py` - Integrated new components

---

## [1.3.8] - 2026-01-31

### Added
- **Workload Forecast Feature**
  - New "ปริมาณการนัดหมาย" page showing upcoming appointments
  - Capacity limit line (green) in daily appointment charts
  - Compare appointment volume vs total capacity from BranchMaster
  - Summary metrics: Today, Tomorrow, 7 days, 30 days ahead
  - By center breakdown with usage percentage
  - Over-capacity warnings

- **Treemap Visualization Enhancements**
  - Show branch_code in treemap boxes (compact view)
  - Rich tooltip on hover with full details:
    - 📍 Full center name
    - 🔢 Branch code
    - 📊 Appointment count
    - 📈 Capacity info
    - Status emoji (🟢🟡🔴⚫)
  - Daily/Monthly view toggle
  - Filter by center type (แรกรับ OB / บริการ SC)

- **Separate Charts by Center Type**
  - Chart 1: ศูนย์แรกรับ (OB) with OB capacity line
  - Chart 2: ศูนย์บริการ (SC) with SC capacity line
  - Each chart has its own average line
  - Added 80% warning line (yellow dashed) to both charts

- **Treemap Color Thresholds**
  - 🟢 Green = Normal (<80%)
  - 🟡 Yellow = Warning (80-89%)
  - 🔴 Red = Over capacity (≥90%)
  - ⚫ Gray = No capacity data

### Changed
- **Page Menu Reordering**
  - Forecast page now appears after Overview (was 2.5_, now 3_)
  - All subsequent pages renumbered (Search: 4_, By Center: 5_, etc.)
  - Profile page moved to 10_

- **Mobile Unit Exclusion**
  - Mobile units (branch_code contains `-MB-`) excluded from total capacity
  - Fixed detection: changed from `startswith('MB-')` to `'-MB-' in branch_code`
  - Applies to both Overview and Forecast pages

### Fixed
- **JSON Serialization Error in Forecast**
  - Removed lambda formatter from ECharts tooltip (not JSON serializable)

- **Total Capacity Calculation**
  - Was showing 24,860 (incorrect) - included mobile units
  - Now shows 12,540 (correct) - excludes 77 mobile units

### Files Modified
- `pages/2_📈_Overview.py` - Added capacity line, fixed mobile unit detection
- `pages/3_📆_Forecast.py` - New page with detailed forecast, treemap, separate OB/SC charts
- `pages/1_📤_Upload.py` - Duplicate check before import
- All pages renumbered to accommodate Forecast after Overview

---

## [1.3.7] - 2026-01-31

### Security
- **SQL Injection Vulnerability Fix**
  - Problem: `database/connection.py` had SQL Injection vulnerability in search functions
  - Using f-string formatting to build SQL queries with user input
  - Solution: Changed to parameterized queries with SQLAlchemy `text()` and `:param` placeholders
  - Risk Level: HIGH - Could allow attackers to execute arbitrary SQL commands
  - Files: `database/connection.py`
  - Commit: `afdeb03`

- **Credential Rotation**
  - Rotated database password after security audit
  - Generated new cookie key (64-char hex)
  - Updated Streamlit Cloud secrets
  - Old credentials invalidated

- **Security Audit Findings**
  - ✅ Fixed: SQL Injection in search queries
  - ✅ Fixed: Credential exposure (password rotation)
  - ⚠️ Warning: RLS (Row Level Security) disabled on Supabase tables
    - Not critical for this app (uses direct connection with password, not Supabase API)
    - Can be enabled later for additional security layer

### Fixed
- **Supabase Connection Issues**
  - Problem: "Circuit breaker open" error after credential rotation
  - Root cause: IP was banned due to repeated failed connection attempts
  - Solution: Unban IP from Supabase Network Bans + wait for circuit breaker reset
  - Database restart required to clear connection pool state

### Infrastructure
- **Supabase Configuration**
  - Using Session Pooler (IPv4 compatible) for Streamlit Cloud
  - Connection URL: `aws-1-ap-southeast-1.pooler.supabase.com:5432`
  - IPv6 direct connection not supported on Streamlit Cloud

---

## [1.3.6] - 2026-01-31

### Added
- **Duplicate Data Check for All Upload Types**
  - Appointment: Check `appointment_id` - ❌ **บล็อก** ถ้าพบซ้ำ
  - QLog: Check `qlog_id` - ❌ **บล็อก** ถ้าพบซ้ำ
  - Card Delivery: Check `serial_number` - ❌ **บล็อก** ถ้าพบซ้ำ
  - Bio Raw: Check `serial_number + print_status` - ⚠️ **Warning เท่านั้น** (อนุญาตซ้ำสำหรับ verify G/B status)
  - Files: `pages/1_📤_Upload.py`

### Fixed
- **Bio Raw Upload: emergency column type error**
  - Problem: `invalid input syntax for type integer: "0.0"` when using COPY
  - Root cause: Excel data has float values (0.0) but PostgreSQL expects integer
  - Solution: Convert emergency column from float to int before COPY export
  - Files: `pages/1_📤_Upload.py`

---

## [1.3.5] - 2026-01-31

### Added
- **Card Delivery Upload Support**
  - New Tab "📦 Card Delivery" in Upload page
  - Support for Card-Delivery-Report-*.xlsx files
  - Handles appointment IDs starting with 68/69 (delivery appointments)
  - No SLA time data (different from Bio Raw)
  - Database models: `CardDeliveryUpload`, `CardDeliveryRecord`
  - Uses COPY protocol for fast bulk insert
  - Test: 196 records (G: 191, B: 5) uploaded successfully
  - Files: `database/models.py`, `pages/1_📤_Upload.py`

### Fixed
- **numpy.int64 PostgreSQL Error**
  - Problem: `can't adapt type 'numpy.int64'` when inserting Card Delivery
  - Solution: Convert pandas value_counts() results to Python int
  - Files: `pages/1_📤_Upload.py`

---

## [1.3.4] - 2026-01-31

### Performance
- **Optimized Bulk Insert for Large Files (30MB+)**
  - Problem: Uploading 6.4MB file (24K records) took extremely long, stuck at 30% progress
  - Root cause: SQLAlchemy `insert()` with batch is slow due to parameter binding overhead
  - Solution v1: Use `psycopg2.extras.execute_values()` - 10-50x faster
  - Solution v2: Upgrade to PostgreSQL `COPY` protocol - additional 2-5x faster
  - Test results:
    - 6.4MB (24K records): ✅ Fast
    - 31MB (130K records): ✅ Fast (appointment-january.csv)
  - Changes:
    - All uploads now use `COPY FROM STDIN WITH CSV`
    - SQLite fallback: Use `pandas.to_sql()` with `method='multi'`
  - Files: `pages/1_📤_Upload.py`

---

## [1.3.3] - 2026-01-29

### Fixed
- **Unique Serial (G) Calculation**
  - Problem: Dashboard showed 21,616 instead of correct 21,599
  - Root cause: Simple addition of center + delivery counts instead of true unique count
  - Solution: Use `UNION ALL` + `COUNT(DISTINCT)` to count unique serials across both tables
  - Files: `pages/2_📈_Overview.py`

- **Unique Serial Reading from Excel**
  - Problem: Preview showed wrong Unique Serial value
  - Root cause: Reading from wrong cell "รวม Unique Serial Number (G)" (Row 74) instead of "G (บัตรดี) - Unique Serial" (Row 12)
  - Solution: Read from correct cell with priority for "G Unique Serial หลังหัก Validation" (Row 106) when available
  - Files: `services/excel_parser.py`

- **Bad Cards Count Missing Delivery**
  - Problem: Bad cards count didn't include delivery cards with B status
  - Solution: Count B cards from both `Card` and `DeliveryCard` tables
  - Files: `pages/2_📈_Overview.py`

- **Import Stats Not Matching Excel**
  - Problem: After import showed 21,586 instead of 21,603
  - Solution: Read total_good, total_bad, total_records from Summary Sheet (most accurate)
  - Files: `services/data_service.py`

- **Monthly Report Parsing Failed**
  - Problem: Monthly reports (Jan 2026) not displaying in Overview
  - Root cause: Monthly files have title rows at top (e.g., "รายการบัตรดี (G) - จำนวน 95,431 รายการ") before column headers
  - Solution: Detect header row containing 'ลำดับ' and restructure dataframe
  - Files: `services/excel_parser.py` - `parse_good_cards()`, `parse_bad_cards()`

### Added
- **Refresh Button on Overview Page**
  - Added "🔄 รีเฟรช" button to clear cache and reload data
  - Reduced date range cache from 5 minutes to 1 minute
  - Files: `pages/2_📈_Overview.py`

### Changed
- **Unique Serial Priority Reading**
  - Priority 1: "G Unique Serial หลังหัก Validation" (post-validation deduction)
  - Priority 2: "G (บัตรดี) - Unique Serial" (fallback)
  - Supports both daily and monthly report formats

---

## [1.3.2] - 2026-01-29

### Changed
- **Anomaly Page - Simplified and Focused**
  - Removed comparison table, comparison chart, and anomaly rate sections
  - Removed SLA-related tabs (SLA>12min, Wait>1hr) - to be handled separately
  - Removed Serial Number duplicates, bad cards sections
  - Summary table now shows only items requiring review:
    - รายการนัดหมายที่มีบัตรดีมากกว่า 1 ใบ (Appt ID G>1)
    - Card ID ที่มีบัตรดีมากกว่า 1 ใบ (รหัสประจำตัวคนต่างด้าว)
  - 4 focused tabs: ผิดวัน, ผิดศูนย์, Appt G>1, Card ID G>1

### Added
- **Anomaly Page - Wrong Branch Tab**
  - Re-added "ผิดศูนย์" (Wrong Branch) tab
  - Shows cards issued at different center than appointment
  - Includes "สรุปตามศูนย์ที่ออกบัตร" summary table
  - Export to Excel with summary sheet

### Fixed
- **Anomaly Logic - Match Excel Report**
  - Changed Anomaly G>1 counting from Appointment ID to Card ID
  - Now matches Excel report exactly:
    - ออกบัตรหลายใบรวม: 120 ✓
    - Reissue ปกติ: 114 ✓
    - Anomaly G>1: 6 ✓

---

## [1.3.1] - 2026-01-28

### Added
- **Anomaly Page - Summary Statistics Table**
  - Added summary statistics section at the top of Anomaly page
  - Shows: G Unique Appointment ID, Appt ID G>1, บัตรไม่สมบูรณ์
  - Shows: ออกบัตรหลายใบรวม (จำนวนบัตร), Reissue ปกติ (มี B ก่อน G), Anomaly G>1
  - Beautiful gradient styling with gold-highlighted values

### Fixed
- **Anomaly Page - Layout Improvements**
  - Fixed search section layout for better symmetry (search input = button widths)
  - Fixed multiselect text color to contrast with textbox background
  - Added CSS styling for multiselect tags (dark blue background, white text)

---

## [1.3.0] - 2026-01-28

### Security
- **Audit Logging System**
  - Added `AuditLog` table for tracking user actions (login, logout, upload, delete)
  - Added `LoginAttempt` table for brute force protection
  - Login locked after 5 failed attempts for 15 minutes
  - All security events logged with Thailand timezone

- **Session Security**
  - Reduced cookie expiry from 30 days to 7 days

### Fixed
- **Overview Page Logic Corrections**
  - Fixed "บัตรจัดส่ง" count - now uses `DeliveryCard` table (Sheet 7) correctly
  - Fixed "บัตรสมบูรณ์" count - now uses Unique Serial instead of row count
  - Fixed "ข้อมูลไม่ครบ" - checks all 4 required fields (Appt ID, Card ID, Serial, Work Permit)
  - All metrics now match Excel report exactly:
    - Unique SN รับที่ศูนย์: 2,880 ✓
    - Unique SN จัดส่ง: 3 ✓
    - รวม Unique SN (G): 2,883 ✓
    - บัตรสมบูรณ์: 2,874 ✓
    - Appt G > 1: 3 ✓
    - ข้อมูลไม่ครบ: 0 ✓
    - Unique Work Permit: 2,872 ✓

- **By Center Page**
  - Fixed slider error when center count < 5 (StreamlitAPIException)

### Added
- **Admin Panel - Audit Logs Tab**
  - View all system activity logs
  - Filter by action type (login, logout, upload, delete)
  - Filter by username
  - Export logs to CSV

### Changed
- **Overview Summary Cards Redesign**
  - Row 1: Unique SN (รับที่ศูนย์, จัดส่ง, รวม), บัตรเสีย
  - Row 2: บัตรสมบูรณ์, Appt G>1, ข้อมูลไม่ครบ, Unique Work Permit
  - Added "สรุปบัตรสมบูรณ์" detail section

---

## [1.2.2] - 2026-01-28

### Performance
- **Partial Re-render with st.fragment**
  - Added `@st.fragment` decorator for Overview page chart section
  - Chart now renders independently from other page sections
  - Reduces unnecessary re-renders when interacting with chart elements

---

## [1.2.1] - 2026-01-28

### Performance
- **User Authentication Caching**
  - Added caching for user authentication queries (5 minutes TTL)
  - Added caching for user role/permission checks (5 minutes TTL)
  - Reduces database queries from every page load to once per 5 minutes

---

## [1.2.0] - 2026-01-28

### Added
- **Database-based User Management**
  - Migrated user authentication from `config.yaml` to Supabase database
  - User data now persists across Streamlit Cloud deployments
  - New database models: `User`, `PendingRegistration`, `SystemSetting`
  - Auto-migration from config.yaml on first startup

### Security
- **Cookie Key Security Improvement**
  - Moved cookie key from `config.yaml` to Streamlit secrets
  - Cookie key no longer stored in Git repository
  - Added fallback: random session key if secrets not configured

- **Secrets Management**
  - Database URL stored only in `secrets.toml` (not in code)
  - Cookie configuration stored in `secrets.toml`
  - Removed credentials section from `config.yaml`

### Changed
- `auth/authenticator.py` - Now reads credentials from database
- `auth/permissions.py` - Gets user role from database
- `auth/__init__.py` - Imports from `db_user_manager` instead of `user_manager`
- `app.py` - Added user migration on startup

### Fixed
- User registrations no longer lost after Streamlit Cloud redeploy
- Approved users now persist in database

### Configuration
Streamlit Cloud secrets now requires only:
```toml
[database]
url = "postgresql://..."

[cookie]
key = "<random-64-char-hex>"
name = "bio_dashboard_auth"
expiry_days = 30
```

---

## [1.1.2] - 2026-01-28

### Added
- **Database Indexes for Performance Optimization**
  - Added 9 indexes on `cards` table for faster queries:
    - `ix_cards_print_date` - Date range filtering
    - `ix_cards_print_status` - Status filtering (G/B/NULL)
    - `ix_cards_status_date` - Combined status + date queries
    - `ix_cards_serial` - Serial number search
    - `ix_cards_appt` - Appointment ID search
    - `ix_cards_branch` - Branch code filtering
    - `ix_cards_sla_over` - Partial index for SLA violations
    - `ix_cards_wrong_branch` - Partial index for wrong branch anomalies
    - `ix_cards_wrong_date` - Partial index for wrong date anomalies

### Performance
- **Query Performance Improvements**:
  - Count by status: Uses Index Only Scan (~20ms for 81K records)
  - Date range filter: Uses Index Only Scan (~0.05ms)
  - Anomaly queries: Use partial indexes for efficient filtering

### Changed
- Added `@st.cache_data` decorators for query caching (TTL: 30-60 seconds)
- Added `@st.cache_resource` for database connection warming
- Optimized connection pool settings for Streamlit Cloud serverless environment

---

## [1.1.1] - 2026-01-28

### Fixed
- **Critical: Database timeout on large imports**
  - Problem: Uploading files with 50K+ records caused Supabase timeout, cards table stayed empty
  - Solution: Added batch flush every 500 records to prevent connection timeout
  - Files: `services/data_service.py`

### Changed
- Migrated to new Supabase project (`bio-dashboard-fts`) for clean database
- Updated Session Pooler URL to `aws-1-ap-southeast-1`

---

## [1.1.0] - 2026-01-28

### Added
- **Supabase PostgreSQL Cloud Database Support**
  - Migrated from local SQLite to Supabase cloud database
  - Data now stored on cloud for better accessibility and reliability
  - Supports Session Pooler connection for IPv4 networks

### Configuration
- Added `.streamlit/secrets.toml` for database configuration
- Database URL format: `postgresql://postgres.xxx:password@aws-xxx.pooler.supabase.com:5432/postgres`

### Changed
- `database/connection.py` now supports both SQLite (local) and PostgreSQL (cloud)
- Automatic fallback to SQLite if no cloud database configured

### How to Switch Database
1. **Use Supabase (cloud)**: Add `secrets.toml` with database URL
2. **Use SQLite (local)**: Remove `secrets.toml` file

---

## [1.0.4] - 2026-01-28

### Fixed
- **Critical: Date parsing error causing chart to show wrong dates**
  - Problem: Chart displayed data on Jan 12, 2025 which didn't exist in uploaded data
  - Root cause: Excel files had inconsistent date formats - some cells stored as string "DD-MM-YYYY", others as datetime objects with day/month swapped
  - Solution: Enhanced `parse_date_value()` with `report_month` parameter to detect and correct day/month swaps
  - Files: `services/excel_parser.py`, `services/data_service.py`

### Changed
- Re-imported all data (Oct, Nov, Dec 2568) with corrected date parsing
- All dates now correctly display within their respective months

## [1.0.3] - 2026-01-28

### Fixed
- **Summary statistics not matching Excel Summary sheet**
  - Problem: Dashboard showed 2,881 good cards, Excel Summary showed 2,884
  - Root cause: Reading from Sheet 2 only (pickup cards), missing delivery cards from Sheet 7
  - Solution: Modified `get_summary_stats()` to read directly from Sheet 1 Summary

### Added
- New statistics fields:
  - `good_pickup`: Good cards received at center
  - `good_delivery`: Good cards via delivery
  - `unique_serial_g`: Total unique serial numbers (G)

### Changed
- Upload preview now shows additional statistics:
  - Good cards - pickup
  - Good cards - delivery
  - Unique Serial (G)

## [1.0.2] - 2026-01-28

### Fixed
- **Good rate calculation error**
  - Problem: Good rate showed 94.67% instead of correct 98.32%
  - Root cause: Dividing by total records including NULL status cards
  - Solution: Calculate good rate using only printed cards (G + B)

```python
# Before (wrong)
good_rate = good / total * 100

# After (correct)
printed_total = good + bad
good_rate = good / printed_total * 100
```

### Changed
- Updated `get_dashboard_stats()` in `data_service.py`
- Updated `app.py` dashboard display

## [1.0.1] - 2026-01-28

### Added
- **DeliveryCard model** for Sheet 7 (บัตรจัดส่ง) data
- Delivery card import functionality in data service
- Delivery card count display in Upload page preview

### Fixed
- SQLAlchemy mapper error for `delivery_cards` relationship

### Changed
- Updated `database/models.py` with DeliveryCard model
- Updated `services/data_service.py` with delivery import logic
- Updated `pages/1_📤_Upload.py` with delivery count display

## [1.0.0] - 2026-01-28

### Added
- Initial release of Bio Dashboard
- Streamlit-based web interface
- SQLite database with SQLAlchemy ORM
- Excel parser for Bio Unified Report files
- Pages:
  - Upload: File upload with preview
  - Reports: Report listing and management
  - Search: Data search functionality
  - Analytics: Charts and statistics
  - Centers: Center-based analysis
  - Settings: Application settings

### Features
- Multi-sheet Excel parsing (23 sheets)
- Support for both daily and monthly report formats
- Data import with duplicate detection
- Interactive charts using Plotly
- Date range filtering
- Summary statistics calculation

---

## Migration Notes

### From 1.0.3 to 1.0.4
**Important**: Re-import all data after updating to fix date parsing issues.

```python
# Clear existing data
DELETE FROM cards;
DELETE FROM delivery_cards;
DELETE FROM reports;

# Re-import all reports through the Upload page
```

### From 1.0.0 to 1.0.1
Run database migration to add `delivery_cards` table:

```sql
CREATE TABLE IF NOT EXISTS delivery_cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL,
    appointment_id VARCHAR(50),
    serial_number VARCHAR(20),
    print_status VARCHAR(10),
    card_id VARCHAR(20),
    work_permit_no VARCHAR(20),
    FOREIGN KEY (report_id) REFERENCES reports(id)
);
```
