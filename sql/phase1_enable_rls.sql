-- ============================================================
-- Phase 1: Enable RLS + Authenticated-Only Access
-- Bio Dashboard (bio-dashboard-fts)
-- Project ID: pdiucwdwgxweqyaeayhb
-- Date: 2026-02-11
--
-- What this does:
--   1. Enables RLS on all 22 public tables
--   2. Creates policy: only authenticated users get full access
--   3. Blocks anon key from reading/writing any data
--
-- Impact: Zero impact on Streamlit app (uses direct DB connection)
-- Rollback: ALTER TABLE public.<table> DISABLE ROW LEVEL SECURITY;
-- ============================================================

BEGIN;

-- ============================================================
-- 1. REPORT DATA TABLES (8 tables)
-- ============================================================

-- reports
ALTER TABLE public.reports ENABLE ROW LEVEL SECURITY;
CREATE POLICY "authenticated_full_access" ON public.reports
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- cards
ALTER TABLE public.cards ENABLE ROW LEVEL SECURITY;
CREATE POLICY "authenticated_full_access" ON public.cards
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- bad_cards
ALTER TABLE public.bad_cards ENABLE ROW LEVEL SECURITY;
CREATE POLICY "authenticated_full_access" ON public.bad_cards
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- center_stats
ALTER TABLE public.center_stats ENABLE ROW LEVEL SECURITY;
CREATE POLICY "authenticated_full_access" ON public.center_stats
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- anomaly_sla
ALTER TABLE public.anomaly_sla ENABLE ROW LEVEL SECURITY;
CREATE POLICY "authenticated_full_access" ON public.anomaly_sla
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- wrong_centers
ALTER TABLE public.wrong_centers ENABLE ROW LEVEL SECURITY;
CREATE POLICY "authenticated_full_access" ON public.wrong_centers
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- complete_diffs
ALTER TABLE public.complete_diffs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "authenticated_full_access" ON public.complete_diffs
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- delivery_cards
ALTER TABLE public.delivery_cards ENABLE ROW LEVEL SECURITY;
CREATE POLICY "authenticated_full_access" ON public.delivery_cards
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- ============================================================
-- 2. RAW UPLOAD TABLES (8 tables)
-- ============================================================

-- appointment_uploads
ALTER TABLE public.appointment_uploads ENABLE ROW LEVEL SECURITY;
CREATE POLICY "authenticated_full_access" ON public.appointment_uploads
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- appointments
ALTER TABLE public.appointments ENABLE ROW LEVEL SECURITY;
CREATE POLICY "authenticated_full_access" ON public.appointments
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- qlog_uploads
ALTER TABLE public.qlog_uploads ENABLE ROW LEVEL SECURITY;
CREATE POLICY "authenticated_full_access" ON public.qlog_uploads
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- qlogs
ALTER TABLE public.qlogs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "authenticated_full_access" ON public.qlogs
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- bio_uploads
ALTER TABLE public.bio_uploads ENABLE ROW LEVEL SECURITY;
CREATE POLICY "authenticated_full_access" ON public.bio_uploads
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- bio_records
ALTER TABLE public.bio_records ENABLE ROW LEVEL SECURITY;
CREATE POLICY "authenticated_full_access" ON public.bio_records
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- card_delivery_uploads
ALTER TABLE public.card_delivery_uploads ENABLE ROW LEVEL SECURITY;
CREATE POLICY "authenticated_full_access" ON public.card_delivery_uploads
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- card_delivery_records
ALTER TABLE public.card_delivery_records ENABLE ROW LEVEL SECURITY;
CREATE POLICY "authenticated_full_access" ON public.card_delivery_records
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- ============================================================
-- 3. USER MANAGEMENT TABLES (4 tables)
-- ============================================================

-- users
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
CREATE POLICY "authenticated_full_access" ON public.users
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- pending_registrations
ALTER TABLE public.pending_registrations ENABLE ROW LEVEL SECURITY;
CREATE POLICY "authenticated_full_access" ON public.pending_registrations
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- login_attempts
ALTER TABLE public.login_attempts ENABLE ROW LEVEL SECURITY;
CREATE POLICY "authenticated_full_access" ON public.login_attempts
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- audit_logs
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "authenticated_full_access" ON public.audit_logs
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- ============================================================
-- 4. SYSTEM TABLES (2 tables)
-- ============================================================

-- system_settings
ALTER TABLE public.system_settings ENABLE ROW LEVEL SECURITY;
CREATE POLICY "authenticated_full_access" ON public.system_settings
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

-- branch_master
ALTER TABLE public.branch_master ENABLE ROW LEVEL SECURITY;
CREATE POLICY "authenticated_full_access" ON public.branch_master
  FOR ALL TO authenticated USING (true) WITH CHECK (true);

COMMIT;

-- ============================================================
-- VERIFICATION: Run after applying to confirm RLS is enabled
-- ============================================================
-- SELECT tablename, rowsecurity
-- FROM pg_tables
-- WHERE schemaname = 'public'
-- ORDER BY tablename;
--
-- Expected: all 22 tables show rowsecurity = true
-- ============================================================
