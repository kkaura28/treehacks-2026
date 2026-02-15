-- ============================================================
-- Runtime tables for post-op compliance analysis pipeline
-- Run AFTER supabase_setup.sql + procedure seed files
-- ============================================================

-- 1. Procedure Runs — one row per surgery performed
-- ============================================================

CREATE TABLE procedure_runs (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  procedure_id  TEXT NOT NULL REFERENCES procedures(id),
  surgeon_name  TEXT,
  patient_id    TEXT,
  started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  ended_at      TIMESTAMPTZ,
  status        TEXT NOT NULL DEFAULT 'in_progress'
                CHECK (status IN ('in_progress', 'completed', 'cancelled')),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_runs_procedure ON procedure_runs(procedure_id);
CREATE INDEX idx_runs_status    ON procedure_runs(status);


-- 2. Observed Events — one row per detected surgical action
-- ============================================================

CREATE TABLE observed_events (
  id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  procedure_run_id  UUID NOT NULL REFERENCES procedure_runs(id) ON DELETE CASCADE,
  node_id           TEXT NOT NULL,
  timestamp         TIMESTAMPTZ NOT NULL,
  confidence        REAL NOT NULL DEFAULT 1.0 CHECK (confidence >= 0 AND confidence <= 1),
  source            TEXT NOT NULL DEFAULT 'mock' CHECK (source IN ('mock', 'cv_model', 'manual')),
  metadata          JSONB DEFAULT '{}',
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_events_run      ON observed_events(procedure_run_id);
CREATE INDEX idx_events_node     ON observed_events(procedure_run_id, node_id);
CREATE INDEX idx_events_time     ON observed_events(procedure_run_id, timestamp);


-- 3. Deviation Reports — one row per completed analysis
-- ============================================================

CREATE TABLE deviation_reports (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  procedure_run_id  UUID NOT NULL REFERENCES procedure_runs(id) ON DELETE CASCADE,
  compliance_score  REAL NOT NULL CHECK (compliance_score >= 0 AND compliance_score <= 1),
  total_expected    INT NOT NULL,
  total_observed    INT NOT NULL,
  confirmed_count   INT NOT NULL DEFAULT 0,
  mitigated_count   INT NOT NULL DEFAULT 0,
  review_count      INT NOT NULL DEFAULT 0,
  raw_deviations    JSONB NOT NULL DEFAULT '[]',
  adjudicated       JSONB NOT NULL DEFAULT '[]',
  report_text       TEXT,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (procedure_run_id)
);

CREATE INDEX idx_reports_run ON deviation_reports(procedure_run_id);


-- 4. RLS
-- ============================================================

ALTER TABLE procedure_runs   ENABLE ROW LEVEL SECURITY;
ALTER TABLE observed_events  ENABLE ROW LEVEL SECURITY;
ALTER TABLE deviation_reports ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public read runs"    ON procedure_runs    FOR SELECT USING (true);
CREATE POLICY "Public read events"  ON observed_events   FOR SELECT USING (true);
CREATE POLICY "Public read reports" ON deviation_reports  FOR SELECT USING (true);

-- Allow inserts from service role (backend)
CREATE POLICY "Service insert runs"    ON procedure_runs    FOR INSERT WITH CHECK (true);
CREATE POLICY "Service insert events"  ON observed_events   FOR INSERT WITH CHECK (true);
CREATE POLICY "Service insert reports" ON deviation_reports  FOR INSERT WITH CHECK (true);
CREATE POLICY "Service update runs"    ON procedure_runs    FOR UPDATE USING (true);
CREATE POLICY "Service update reports" ON deviation_reports  FOR UPDATE USING (true);

