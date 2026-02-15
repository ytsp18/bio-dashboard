-- ============================================================
-- Bio Dashboard: Fix Slow Queries — Create Missing Indexes
-- Run on Supabase SQL Editor (pdiucwdwgxweqyaeayhb)
-- Date: 2026-02-16
-- ============================================================
-- Problem: All queries do full table scans because no indexes exist
-- on PostgreSQL (SQLAlchemy model indexes only apply to SQLite local DB)
--
-- Top slow queries all filter by: date range + status columns
-- Adding composite indexes will reduce mean query time from 800-2800ms to <50ms
--
-- NOTE: Using regular CREATE INDEX (not CONCURRENTLY) so this can run
-- in Supabase SQL Editor which wraps in a transaction.
-- Tables will be briefly locked during index creation.
-- ============================================================

-- =====================
-- TABLE: cards (heaviest — 13 of top 20 slow queries)
-- =====================

-- Q3,Q5,Q7,Q8: WHERE print_date >= $1 AND print_date <= $2 AND print_status = $3
CREATE INDEX IF NOT EXISTS idx_cards_print_date_status
  ON cards (print_date, print_status);

-- Q5,Q7: WHERE appointment_id IN (...) — subquery join
CREATE INDEX IF NOT EXISTS idx_cards_appointment_id
  ON cards (appointment_id)
  WHERE appointment_id IS NOT NULL AND appointment_id != '';

-- Q8: aggregate with serial_number checks
CREATE INDEX IF NOT EXISTS idx_cards_serial_number
  ON cards (serial_number)
  WHERE serial_number IS NOT NULL AND serial_number != '';

-- Q11: SELECT DISTINCT branch_code FROM cards
CREATE INDEX IF NOT EXISTS idx_cards_branch_code
  ON cards (branch_code)
  WHERE branch_code IS NOT NULL AND branch_code != '';

-- Center stats: GROUP BY branch_code + filter by print_date
CREATE INDEX IF NOT EXISTS idx_cards_branch_date
  ON cards (branch_code, print_date);

-- =====================
-- TABLE: appointments (Q4, Q6, Q9, Q10)
-- =====================

-- Q4,Q9: WHERE appt_date >= $1 AND appt_date <= $2 AND appt_status = $3
CREATE INDEX IF NOT EXISTS idx_appointments_date_status
  ON appointments (appt_date, appt_status);

-- Q6,Q10: subquery SELECT DISTINCT appointment_id
CREATE INDEX IF NOT EXISTS idx_appointments_appointment_id
  ON appointments (appointment_id);

-- =====================
-- TABLE: qlogs (Q6, Q10, Q12)
-- =====================

-- Q6: WHERE qlog_date >= $1 AND qlog_date <= $2 AND qlog_status = $3
CREATE INDEX IF NOT EXISTS idx_qlogs_date_status
  ON qlogs (qlog_date, qlog_status);

-- Q6,Q10: WHERE appointment_code IN (...)
CREATE INDEX IF NOT EXISTS idx_qlogs_appointment_code
  ON qlogs (appointment_code);

-- Q12: WHERE qlog_type = $10 AND wait_time_seconds IS NOT NULL
CREATE INDEX IF NOT EXISTS idx_qlogs_type_wait
  ON qlogs (qlog_type, wait_time_seconds)
  WHERE wait_time_seconds IS NOT NULL;

-- =====================
-- TABLE: bio_records (Q12 subquery)
-- =====================

-- Q12: WHERE print_date >= $1 AND print_status = $2
CREATE INDEX IF NOT EXISTS idx_bio_records_date_status
  ON bio_records (print_date, print_status);

-- Q12: WHERE appointment_id IS NOT NULL
CREATE INDEX IF NOT EXISTS idx_bio_records_appointment_id
  ON bio_records (appointment_id)
  WHERE appointment_id IS NOT NULL AND appointment_id != '';

-- ============================================================
-- VERIFY: Run after indexes are created
-- ============================================================
SELECT tablename, indexname
FROM pg_indexes
WHERE schemaname = 'public'
AND tablename IN ('cards', 'appointments', 'qlogs', 'bio_records')
ORDER BY tablename, indexname;
