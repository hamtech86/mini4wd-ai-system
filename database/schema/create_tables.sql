-- ============================================================
-- create_tables.sql
-- Motor Database System
-- Revision 1
-- SQLite3
-- Part 1 / Final
-- ============================================================

PRAGMA foreign_keys = ON;


-- ============================================================
-- ① schema_info
-- Database schema management
-- ============================================================

CREATE TABLE IF NOT EXISTS schema_info (

    schema_version TEXT NOT NULL,

    created_at DATETIME NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at DATETIME NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    description TEXT

);


-- ============================================================
-- ② motor_model
-- Motor master data
-- ============================================================

CREATE TABLE IF NOT EXISTS motor_model (

    motor_model_id INTEGER PRIMARY KEY AUTOINCREMENT,

    name TEXT NOT NULL,

    series TEXT,

    shaft_type TEXT,

    motor_category TEXT,

    nominal_voltage REAL,

    nominal_rpm INTEGER,

    nominal_current_ma INTEGER,

    nominal_torque_gcm REAL,

    efficiency_index REAL,

    stability_tendency REAL,

    heat_tendency REAL,

    brush_life_index REAL,

    peak_position TEXT,

    rpm_gain_rate REAL,

    torque_loss_rate REAL,

    current_drop_rate REAL,

    data_confidence REAL,

    notes TEXT,


    created_at DATETIME NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at DATETIME NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    is_deleted INTEGER NOT NULL
        DEFAULT 0

);


-- ============================================================
-- ③ motor_instance
-- Individual motor management
-- ============================================================

CREATE TABLE IF NOT EXISTS motor_instance (

    instance_id INTEGER PRIMARY KEY AUTOINCREMENT,


    motor_model_id INTEGER NOT NULL,


    serial_number TEXT,

    nickname TEXT,


    purchase_date DATE,

    opened_date DATE,


    status TEXT,

    health_status TEXT,


    latest_session_id INTEGER,

    latest_work_id INTEGER,


    first_log_id INTEGER,

    peak_log_id INTEGER,

    latest_log_id INTEGER,


    backup_log1 INTEGER,

    backup_log2 INTEGER,

    backup_log3 INTEGER,


    anomaly_count INTEGER NOT NULL
        DEFAULT 0,

    consecutive_anomaly_count INTEGER NOT NULL
        DEFAULT 0,


    notes TEXT,


    created_at DATETIME NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    updated_at DATETIME NOT NULL
        DEFAULT CURRENT_TIMESTAMP,

    is_deleted INTEGER NOT NULL
        DEFAULT 0,


    FOREIGN KEY(
        motor_model_id
    )
    REFERENCES motor_model(
        motor_model_id
    )

);


-- ============================================================
-- ④ motor_work
-- Work operation history
-- ============================================================

CREATE TABLE IF NOT EXISTS motor_work (

    work_id INTEGER PRIMARY KEY AUTOINCREMENT,


    instance_id INTEGER NOT NULL,

    session_id INTEGER,


    work_type TEXT NOT NULL,


    start_datetime DATETIME,

    end_datetime DATETIME,


    duration_sec INTEGER,


    performed_by TEXT,


    memo TEXT,


    created_at DATETIME NOT NULL
        DEFAULT CURRENT_TIMESTAMP,


    FOREIGN KEY(
        instance_id
    )
    REFERENCES motor_instance(
        instance_id
    )

);


-- ============================================================
-- ⑤ measurement_session
-- Measurement session information
-- ============================================================

CREATE TABLE IF NOT EXISTS measurement_session (

    session_id INTEGER PRIMARY KEY AUTOINCREMENT,


    instance_id INTEGER NOT NULL,


    device_type TEXT NOT NULL,

    device_model TEXT,


    firmware_version TEXT,

    analysis_version TEXT,


    calibration_profile TEXT,


    start_datetime DATETIME,

    end_datetime DATETIME,


    operator TEXT,


    result TEXT,


    notes TEXT,


    created_at DATETIME NOT NULL
        DEFAULT CURRENT_TIMESTAMP,


    FOREIGN KEY(
        instance_id
    )
    REFERENCES motor_instance(
        instance_id
    )

);

-- ============================================================
-- create_tables.sql
-- Motor Database System
-- Revision 1
-- SQLite3
-- Part 2 / Final
-- ============================================================


-- ============================================================
-- ⑥ breakin_log
-- Actual measurement log
-- ============================================================

CREATE TABLE IF NOT EXISTS breakin_log (

    log_id INTEGER PRIMARY KEY AUTOINCREMENT,


    session_id INTEGER NOT NULL,


    timestamp DATETIME NOT NULL,


    elapsed_sec INTEGER NOT NULL,


    voltage_v REAL NOT NULL,


    current_ma INTEGER NOT NULL,


    temperature_c REAL,


    pwm INTEGER,


    direction TEXT,


    measured_rpm INTEGER,


    smartphone_rpm INTEGER,


    quality_status TEXT NOT NULL
        DEFAULT 'GOOD',


    anomaly_type TEXT NOT NULL
        DEFAULT 'NONE',


    memo TEXT,


    created_at DATETIME NOT NULL
        DEFAULT CURRENT_TIMESTAMP,


    FOREIGN KEY(
        session_id
    )
    REFERENCES measurement_session(
        session_id
    )

);



-- ============================================================
-- ⑦ work_history
-- External/manual work history
-- ============================================================

CREATE TABLE IF NOT EXISTS work_history (

    history_id INTEGER PRIMARY KEY AUTOINCREMENT,


    instance_id INTEGER NOT NULL,


    work_id INTEGER,


    datetime DATETIME NOT NULL,


    work_type TEXT NOT NULL,


    duration_sec INTEGER,


    performed_by TEXT,


    memo TEXT,


    created_at DATETIME NOT NULL
        DEFAULT CURRENT_TIMESTAMP,


    FOREIGN KEY(
        instance_id
    )
    REFERENCES motor_instance(
        instance_id
    ),


    FOREIGN KEY(
        work_id
    )
    REFERENCES motor_work(
        work_id
    )

);



-- ============================================================
-- ENUM CHECK CONSTRAINT UPDATE
-- ============================================================

-- SQLite does not support ALTER CHECK easily.
-- Validation is handled by application layer.
-- Values defined by specification:

-- motor_work.work_type
-- INITIAL_BREAKIN
-- BREAKIN
-- PEAK_CHECK
-- CLEANING
-- CONTACT_REVIVER
-- MAGNETIZATION
-- DISASSEMBLY
-- ASSEMBLY
-- REPAIR
-- OTHER


-- measurement_session.device_type
-- BREAKIN
-- EVALUATION
-- MANUAL
-- REFERENCE


-- measurement_session.result
-- COMPLETE
-- ERROR
-- TIMEOUT
-- CANCEL


-- breakin_log.quality_status
-- GOOD
-- WARNING
-- ERROR
-- INVALID


-- breakin_log.anomaly_type
-- NONE
-- RANDOM
-- DEVICE
-- OBJECT
-- UNKNOWN



-- ============================================================
-- Additional foreign key cache references
-- motor_instance cache columns
-- ============================================================

-- latest_session_id
-- latest_work_id
-- first_log_id
-- peak_log_id
-- latest_log_id
-- backup_log1
-- backup_log2
-- backup_log3

-- These columns intentionally do not use FOREIGN KEY.
-- Reason:
-- Log rotation and cache update require independent lifecycle.
-- Referential integrity is managed by DatabaseManager.



-- ============================================================
-- Initial schema record
-- ============================================================

INSERT INTO schema_info
(
    schema_version,
    description
)
VALUES
(
    'Rev.1',
    'Motor Database System Schema Revision 1'
);



-- ============================================================
-- END OF create_tables.sql Rev.1
-- ============================================================



