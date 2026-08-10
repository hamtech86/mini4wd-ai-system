-- ============================================================
-- MINI4WD AI SYSTEM
-- MOTOR MODEL MASTER
-- Nominal specification reference data
-- ============================================================
--
-- Source: project-provided nominal motor specification CSV
-- Purpose: reference/master data only.
-- Measured individual motor values must be stored separately.
--
-- Vehicle assumptions for derived weight guidance:
--   Tire diameter : 24 mm
--   Gear ratio    : 3.5:1
--
-- ============================================================

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS motor_model (
    motor_model_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    series TEXT NOT NULL,
    shaft_type TEXT NOT NULL,
    motor_category TEXT NOT NULL,
    nominal_rpm REAL,
    nominal_current_ma REAL,
    nominal_torque_gcm REAL,
    efficiency_index REAL,
    stability_tendency TEXT,
    heat_tendency TEXT,
    data_confidence TEXT,
    notes TEXT,
    is_deleted INTEGER NOT NULL DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

INSERT OR REPLACE INTO motor_model
(
    motor_model_id,
    name,
    series,
    shaft_type,
    motor_category,
    nominal_rpm,
    nominal_current_ma,
    nominal_torque_gcm,
    efficiency_index,
    stability_tendency,
    heat_tendency,
    data_confidence,
    notes,
    is_deleted,
    updated_at
)
VALUES
('MD_PRO','マッハダッシュPro','PRO','両軸','DASH',25500,1650,180,1.40,'LOW','HIGH','HIGH','高回転ピーキー最上位',0,CURRENT_TIMESTAMP),
('HD_PRO','ハイパーダッシュPro','PRO','両軸','DASH',24000,1600,190,1.30,'LOW','HIGH','HIGH','バランス高回転型',0,CURRENT_TIMESTAMP),
('LD_PRO','ライトダッシュPro','PRO','両軸','TUNED',18500,1200,165,1.15,'HIGH','MEDIUM','HIGH','安定高速型',0,CURRENT_TIMESTAMP),
('TT2_PRO','トルクチューン2Pro','PRO','両軸','TUNED',15000,1400,220,1.00,'HIGH','LOW','HIGH','トルク特化型',0,CURRENT_TIMESTAMP),
('AT2_PRO','アトミックチューン2Pro','PRO','両軸','TUNED',16000,1350,200,1.05,'HIGH','MEDIUM','HIGH','万能型',0,CURRENT_TIMESTAMP),
('RT2_PRO','レブチューン2Pro','PRO','両軸','TUNED',20000,1450,170,1.20,'MEDIUM','MEDIUM','HIGH','高回転安定型',0,CURRENT_TIMESTAMP),
('NOR_DBL','ノーマル両軸','STD','両軸','NORMAL',11000,900,140,1.00,'HIGH','LOW','HIGH','基準モーター両軸',0,CURRENT_TIMESTAMP),
('SPT','スプリントダッシュ','STD','片軸','DASH',26500,1700,175,1.35,'LOW','HIGH','HIGH','ピーキー高速型',0,CURRENT_TIMESTAMP),
('PD','パワーダッシュ','STD','片軸','DASH',23000,1750,230,1.10,'LOW','HIGH','HIGH','トルク特化型',0,CURRENT_TIMESTAMP),
('HD3','ハイパーダッシュ3','STD','片軸','DASH',23500,1650,200,1.20,'LOW','HIGH','MEDIUM','高負荷安定型',0,CURRENT_TIMESTAMP),
('LD','ライトダッシュ','STD','片軸','TUNED',17500,1150,160,1.05,'HIGH','MEDIUM','MEDIUM','安定型',0,CURRENT_TIMESTAMP),
('TT2','トルクチューン2','STD','片軸','TUNED',14500,1350,210,0.95,'HIGH','LOW','HIGH','定番トルク型',0,CURRENT_TIMESTAMP),
('AT2','アトミックチューン2','STD','片軸','TUNED',15500,1300,195,1.00,'HIGH','MEDIUM','HIGH','万能型',0,CURRENT_TIMESTAMP),
('RT2','レブチューン2','STD','片軸','TUNED',19000,1400,165,1.15,'MEDIUM','MEDIUM','HIGH','高回転型',0,CURRENT_TIMESTAMP),
('NOR_STD','ノーマル片軸','STD','片軸','NORMAL',10500,850,135,1.00,'HIGH','LOW','HIGH','基準モーター片軸',0,CURRENT_TIMESTAMP);

CREATE INDEX IF NOT EXISTS idx_motor_model_master_name
ON motor_model(name);

CREATE INDEX IF NOT EXISTS idx_motor_model_master_series
ON motor_model(series);

CREATE INDEX IF NOT EXISTS idx_motor_model_master_category
ON motor_model(motor_category);

-- ============================================================
-- END
-- ============================================================
