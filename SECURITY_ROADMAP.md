# Security Roadmap — Bio Dashboard (bio-dashboard-fts)

> Project ID: `pdiucwdwgxweqyaeayhb`
> Created: 2026-02-11
> Status: Phase 1 Ready

---

## Current State

- **22 tables** in `public` schema have **RLS disabled**
- Supabase exposes PostgREST API → anon key can read/write ALL data
- App connects via Python backend (SQLAlchemy) → not affected by RLS
- Authentication: Streamlit Authenticator + `users` table (bcrypt)
- Authorization: 3 roles (`admin`, `user`, `viewer`) — app-level only

---

## Phase 1: Block Anonymous API Access (Critical)

**Goal:** Enable RLS on all 22 tables + allow only authenticated users
**Impact:** Fixes all 22 security errors. Zero impact on Streamlit app.
**Effort:** ~15 minutes (run 1 SQL file)

### What it does:
- `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` on all tables
- Creates `"Authenticated full access"` policy on each table
- Blocks anon key from accessing any data via PostgREST API
- App (using service_role or direct connection) continues working normally

### Tables:
| Group | Tables |
|---|---|
| Report Data | `reports`, `cards`, `bad_cards`, `center_stats`, `anomaly_sla`, `wrong_centers`, `complete_diffs`, `delivery_cards` |
| Raw Uploads | `appointment_uploads`, `appointments`, `qlog_uploads`, `qlogs`, `bio_uploads`, `bio_records`, `card_delivery_uploads`, `card_delivery_records` |
| User Management | `users`, `pending_registrations`, `login_attempts`, `audit_logs` |
| System | `system_settings`, `branch_master` |

### SQL File:
```
sql/phase1_enable_rls.sql
```

### How to apply:
1. Open Supabase Dashboard → SQL Editor
2. Paste contents of `sql/phase1_enable_rls.sql`
3. Run
4. Verify: Security Advisor should show 0 errors

### Rollback:
```sql
-- If something goes wrong (per table):
ALTER TABLE public.<table_name> DISABLE ROW LEVEL SECURITY;
```

---

## Phase 2: Role-Based Policies (Recommended)

**Goal:** Enforce Streamlit roles at database level
**Impact:** viewer=SELECT only, user=SELECT+INSERT+UPDATE, admin=full access
**Effort:** Medium — requires mapping Streamlit users → Supabase Auth
**Prerequisite:** Decide how to map Streamlit users to Supabase auth.uid()

### Design Decisions Needed:
1. **Auth Mapping:** How to link Streamlit `users.username` → Supabase `auth.users.id`?
   - Option A: Use Supabase Auth for login (replace Streamlit Authenticator)
   - Option B: Use service_role for all app queries, keep RLS for API-only protection
   - Option C: Store `supabase_uid` in Streamlit `users` table, use custom JWT

2. **Policy Structure:**
```sql
-- Example: viewer can only SELECT
CREATE POLICY "viewer_select" ON cards
  FOR SELECT TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM users
      WHERE users.supabase_uid = auth.uid()
      AND users.role IN ('admin', 'user', 'viewer')
    )
  );

-- Example: only admin/user can INSERT
CREATE POLICY "user_insert" ON cards
  FOR INSERT TO authenticated
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM users
      WHERE users.supabase_uid = auth.uid()
      AND users.role IN ('admin', 'user')
    )
  );

-- Example: only admin can DELETE
CREATE POLICY "admin_delete" ON cards
  FOR DELETE TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM users
      WHERE users.supabase_uid = auth.uid()
      AND users.role = 'admin'
    )
  );
```

3. **Sensitive Tables (stricter policies):**

| Table | SELECT | INSERT | UPDATE | DELETE |
|---|---|---|---|---|
| `users` | own record or admin | admin only | own record or admin | admin only |
| `pending_registrations` | admin only | anyone (self-register) | admin only | admin only |
| `audit_logs` | admin only | system only | never | never |
| `login_attempts` | admin only | system only | never | admin only |
| `system_settings` | all authenticated | admin only | admin only | admin only |
| `branch_master` | all authenticated | admin only | admin only | admin only |
| Data tables (reports, cards, etc.) | all authenticated | admin + user | admin + user | admin + user |

### SQL File (future):
```
sql/phase2_role_based_policies.sql
```

---

## Phase 3: Branch-Level Data Isolation (Optional)

**Goal:** Users see only data from their assigned branches
**Impact:** True multi-tenant data isolation
**Effort:** High — requires schema changes + app logic changes
**Prerequisite:** Phase 2 completed + branch assignment feature

### Schema Changes Needed:
```sql
-- Add branch assignment to users
ALTER TABLE users ADD COLUMN allowed_branches TEXT[];
-- Example: {'0100', '0200', '0300'}

-- Or create a separate mapping table
CREATE TABLE user_branch_access (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id),
  branch_code VARCHAR(20),
  UNIQUE(user_id, branch_code)
);
```

### Policy Example:
```sql
CREATE POLICY "branch_isolation" ON cards
  FOR SELECT TO authenticated
  USING (
    -- Admin sees all
    EXISTS (
      SELECT 1 FROM users
      WHERE supabase_uid = auth.uid() AND role = 'admin'
    )
    OR
    -- Others see only their branches
    branch_code IN (
      SELECT unnest(allowed_branches)
      FROM users
      WHERE supabase_uid = auth.uid()
    )
  );
```

### App Changes Needed:
- Admin Panel: UI to assign branches to users
- `permissions.py`: Add `get_user_branches()` function
- Data queries: Add automatic branch filtering (defense-in-depth with RLS)

### SQL File (future):
```
sql/phase3_branch_isolation.sql
```

---

## Phase 4: Advanced Security Hardening (Nice-to-Have)

### 4.1 Audit Log Protection
```sql
-- Make audit_logs append-only (no UPDATE/DELETE even for admin)
CREATE POLICY "audit_append_only" ON audit_logs
  FOR INSERT TO authenticated
  WITH CHECK (true);
-- No SELECT/UPDATE/DELETE policies = nobody can read/modify via API
```

### 4.2 Rate Limiting (Supabase Edge Functions)
- Limit API calls per user per minute
- Protect against brute-force via PostgREST

### 4.3 Column-Level Security
- Hide `password_hash` from `users` table in API responses
- Use Supabase Views or column grants

### 4.4 Backup & Recovery
- Enable Supabase Point-in-Time Recovery (PITR)
- Regular backup schedule

---

## Progress Tracker

| Phase | Status | Date | Notes |
|---|---|---|---|
| Phase 1: Block Anon Access | **Done** | 2026-02-11 | RLS enabled on 22 tables, Security Advisor 0 errors |
| Performance: Index Optimization | **Done** | 2026-02-11 | 9 new indexes, 20 duplicates dropped (~58 MB saved) |
| Data: Skip Duplicate on Upload | Planning | - | Bio Raw / Appointment / QLog / Delivery upload ทั้งหมด |
| Data: Date Range from Bio Raw | Planning | - | Overview date filter ดึงแค่ cards table |
| Phase 2: Role-Based Policies | Planning | - | Need auth mapping decision |
| Phase 3: Branch Isolation | Future | - | Need branch assignment feature |
| Phase 4: Advanced Hardening | Future | - | Nice-to-have |

---

## Quick Reference

### Check current RLS status:
```sql
SELECT tablename,
       rowsecurity
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;
```

### Check existing policies:
```sql
SELECT schemaname, tablename, policyname, permissive, roles, cmd
FROM pg_policies
WHERE schemaname = 'public'
ORDER BY tablename, policyname;
```

---

---

## Pending Items (Data Quality)

### Skip Duplicate Records on Upload

**Goal:** ป้องกันข้อมูลซ้ำเมื่ออัปโหลดไฟล์เดิมหลายรอบ
**Scope:** Bio Raw, Appointment, QLog, Card Delivery
**Current behavior:** แสดง ⚠️ warning แต่ยัง insert ได้ → ข้อมูลซ้ำ นับซ้ำ

**Logic ที่วางแผนไว้:**
- Key: `serial_number + print_status` (Bio Raw), `appointment_id` (Appointment), etc.
- Query existing keys ก่อน insert
- Filter เฉพาะ row ที่ไม่มีใน DB แล้วค่อย COPY
- แสดงผล: "นำเข้า X | ข้ามซ้ำ Y"

**ประเด็นต้องระวัง:**
1. `appointment_id` เดียวกันมีหลาย `serial_number` (reprint) → ต้องชัดว่า key คืออะไร
2. `serial_number` null/empty → key จะเป็น `None_G` → filter ผิดพลาด
3. `BioUpload` metadata (`total_records`, `total_good`, `total_bad`) ต้องคำนวณ **หลัง skip** ไม่ใช่จากไฟล์
4. Race condition: 2 คน upload พร้อมกัน → ต้องมี DB unique constraint เป็น safety net
5. Pages ที่นับจาก `bio_records` โดยตรง (Overview, By Center, Queue Slots) ต้องทดสอบหลัง implement

---

### Date Range Filter ไม่รวม Bio Raw

**Goal:** Overview date filter สามารถเลือกวันที่ที่มีข้อมูล Bio Raw แม้ยังไม่มี Unified Report
**Current behavior:** `get_date_range()` ดึง max date จาก `cards` table เท่านั้น → ถ้าอัปโหลด Bio Raw แต่ยังไม่มี Unified Report → วันที่ใหม่เลือกไม่ได้

**แนวทางแก้:**
- Option A: ดึง max date จาก `MAX(cards.print_date, bio_records.print_date)` → เปิด filter ได้ทันที แต่บาง section อาจว่างถ้ายังไม่มี Unified Report
- Option B: รออัปโหลด Unified Report → ข้อมูลครบทุก section

**ประเด็นต้องระวัง:**
- ถ้าใช้ Option A บาง section (Complete Diff, By Center จาก cards) จะว่างในช่วงวันที่ที่มีแค่ Bio Raw
- ต้องแจ้ง user อย่างชัดเจนว่า section ไหนยังไม่มีข้อมูล

---

## Change Log

### 2026-02-22 — Data Quality Issues Identified
- พบว่า Bio Raw upload ไม่มี skip duplicate → อัปโหลดซ้ำได้ → นับซ้ำ
- พบว่า Overview date filter ไม่รวม bio_records → เลือกวันที่ กพ ไม่ได้หลัง upload Bio Raw

### 2026-02-11 — Initial Security + Performance Optimization

**Security — Phase 1 (RLS):**
- Enabled RLS on all 22 public tables
- Created `authenticated_full_access` policy on each table
- Security Advisor: 22 errors → **0 errors**
- SQL: `sql/phase1_enable_rls.sql`

**Performance — New Indexes (9 total):**
| Index | Table | Type |
|---|---|---|
| `ix_appointments_date_status_apptid` | appointments | Composite covering |
| `ix_cards_date_status_serial` | cards | Composite covering |
| `ix_cards_date_status_wpno` | cards | Composite covering |
| `ix_cards_date_status_apptid` | cards | Composite covering |
| `ix_cards_branch_code_only` | cards | Partial (NOT NULL) |
| `ix_qlogs_date_status_apptcode` | qlogs | Composite covering |
| `ix_qlogs_date_type_wait` | qlogs | Partial (NOT NULL) |
| `ix_bio_date_status_apptid` | bio_records | Composite covering |
| `ix_delivery_cards_print_status` | delivery_cards | Single (Index Advisor) |
- SQL: `sql/performance_indexes.sql`

**Cleanup — Duplicate Indexes Dropped (20 total):**
- Round 1 (from performance_indexes.sql): 4 duplicates
  - `ix_appointments_appt_id`, `ix_appointments_date`, `ix_bio_records_appt_id`, `ix_qlogs_qlog_date`
- Round 2 (from drop_duplicate_indexes.sql): 16 duplicates
  - Tables: bio_records, branch_master, card_delivery_records, cards (×5), center_stats, complete_diffs, delivery_cards, qlogs, users (×2)
- Total space saved: ~58 MB
- Performance Advisor: 11 warnings → **0 warnings**
- SQL: `sql/drop_duplicate_indexes.sql`
- Rollback: `sql/rollback_duplicate_indexes.sql`

**SQL Files Created:**
| File | Purpose |
|---|---|
| `sql/phase1_enable_rls.sql` | Phase 1 RLS — enable + authenticated policy |
| `sql/performance_indexes.sql` | New composite/covering indexes |
| `sql/drop_duplicate_indexes.sql` | Drop 16 duplicate indexes |
| `sql/rollback_duplicate_indexes.sql` | Rollback — recreate dropped indexes |
