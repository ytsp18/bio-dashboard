# Changelog

All notable changes to Bio Dashboard project are documented in this file.

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
