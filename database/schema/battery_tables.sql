-- Battery Database + Benchmark Analysis
-- Additive, idempotent schema. Does not modify shared measurement tables.

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
    lifecycle_status TEXT NOT NULL DEFAULT 'ACTIVE',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    is_deleted INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (battery_model_id) REFERENCES battery_model(battery_model_id)
);

CREATE TABLE IF NOT EXISTS battery_benchmark_result (
    result_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    instance_id TEXT,
    analysis_version TEXT NOT NULL,
    measurement_count INTEGER NOT NULL DEFAULT 0,
    start_voltage REAL,
    end_voltage REAL,
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

CREATE INDEX IF NOT EXISTS idx_battery_instance_model ON battery_instance(battery_model_id);
CREATE INDEX IF NOT EXISTS idx_benchmark_session ON battery_benchmark_result(session_id);
CREATE INDEX IF NOT EXISTS idx_benchmark_instance ON battery_benchmark_result(instance_id);

-- Derive analysis-critical voltage fields from the raw Measurement log.
-- COALESCE supports both independent CH1/CH2 session layouts: whichever voltage
-- column is populated for the session becomes the source of truth.
CREATE TRIGGER IF NOT EXISTS trg_battery_benchmark_derive_measurement_fields
AFTER INSERT ON battery_benchmark_result
FOR EACH ROW
BEGIN
    UPDATE battery_benchmark_result
       SET start_voltage = (
               SELECT COALESCE(voltage1, voltage2) FROM measurement
                WHERE session_id = NEW.session_id
                  AND COALESCE(voltage1, voltage2) IS NOT NULL
                ORDER BY elapsed_time ASC
                LIMIT 1
           ),
           end_voltage = (
               SELECT COALESCE(voltage1, voltage2) FROM measurement
                WHERE session_id = NEW.session_id
                  AND COALESCE(voltage1, voltage2) IS NOT NULL
                ORDER BY elapsed_time DESC
                LIMIT 1
           ),
           voltage_drop = (
               SELECT COALESCE(voltage1, voltage2) FROM measurement
                WHERE session_id = NEW.session_id
                  AND COALESCE(voltage1, voltage2) IS NOT NULL
                ORDER BY elapsed_time ASC
                LIMIT 1
           ) - (
               SELECT COALESCE(voltage1, voltage2) FROM measurement
                WHERE session_id = NEW.session_id
                  AND COALESCE(voltage1, voltage2) IS NOT NULL
                ORDER BY elapsed_time DESC
                LIMIT 1
           )
     WHERE result_id = NEW.result_id;
END;

-- Tamiya Neo Champ preset.
INSERT OR IGNORE INTO battery_model
    (model_code, name, chemistry, nominal_voltage, capacity_nominal_mah, manufacturer, data_confidence, notes)
VALUES
    ('NEO_CHAMP', 'Neo Champ', 'NiMH', 1.2, 950.0, 'Tamiya', 1.0,
     'Tamiya Neo Champ preset. Nominal voltage 1.2V; nominal capacity 950mAh.');
