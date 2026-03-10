-- =============================================================================
-- 2026-03-10: FK Indexes + Unused Index Cleanup
-- =============================================================================
-- Part 1: Add indexes on foreign key columns (11 tables)
-- Part 2: Drop verified unused indexes (10 indexes)
-- Rollback: sql/20260310_rollback_fk_indexes_and_cleanup.sql
-- =============================================================================

-- ======================== PART 1: FK Indexes ========================
-- These FK columns are used in DELETE operations (data_service.py, Upload.py)
-- Without index → sequential scan on DELETE → timeout risk (see v2.3.7)

-- report_id FK indexes (7 child tables of reports)
CREATE INDEX IF NOT EXISTS ix_anomaly_sla_report_id ON anomaly_sla (report_id);
CREATE INDEX IF NOT EXISTS ix_bad_cards_report_id ON bad_cards (report_id);
CREATE INDEX IF NOT EXISTS ix_cards_report_id ON cards (report_id);
CREATE INDEX IF NOT EXISTS ix_center_stats_report_id ON center_stats (report_id);
CREATE INDEX IF NOT EXISTS ix_complete_diffs_report_id ON complete_diffs (report_id);
CREATE INDEX IF NOT EXISTS ix_delivery_cards_report_id ON delivery_cards (report_id);
CREATE INDEX IF NOT EXISTS ix_wrong_centers_report_id ON wrong_centers (report_id);

-- upload_id FK indexes (4 raw data tables)
CREATE INDEX IF NOT EXISTS ix_appointments_upload_id ON appointments (upload_id);
CREATE INDEX IF NOT EXISTS ix_bio_records_upload_id ON bio_records (upload_id);
CREATE INDEX IF NOT EXISTS ix_card_delivery_records_upload_id ON card_delivery_records (upload_id);
CREATE INDEX IF NOT EXISTS ix_qlogs_upload_id ON qlogs (upload_id);

-- ======================== PART 2: Drop Unused Indexes ========================
-- Verified: no code queries these columns in WHERE clause
-- Analysis date: 2026-03-10

-- cards: work_permit_no never filtered in WHERE (21 MB)
DROP INDEX IF EXISTS ix_cards_date_status_wpno;

-- complete_diffs: ILIKE search doesn't use btree index (16 kB each)
DROP INDEX IF EXISTS ix_complete_diffs_appointment_id;
DROP INDEX IF EXISTS ix_complete_diffs_serial_number;

-- center_stats: loaded by report_id, filtered in Python (16 kB)
DROP INDEX IF EXISTS ix_center_stats_branch_code;

-- delivery_cards: serial filtered after report_id (48 kB), appt not queried (40 kB)
DROP INDEX IF EXISTS ix_delivery_cards_serial_number;
DROP INDEX IF EXISTS ix_delivery_cards_appointment_id;

-- card_delivery_records: none of these columns are filtered in code
DROP INDEX IF EXISTS ix_card_delivery_appt_id;            -- 40 kB
DROP INDEX IF EXISTS ix_card_delivery_records_send_date;   -- 16 kB
DROP INDEX IF EXISTS ix_card_delivery_records_alien_card_id; -- 16 kB

-- ======================== ANALYZE ========================
ANALYZE anomaly_sla;
ANALYZE bad_cards;
ANALYZE cards;
ANALYZE center_stats;
ANALYZE complete_diffs;
ANALYZE delivery_cards;
ANALYZE wrong_centers;
ANALYZE appointments;
ANALYZE bio_records;
ANALYZE card_delivery_records;
ANALYZE qlogs;
