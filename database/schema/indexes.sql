-- ============================================================
-- indexes.sql
-- Motor Database System
-- Revision 1
-- SQLite3
-- ============================================================


PRAGMA foreign_keys = ON;


-- ============================================================
-- motor_model indexes
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_motor_model_name
ON motor_model(
    name
);


CREATE INDEX IF NOT EXISTS idx_motor_model_series
ON motor_model(
    series
);


CREATE INDEX IF NOT EXISTS idx_motor_model_category
ON motor_model(
    motor_category
);


CREATE INDEX IF NOT EXISTS idx_motor_model_created_at
ON motor_model(
    created_at
);



-- ============================================================
-- motor_instance indexes
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_motor_instance_model_id
ON motor_instance(
    motor_model_id
);


CREATE INDEX IF NOT EXISTS idx_motor_instance_serial_number
ON motor_instance(
    serial_number
);


CREATE INDEX IF NOT EXISTS idx_motor_instance_status
ON motor_instance(
    status
);


CREATE INDEX IF NOT EXISTS idx_motor_instance_health_status
ON motor_instance(
    health_status
);


CREATE INDEX IF NOT EXISTS idx_motor_instance_created_at
ON motor_instance(
    created_at
);



-- ============================================================
-- motor_work indexes
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_motor_work_instance_id
ON motor_work(
    instance_id
);


CREATE INDEX IF NOT EXISTS idx_motor_work_session_id
ON motor_work(
    session_id
);


CREATE INDEX IF NOT EXISTS idx_motor_work_type
ON motor_work(
    work_type
);


CREATE INDEX IF NOT EXISTS idx_motor_work_start_datetime
ON motor_work(
    start_datetime
);



-- ============================================================
-- measurement_session indexes
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_measurement_session_instance_id
ON measurement_session(
    instance_id
);


CREATE INDEX IF NOT EXISTS idx_measurement_session_device_type
ON measurement_session(
    device_type
);


CREATE INDEX IF NOT EXISTS idx_measurement_session_start_datetime
ON measurement_session(
    start_datetime
);


CREATE INDEX IF NOT EXISTS idx_measurement_session_result
ON measurement_session(
    result
);



-- ============================================================
-- breakin_log indexes
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_breakin_log_session_id
ON breakin_log(
    session_id
);


CREATE INDEX IF NOT EXISTS idx_breakin_log_timestamp
ON breakin_log(
    timestamp
);


CREATE INDEX IF NOT EXISTS idx_breakin_log_quality_status
ON breakin_log(
    quality_status
);


CREATE INDEX IF NOT EXISTS idx_breakin_log_anomaly_type
ON breakin_log(
    anomaly_type
);



-- ============================================================
-- work_history indexes
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_work_history_instance_id
ON work_history(
    instance_id
);


CREATE INDEX IF NOT EXISTS idx_work_history_work_id
ON work_history(
    work_id
);


CREATE INDEX IF NOT EXISTS idx_work_history_datetime
ON work_history(
    datetime
);


CREATE INDEX IF NOT EXISTS idx_work_history_work_type
ON work_history(
    work_type
);



-- ============================================================
-- Common search indexes
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_motor_instance_active
ON motor_instance(
    is_deleted
);


CREATE INDEX IF NOT EXISTS idx_motor_model_active
ON motor_model(
    is_deleted
);



-- ============================================================
-- END OF indexes.sql Rev.1
-- ============================================================



