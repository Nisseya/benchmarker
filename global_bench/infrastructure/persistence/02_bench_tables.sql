-- Enable uuid generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ----------------------------
-- 1) Runs
-- ----------------------------
CREATE TABLE IF NOT EXISTS bench_runs (
  run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  model_id TEXT NOT NULL,
  revision TEXT NOT NULL,

  db_id TEXT NOT NULL,
  params JSONB NOT NULL DEFAULT '{}'::jsonb,

  status TEXT NOT NULL DEFAULT 'running',

  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  ended_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS bench_runs_model_idx ON bench_runs (model_id);
CREATE INDEX IF NOT EXISTS bench_runs_dbid_idx ON bench_runs (db_id);
CREATE INDEX IF NOT EXISTS bench_runs_started_at_idx ON bench_runs (started_at DESC);


-- ----------------------------
-- 2) Raw SSE events (audit log)
-- ----------------------------
CREATE TABLE IF NOT EXISTS bench_events (
  id BIGSERIAL PRIMARY KEY,

  run_id UUID NOT NULL REFERENCES bench_runs(run_id) ON DELETE CASCADE,
  ts TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  event_type TEXT NOT NULL,       -- meta/status/result/done/error/...
  payload JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS bench_events_run_id_idx ON bench_events (run_id);
CREATE INDEX IF NOT EXISTS bench_events_type_idx ON bench_events (event_type);
CREATE INDEX IF NOT EXISTS bench_events_ts_idx ON bench_events (ts DESC);


-- ----------------------------
-- 3) Results per question (enriched)
-- ----------------------------
CREATE TABLE IF NOT EXISTS bench_items (
  id BIGSERIAL PRIMARY KEY,

  run_id UUID NOT NULL REFERENCES bench_runs(run_id) ON DELETE CASCADE,
  idx INTEGER NOT NULL,

  question_id TEXT NOT NULL,
  db_id TEXT NOT NULL,
  source_index INTEGER,

  raw_answer TEXT,
  sql TEXT,
  gold_sql TEXT,

  gen_time_ms DOUBLE PRECISION,
  metrics JSONB NOT NULL DEFAULT '{}'::jsonb,

  -- scoring
  pred_exec_success BOOLEAN,
  gold_exec_success BOOLEAN,
  is_correct BOOLEAN,

  pred_error TEXT,
  gold_error TEXT,

  rows_pred INTEGER,
  rows_gold INTEGER,

  match_kind TEXT,

  -- perf enrich (optional fields you can fill later)
  pred_exec_time_ms DOUBLE PRECISION,
  gold_exec_time_ms DOUBLE PRECISION,
  scoring_time_ms DOUBLE PRECISION
);

-- Avoid duplicates if retrying inserts
CREATE UNIQUE INDEX IF NOT EXISTS bench_items_unique_per_run
ON bench_items (run_id, idx);

CREATE INDEX IF NOT EXISTS bench_items_run_id_idx ON bench_items (run_id);
CREATE INDEX IF NOT EXISTS bench_items_question_id_idx ON bench_items (question_id);
CREATE INDEX IF NOT EXISTS bench_items_is_correct_idx ON bench_items (is_correct);
CREATE INDEX IF NOT EXISTS bench_items_dbid_idx ON bench_items (db_id);
