# Rollback Guide — v2.3.0 (COPY Protocol + Duplicate Column Fix)

> Created: 2026-02-23
> Changes: 3 files modified (data_service.py, excel_parser.py, Upload.py)

---

## What Changed

| File | Change | Risk |
|------|--------|------|
| `services/data_service.py` | Rewrote `import_excel()` from ORM row-by-row to COPY protocol | High — core import logic |
| `services/excel_parser.py` | Added `df.loc[:, ~df.columns.duplicated()]` after rename in 8 methods | Low — additive fix |
| `pages/1_📤_Upload.py` | Added progress_callback + detailed import result display | Low — UI only |

---

## How to Rollback

### Option 1: Revert all 3 files (full rollback)

```bash
cd bio_dashboard

# Revert data_service.py to last commit before COPY rewrite
git checkout dd692eb -- services/data_service.py

# Revert excel_parser.py to last commit before duplicate column fix
git checkout 8f8b909 -- services/excel_parser.py

# Revert Upload.py to last commit before progress_callback
git checkout 09d84a7 -- "pages/1_📤_Upload.py"

# Commit the rollback
git add -A && git commit -m "Rollback v2.3.0 — revert to pre-COPY import"
git push origin main
```

### Option 2: Revert only data_service.py (keep parser fix + UI)

If the COPY protocol causes issues but the parser fix works fine:

```bash
git checkout dd692eb -- services/data_service.py

# Also revert Upload.py since progress_callback depends on new data_service
git checkout 09d84a7 -- "pages/1_📤_Upload.py"

git add -A && git commit -m "Rollback data_service.py — revert COPY protocol, keep parser fix"
git push origin main
```

### Option 3: Revert only excel_parser.py (unlikely needed)

```bash
git checkout 8f8b909 -- services/excel_parser.py
git add -A && git commit -m "Rollback excel_parser.py duplicate column fix"
git push origin main
```

---

## Verification After Rollback

1. Go to Upload page
2. Upload any Unified Report file
3. Verify it imports successfully
4. Check Overview page shows correct data

---

## Pre-rollback Commit Hashes (for reference)

| File | Last Known Good Commit | Description |
|------|----------------------|-------------|
| `services/data_service.py` | `dd692eb` | Session-based insert (ORM loop) |
| `services/excel_parser.py` | `8f8b909` | Monthly report header detection |
| `pages/1_📤_Upload.py` | `09d84a7` | Emergency Int64 fix |

---

## Notes

- The COPY protocol change is the highest risk. If `import_excel()` fails, rollback data_service.py first.
- The excel_parser.py fix is very safe — it only removes duplicate columns that cause `The truth value of a Series is ambiguous` error.
- Upload.py changes are purely cosmetic (progress bar + detailed results).
- After any rollback, Streamlit Cloud will auto-deploy when you push to main.
