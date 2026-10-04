-- ============================================================
-- Benchmark identification separation
-- Migration 003
--
-- Separates benchmark procedure type from voltage-control mode.
-- Existing rows are intentionally NOT reclassified or backfilled.
-- RawLog bodies are never modified by this migration.
-- ============================================================

PRAGMA foreign_keys = ON;

-- Canonical benchmark type for new/explicitly identified sessions.
-- NULL means the historical row has not been classified under the
-- new scheme; this is intentional.
ALTER TABLE measurement_session
    ADD COLUMN benchmark_type_code TEXT;

-- Canonical voltage control mode for new/explicitly identified sessions.
-- TERMINAL = legacy terminal-voltage-fixed acquisition.
-- INPUT    = new input-side-voltage-fixed acquisition.
-- NULL means the historical row has not been classified under the
-- new scheme; this is intentional.
ALTER TABLE measurement_session
    ADD COLUMN voltage_control_mode TEXT;

CREATE INDEX IF NOT EXISTS idx_measurement_session_benchmark_type_code
    ON measurement_session(benchmark_type_code);

CREATE INDEX IF NOT EXISTS idx_measurement_session_voltage_control_mode
    ON measurement_session(voltage_control_mode);

-- No UPDATE statements are intentional here.
-- Existing benchmark_type / notes / RawLog metadata remain untouched.
