-- =============================================================================
-- ROLLBACK: 2026-03-10 FK Indexes + Unused Index Cleanup
-- =============================================================================
-- Run this to undo changes from 20260310_fk_indexes_and_cleanup.sql
-- =============================================================================

-- ======================== Undo Part 1: Drop FK Indexes ========================
DROP INDEX IF EXISTS ix_anomaly_sla_report_id;
DROP INDEX IF EXISTS ix_bad_cards_report_id;
DROP INDEX IF EXISTS ix_cards_report_id;
DROP INDEX IF EXISTS ix_center_stats_report_id;
DROP INDEX IF EXISTS ix_complete_diffs_report_id;
DROP INDEX IF EXISTS ix_delivery_cards_report_id;
DROP INDEX IF EXISTS ix_wrong_centers_report_id;
DROP INDEX IF EXISTS ix_appointments_upload_id;
DROP INDEX IF EXISTS ix_bio_records_upload_id;
DROP INDEX IF EXISTS ix_card_delivery_records_upload_id;
DROP INDEX IF EXISTS ix_qlogs_upload_id;

-- ======================== Undo Part 2: Recreate Dropped Indexes ========================
CREATE INDEX IF NOT EXISTS ix_cards_date_status_wpno ON cards (print_date, print_status, work_permit_no);
CREATE INDEX IF NOT EXISTS ix_complete_diffs_appointment_id ON complete_diffs (appointment_id);
CREATE INDEX IF NOT EXISTS ix_complete_diffs_serial_number ON complete_diffs (serial_number);
CREATE INDEX IF NOT EXISTS ix_center_stats_branch_code ON center_stats (branch_code);
CREATE INDEX IF NOT EXISTS ix_delivery_cards_serial_number ON delivery_cards (serial_number);
CREATE INDEX IF NOT EXISTS ix_delivery_cards_appointment_id ON delivery_cards (appointment_id);
CREATE INDEX IF NOT EXISTS ix_card_delivery_appt_id ON card_delivery_records (appointment_id);
CREATE INDEX IF NOT EXISTS ix_card_delivery_records_send_date ON card_delivery_records (send_date);
CREATE INDEX IF NOT EXISTS ix_card_delivery_records_alien_card_id ON card_delivery_records (alien_card_id);

-- ======================== ANALYZE ========================
ANALYZE cards;
ANALYZE complete_diffs;
ANALYZE center_stats;
ANALYZE delivery_cards;
ANALYZE card_delivery_records;
