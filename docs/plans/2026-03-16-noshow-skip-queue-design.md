# Design: No-Show Improvement + Skip Queue Metric

**Date:** 2026-03-16
**Status:** Approved

---

## Problem

No-Show calculation uses only QLog to determine who showed up:
```
No-Show = Appointment - QLog (has qlog_num)
```

This overcounts No-Show because some people get cards issued (BioRecord exists)
without going through the queue system (QLog missing). Causes:
- Queue system outage
- Operator bypasses queue for urgent cases
- All centers have queue machines, but not all transactions go through them

## Solution

### New Data Flow

```
Appointment (exclude CANCEL/EXPIRED)
    ├── Has QLog (qlog_num IS NOT NULL)      → "มา Check-in"
    ├── No QLog BUT has BioRecord            → "ไม่ผ่านตู้คิว" (NEW)
    └── No QLog AND no BioRecord             → "No-Show" (FIXED)
```

### New Formula

- `checked_in` = QLog unique appointment_code (has qlog_num) — unchanged
- `bio_served` = BioRecord unique appointment_id in date range — NEW query
- `skip_queue` = bio_served - checked_in (has Bio, no QLog) — NEW calc
- `no_show` = total_appts - checked_in - skip_queue — FIXED

### Approach

**Approach A (selected):** Fix in query layer — add one Bio query to
`get_appointment_service_stats()`, compute skip_queue as set difference.
Uses existing indexes, no schema changes needed.

## Files to Modify

| File | Changes |
|---|---|
| `pages/2_📈_Overview.py` | `get_appointment_service_stats()`: add Bio query, compute `skip_queue`, fix `no_show`, add metric card + chart series |
| `pages/6_🏢_By_Center.py` | Add "ไม่ผ่านตู้คิว" metric per branch |
| `pages/1_📤_Upload.py` | Chunked import for large Appointment CSV (579K+ rows): 50K chunks, progress bar, batch dedup |

**No changes needed:** models.py, connection.py (no schema changes)

## UI Layout

### Overview Metric Cards (5 → 6)

```
📅 นัดหมาย | 🏢 มา Check-in | ⚠️ ไม่ผ่านตู้คิว | ✅ ออกบัตรแล้ว | ❌ ไม่มา | 📊 อัตราออกบัตร
  10,000   |     8,000      |       500       |     8,300    |  1,500  |    97.6%
```

### Daily Chart (4 → 5 series)

- นัดหมาย (bar, blue)
- มา Check-in (bar, green)
- ออกบัตร (line, purple)
- ไม่ผ่านตู้คิว (bar, orange) — NEW
- ไม่มา (bar, red) — value decreases

## Upload Fix: Chunked Import

**Problem:** appointment130326.csv (579K rows) causes Streamlit timeout.

**Fix:**
- Read CSV in chunks (50K rows/chunk)
- Show progress bar during import
- Use COPY (bulk insert) per chunk
- Batch dedup check (chunk appointment_ids → query DB → filter)
