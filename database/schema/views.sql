-- ============================================================
-- views.sql
-- Motor Database System
-- Revision 1
-- SQLite3
-- ============================================================

PRAGMA foreign_keys = ON;

-- ============================================================
-- View : vw_motor_instance
-- モーター一覧表示用
-- ============================================================

CREATE VIEW IF NOT EXISTS vw_motor_instance AS

SELECT

    mi.instance_id,

    mm.motor_model_id,

    mm.name AS motor_name,

    mm.series,

    mi.serial_number,

    mi.nickname,

    mi.status,

    mi.health_status,

    mi.purchase_date,

    mi.opened_date,

    mi.latest_session_id,

    mi.latest_work_id,

    mi.anomaly_count,

    mi.consecutive_anomaly_count,

    mi.created_at,

    mi.updated_at

FROM motor_instance mi

INNER JOIN motor_model mm

ON mi.motor_model_id = mm.motor_model_id

WHERE

    mi.is_deleted = 0

AND

    mm.is_deleted = 0;





-- ============================================================
-- View : vw_latest_session
-- 最新セッション一覧
-- ============================================================

CREATE VIEW IF NOT EXISTS vw_latest_session AS

SELECT

    ms.session_id,

    ms.instance_id,

    mm.name AS motor_name,

    mi.nickname,

    ms.device_type,

    ms.device_model,

    ms.start_datetime,

    ms.end_datetime,

    ms.result

FROM measurement_session ms

INNER JOIN motor_instance mi

ON ms.instance_id = mi.instance_id

INNER JOIN motor_model mm

ON mi.motor_model_id = mm.motor_model_id;





-- ============================================================
-- View : vw_breakin_summary
-- セッション別ログ件数
-- ============================================================

CREATE VIEW IF NOT EXISTS vw_breakin_summary AS

SELECT

    session_id,

    COUNT(*) AS log_count,

    MIN(elapsed_sec) AS first_sec,

    MAX(elapsed_sec) AS last_sec,

    MIN(timestamp) AS first_timestamp,

    MAX(timestamp) AS last_timestamp

FROM breakin_log

GROUP BY session_id;





-- ============================================================
-- View : vw_latest_log
-- 最新ログ表示
-- ============================================================

CREATE VIEW IF NOT EXISTS vw_latest_log AS

SELECT

    log_id,

    session_id,

    timestamp,

    elapsed_sec,

    voltage_v,

    current_ma,

    temperature_c,

    pwm,

    direction,

    measured_rpm,

    smartphone_rpm,

    quality_status,

    anomaly_type

FROM breakin_log

ORDER BY timestamp DESC;





-- ============================================================
-- END OF views.sql
-- ============================================================

