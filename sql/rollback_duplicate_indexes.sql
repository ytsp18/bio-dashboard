-- ============================================================
-- ROLLBACK: Recreate Dropped Duplicate Indexes
-- Project: bio-dashboard-fts (pdiucwdwgxweqyaeayhb)
-- Date: 2026-02-11
--
-- Use this script to restore indexes if issues arise after
-- dropping duplicates with drop_duplicate_indexes.sql
--
-- IMPORTANT: Run each statement ONE AT A TIME
-- (CREATE INDEX CONCURRENTLY cannot run inside a transaction block)
-- ============================================================

-- bio_records
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_bio_records_serial_number
  ON public.bio_records USING btree (serial_number);

-- branch_master
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_branch_master_code
  ON public.branch_master USING btree (branch_code);

-- card_delivery_records
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_card_delivery_records_appointment_id
  ON public.card_delivery_records USING btree (appointment_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_card_delivery_branch
  ON public.card_delivery_records USING btree (branch_code);

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_card_delivery_records_serial_number
  ON public.card_delivery_records USING btree (serial_number);

-- cards
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_cards_appt
  ON public.cards USING btree (appointment_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_cards_appointment_id
  ON public.cards USING btree (appointment_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_cards_branch
  ON public.cards USING btree (branch_code);

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_cards_branch_code
  ON public.cards USING btree (branch_code);

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_cards_serial
  ON public.cards USING btree (serial_number);

-- center_stats
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_center_stats_branch
  ON public.center_stats USING btree (branch_code);

-- complete_diffs
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_complete_diffs_appt
  ON public.complete_diffs USING btree (appointment_id);

-- delivery_cards
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_delivery_cards_serial
  ON public.delivery_cards USING btree (serial_number);

-- qlogs
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_qlogs_appt_code
  ON public.qlogs USING btree (appointment_code);

-- users
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_users_email
  ON public.users USING btree (email);

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_users_username
  ON public.users USING btree (username);
