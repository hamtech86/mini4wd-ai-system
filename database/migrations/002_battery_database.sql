-- ============================================================
-- Battery Database + Benchmark Analysis
-- Migration 002
--
-- Battery 5A Standalone remains the measurement anchor.
-- No Arduino/firmware changes are required by this migration.
-- ============================================================

PRAGMA foreign_keys = ON;

-- Reuse the common measurement_session table.  SQLite has no
-- ADD COLUMN IF NOT EXISTS, so the application repository performs
-- the idempotent column check before applying these additions.
--
-- Intended columns:
--   battery_instance_id TEXT
--   device_model TEXT
--   analysis_version TEXT

CREATE TABLE IF NOT EXISTS battery_model (
    battery_model_id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    chemistry TEXT,
    nominal_voltage REAL,
    capacity_nominal_mah REAL,
    manufacturer TEXT,
    data_confidence REAL,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    is_deleted INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS battery_instance (
    instance_id TEXT PRIMARY KEY,
    battery_model_id INTEGER NOT NULL,
    serial_number TEXT,
    nickname TEXT,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    is_deleted INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (battery_model_id) REFERENCES battery_model(battery_model_id)
);

-- Analysis results are derived data.  Raw measurement rows are never
-- overwritten by this table.
CREATE TABLE IF NOT EXISTS battery_benchmark_result (
    result_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    instance_id TEXT,
    analysis_version TEXT NOT NULL,
    measurement_count INTEGER NOT NULL DEFAULT 0,
    avg_voltage REAL,
    avg_current REAL,
    avg_power REAL,
    max_current REAL,
    max_power REAL,
    discharge_time_s REAL,
    voltage_drop REAL,
    capacity_ah REAL,
    capacity_mah REAL,
    energy_wh REAL,
    voltage_stddev REAL,
    current_stddev REAL,
    power_stddev REAL,
    voltage_hold_score REAL,
    stability_score REAL,
    capacity_score REAL,
    power_score REAL,
    overall_score REAL,
    internal_resistance_mohm REAL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id, analysis_version),
    FOREIGN KEY (session_id) REFERENCES measurement_session(session_id),
    FOREIGN KEY (instance_id) REFERENCES battery_instance(instance_id)
);

CREATE INDEX IF NOT EXISTS idx_battery_instance_model
    ON battery_instance(battery_model_id);
CREATE INDEX IF NOT EXISTS idx_battery_result_session
    ON battery_benchmark_result(session_id);
CREATE INDEX IF NOT EXISTS idx_battery_result_instance
    ON battery_benchmark_result(instance_id);

-- Canonical reference models.  These are intentionally descriptive
-- only; no performance score is inferred from these entries.
INSERT OR IGNORE INTO battery_model
    (model_code, name, chemistry, nominal_voltage, data_confidence, notes)
VALUES
    ('NEO_STD', 'Tamiya Neo Champ', 'NiMH', 1.2, 0.5, 'Reference model; measured data takes precedence.'),
    ('NEO_GROWN', 'Tamiya Neo Champ (grown)', 'NiMH', 1.2, 0.5, 'Reference model; measured data takes precedence.'),
    ('POWER_GOLD', 'POWER GOLD', 'NiMH', 1.2, 0.5, 'Reference model; measured data takes precedence.');

-- ============================================================
-- END
-- ============================================================
