-- ============================================================
-- Performance Indexes for Bio Dashboard
-- Project: bio-dashboard-fts (pdiucwdwgxweqyaeayhb)
-- Date: 2026-02-11
--
-- Addresses top slow queries from Query Performance report
-- All indexes created CONCURRENTLY to avoid table locks
-- ============================================================

-- ============================================================
-- 1. APPOINTMENTS TABLE
--    Slow: count(distinct appointment_id) WHERE appt_date + appt_status
--    Existing: ix_appointments_appt_date (appt_date only)
--    Missing: composite (appt_date, appt_status) + appointment_id for covering
-- ============================================================

-- Covers: WHERE appt_date >= $1 AND appt_date <= $2 AND appt_status = $3
-- Used by: Overview page appointment counts, daily breakdown
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_appointments_date_status_apptid
  ON public.appointments (appt_date, appt_status, appointment_id);

-- Drop duplicate indexes (appointment_id indexed twice)
-- ix_appointments_appointment_id and ix_appointments_appt_id are identical
DROP INDEX CONCURRENTLY IF EXISTS ix_appointments_appt_id;

-- ============================================================
-- 2. CARDS TABLE
--    Slow: count(distinct serial_number) WHERE print_date + print_status
--    Slow: big aggregation query with 13+ CASE WHEN on print_date range
--    Slow: DISTINCT branch_code full scan
--    Existing: ix_cards_status_date (print_date, print_status)
--             ix_cards_status_serial (print_status, serial_number)
-- ============================================================

-- Covers: WHERE print_date + print_status → count(distinct serial_number)
-- The existing ix_cards_status_date covers WHERE but not the DISTINCT column
-- This covering index includes serial_number to avoid table lookups
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_cards_date_status_serial
  ON public.cards (print_date, print_status, serial_number);

-- Covers: WHERE print_date + print_status → count(distinct work_permit_no)
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_cards_date_status_wpno
  ON public.cards (print_date, print_status, work_permit_no);

-- Covers: WHERE print_date + print_status + appointment_id subqueries
-- For "single G" count queries with HAVING count = 1
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_cards_date_status_apptid
  ON public.cards (print_date, print_status, appointment_id);

-- Covers: DISTINCT branch_code (avoid full table scan)
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_cards_branch_code_only
  ON public.cards (branch_code)
  WHERE branch_code IS NOT NULL AND branch_code != '';

-- ============================================================
-- 3. QLOGS TABLE
--    Slow: count(distinct appointment_code) WHERE qlog_date + qlog_status
--          + IN (subquery from appointments)
--    Existing: ix_qlogs_appt_code (appointment_code only)
--             ix_qlogs_date (qlog_date only)
-- ============================================================

-- Covers: WHERE qlog_date + qlog_status → count(distinct appointment_code)
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_qlogs_date_status_apptcode
  ON public.qlogs (qlog_date, qlog_status, appointment_code);

-- Covers: wait time SLA queries with qlog_type filter
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_qlogs_date_type_wait
  ON public.qlogs (qlog_date, qlog_type, wait_time_seconds)
  WHERE wait_time_seconds IS NOT NULL;

-- ============================================================
-- 4. BIO_RECORDS TABLE
--    Slow: subquery for appointment_id with print_date + print_status
--    Existing: ix_bio_records_date_status (print_date, print_status)
-- ============================================================

-- Covers: WHERE print_date + print_status → DISTINCT appointment_id
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_bio_date_status_apptid
  ON public.bio_records (print_date, print_status, appointment_id);

-- ============================================================
-- CLEANUP: Remove redundant indexes to reduce write overhead
-- ============================================================

-- ix_appointments_date duplicates ix_appointments_appt_date
DROP INDEX CONCURRENTLY IF EXISTS ix_appointments_date;

-- ix_bio_records_appt_id duplicates ix_bio_records_appointment_id
DROP INDEX CONCURRENTLY IF EXISTS ix_bio_records_appt_id;

-- ix_qlogs_qlog_date duplicates ix_qlogs_date
DROP INDEX CONCURRENTLY IF EXISTS ix_qlogs_qlog_date;

-- ============================================================
-- 5. DELIVERY_CARDS TABLE
--    Recommended by Supabase Index Advisor
--    Slow: count(distinct serial_number) WHERE print_status
-- ============================================================

-- Covers: WHERE print_status filter on delivery_cards
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_delivery_cards_print_status
  ON public.delivery_cards (print_status);

-- ============================================================
-- VERIFICATION
-- ============================================================
-- After running, check with:
--
-- SELECT indexname, tablename
-- FROM pg_indexes
-- WHERE schemaname = 'public'
-- AND tablename IN ('cards', 'appointments', 'qlogs', 'bio_records')
-- ORDER BY tablename, indexname;
--
-- Then reset pg_stat_statements to track improvement:
-- SELECT pg_stat_statements_reset();
-- ============================================================
