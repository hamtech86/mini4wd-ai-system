-- =====================================================
-- MINI4WD AI SYSTEM
-- MOTOR_BREAKIN_V3
-- Database Schema
-- Phase1
-- =====================================================

PRAGMA foreign_keys = ON;

-- =====================================================
-- Measurement Session
-- =====================================================

CREATE TABLE IF NOT EXISTS measurement_session (

    session_id TEXT PRIMARY KEY,

    measurement_type TEXT NOT NULL,

    status TEXT NOT NULL,

    start_time TEXT,

    end_time TEXT,

    measurement_count INTEGER DEFAULT 0,

    operator TEXT,

    notes TEXT,

    schema_version TEXT,

    firmware_version TEXT
);

-- =====================================================
-- Measurement
-- =====================================================

CREATE TABLE IF NOT EXISTS measurement (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    session_id TEXT NOT NULL,

    record_type TEXT,

    device_model TEXT,

    instance_id TEXT,

    elapsed_time REAL,

    raw_acs1 INTEGER,
    raw_acs2 INTEGER,

    current1 REAL,
    current2 REAL,

    voltage1 REAL,
    voltage2 REAL,

    motor_voltage REAL,

    pwm INTEGER,

    direction TEXT,

    state TEXT,

    current_avg REAL,

    power REAL,

    current_ripple REAL,

    voltage_ripple REAL,

    peak_power REAL,

    peak_current REAL,

    peak_voltage REAL,

    peak_pwm INTEGER,

    brush_peak_current REAL,

    raw_magnetic INTEGER,

    magnetic_level REAL,

    motor_temperature REAL,

    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY(session_id)
        REFERENCES measurement_session(session_id)
);

