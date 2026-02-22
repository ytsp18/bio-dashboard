-- ============================================================
-- Drop Duplicate Indexes — Bio Dashboard
-- Project: bio-dashboard-fts (pdiucwdwgxweqyaeayhb)
-- Date: 2026-02-11
--
-- Removes 16 exact duplicate indexes to reduce write overhead
-- and storage waste (~58 MB total)
--
-- IMPORTANT: Run each statement ONE AT A TIME
-- (DROP INDEX CONCURRENTLY cannot run inside a transaction block)
-- ============================================================

-- ============================================================
-- TABLE: bio_records (11 MB saved)
-- Keep: ix_bio_records_serial
-- Drop: ix_bio_records_serial_number (same: btree serial_number)
-- ============================================================
DROP INDEX CONCURRENTLY IF EXISTS ix_bio_records_serial_number;

-- ============================================================
-- TABLE: branch_master (16 kB saved)
-- Keep: ix_branch_master_branch_code (UNIQUE)
-- Drop: ix_branch_master_code (same: btree branch_code)
-- ============================================================
DROP INDEX CONCURRENTLY IF EXISTS ix_branch_master_code;

-- ============================================================
-- TABLE: card_delivery_records (96 kB saved)
-- Keep: ix_card_delivery_appt_id
-- Drop: ix_card_delivery_records_appointment_id (same: btree appointment_id)
-- ============================================================
DROP INDEX CONCURRENTLY IF EXISTS ix_card_delivery_records_appointment_id;

-- Keep: ix_card_delivery_records_branch_code
-- Drop: ix_card_delivery_branch (same: btree branch_code)
DROP INDEX CONCURRENTLY IF EXISTS ix_card_delivery_branch;

-- Keep: ix_card_delivery_serial
-- Drop: ix_card_delivery_records_serial_number (same: btree serial_number)
DROP INDEX CONCURRENTLY IF EXISTS ix_card_delivery_records_serial_number;

-- ============================================================
-- TABLE: cards (34 MB saved — biggest savings!)
-- ============================================================

-- 3-way duplicate on appointment_id:
-- Keep: ix_cards_appointment
-- Drop: ix_cards_appt + ix_cards_appointment_id
DROP INDEX CONCURRENTLY IF EXISTS ix_cards_appt;
DROP INDEX CONCURRENTLY IF EXISTS ix_cards_appointment_id;

-- 3-way duplicate on branch_code:
-- Keep: ix_cards_branch_code_only (partial: WHERE branch_code IS NOT NULL AND != '')
-- Drop: ix_cards_branch + ix_cards_branch_code (full indexes)
DROP INDEX CONCURRENTLY IF EXISTS ix_cards_branch;
DROP INDEX CONCURRENTLY IF EXISTS ix_cards_branch_code;

-- Duplicate on serial_number:
-- Keep: ix_cards_serial_number
-- Drop: ix_cards_serial (same: btree serial_number)
DROP INDEX CONCURRENTLY IF EXISTS ix_cards_serial;

-- ============================================================
-- TABLE: center_stats (16 kB saved)
-- Keep: ix_center_stats_branch_code
-- Drop: ix_center_stats_branch (same: btree branch_code)
-- ============================================================
DROP INDEX CONCURRENTLY IF EXISTS ix_center_stats_branch;

-- ============================================================
-- TABLE: complete_diffs (16 kB saved)
-- Keep: ix_complete_diffs_appointment_id
-- Drop: ix_complete_diffs_appt (same: btree appointment_id)
-- ============================================================
DROP INDEX CONCURRENTLY IF EXISTS ix_complete_diffs_appt;

-- ============================================================
-- TABLE: delivery_cards (40 kB saved)
-- Keep: ix_delivery_cards_serial_number
-- Drop: ix_delivery_cards_serial (same: btree serial_number)
-- ============================================================
DROP INDEX CONCURRENTLY IF EXISTS ix_delivery_cards_serial;

-- ============================================================
-- TABLE: qlogs (11 MB saved)
-- Keep: ix_qlogs_appointment_code
-- Drop: ix_qlogs_appt_code (same: btree appointment_code)
-- ============================================================
DROP INDEX CONCURRENTLY IF EXISTS ix_qlogs_appt_code;

-- ============================================================
-- TABLE: users (32 kB saved)
-- Keep: users_email_key (UNIQUE constraint)
-- Drop: ix_users_email (same: btree email)
-- ============================================================
DROP INDEX CONCURRENTLY IF EXISTS ix_users_email;

-- Keep: users_username_key (UNIQUE constraint)
-- Drop: ix_users_username (same: btree username)
DROP INDEX CONCURRENTLY IF EXISTS ix_users_username;

-- ============================================================
-- VERIFICATION: Check remaining indexes after cleanup
-- ============================================================
-- SELECT tablename, indexname
-- FROM pg_indexes
-- WHERE schemaname = 'public'
-- ORDER BY tablename, indexname;
