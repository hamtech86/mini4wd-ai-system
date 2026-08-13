-- ============================================================
-- motor_model_master_rev2.sql
-- MINI4WD AI SYSTEM
-- Confirmed Motor Model Master: 15 models
-- ============================================================
--
-- Existing DB compatibility:
--   motor_model_id is INTEGER PRIMARY KEY AUTOINCREMENT.
--   Existing IDs 1-5 are preserved so Motor Instance foreign keys
--   and historical records remain valid.
--
-- The confirmed string IDs (TT2, AT2, ... MD_PRO) are mapped to
-- the existing integer DB keys through the motor_model rows.
-- No schema conversion is performed by this migration.
--
PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

-- Preserve existing integer IDs 1-5 and update their master data.
UPDATE motor_model SET
    name='トルクチューン2', series='STD', shaft_type='片軸', motor_category='TUNED',
    nominal_voltage=2.4, nominal_rpm=14500, nominal_current_ma=1350,
    nominal_torque_gcm=210, efficiency_index=0.95,
    stability_tendency='HIGH', heat_tendency='LOW', brush_life_index=NULL,
    data_confidence='HIGH', notes='定番トルク型', is_deleted=0
WHERE motor_model_id=1;

UPDATE motor_model SET
    name='アトミックチューン2', series='STD', shaft_type='片軸', motor_category='TUNED',
    nominal_voltage=2.4, nominal_rpm=15500, nominal_current_ma=1300,
    nominal_torque_gcm=195, efficiency_index=1.00,
    stability_tendency='HIGH', heat_tendency='MEDIUM', brush_life_index=NULL,
    data_confidence='HIGH', notes='万能型', is_deleted=0
WHERE motor_model_id=2;

UPDATE motor_model SET
    name='レブチューン2', series='STD', shaft_type='片軸', motor_category='TUNED',
    nominal_voltage=2.4, nominal_rpm=19000, nominal_current_ma=1400,
    nominal_torque_gcm=165, efficiency_index=1.15,
    stability_tendency='MEDIUM', heat_tendency='MEDIUM', brush_life_index=NULL,
    data_confidence='HIGH', notes='高回転型', is_deleted=0
WHERE motor_model_id=3;

UPDATE motor_model SET
    name='ハイパーダッシュ3', series='STD', shaft_type='片軸', motor_category='DASH',
    nominal_voltage=2.4, nominal_rpm=23500, nominal_current_ma=1650,
    nominal_torque_gcm=200, efficiency_index=1.20,
    stability_tendency='LOW', heat_tendency='HIGH', brush_life_index=NULL,
    data_confidence='MEDIUM', notes='高負荷安定型', is_deleted=0
WHERE motor_model_id=4;

-- Legacy Power Dash 2 is not part of the confirmed 15-model list.
-- Keep it for referential integrity, but hide it from active selection.
UPDATE motor_model
SET is_deleted=1
WHERE motor_model_id=5;

-- New models use the existing integer AUTOINCREMENT key.
-- The confirmed string model IDs are represented in this migration
-- by the documented name/code mapping below; no text is inserted into
-- the INTEGER primary key.
INSERT INTO motor_model
(name,series,shaft_type,motor_category,nominal_voltage,nominal_rpm,nominal_current_ma,nominal_torque_gcm,efficiency_index,stability_tendency,heat_tendency,brush_life_index,data_confidence,notes,is_deleted)
SELECT 'マッハダッシュPro','PRO','両軸','DASH',2.4,25500,1650,180,1.40,'LOW','HIGH',NULL,'HIGH','高回転ピーキー最上位',0
WHERE NOT EXISTS (SELECT 1 FROM motor_model WHERE name='マッハダッシュPro' AND is_deleted=0);

INSERT INTO motor_model
(name,series,shaft_type,motor_category,nominal_voltage,nominal_rpm,nominal_current_ma,nominal_torque_gcm,efficiency_index,stability_tendency,heat_tendency,brush_life_index,data_confidence,notes,is_deleted)
SELECT 'ハイパーダッシュPro','PRO','両軸','DASH',2.4,24000,1600,190,1.30,'LOW','HIGH',NULL,'HIGH','バランス高回転型',0
WHERE NOT EXISTS (SELECT 1 FROM motor_model WHERE name='ハイパーダッシュPro' AND is_deleted=0);

INSERT INTO motor_model
(name,series,shaft_type,motor_category,nominal_voltage,nominal_rpm,nominal_current_ma,nominal_torque_gcm,efficiency_index,stability_tendency,heat_tendency,brush_life_index,data_confidence,notes,is_deleted)
SELECT 'ライトダッシュPro','PRO','両軸','TUNED',2.4,18500,1200,165,1.15,'HIGH','MEDIUM',NULL,'HIGH','安定高速型',0
WHERE NOT EXISTS (SELECT 1 FROM motor_model WHERE name='ライトダッシュPro' AND is_deleted=0);

INSERT INTO motor_model
(name,series,shaft_type,motor_category,nominal_voltage,nominal_rpm,nominal_current_ma,nominal_torque_gcm,efficiency_index,stability_tendency,heat_tendency,brush_life_index,data_confidence,notes,is_deleted)
SELECT 'トルクチューン2Pro','PRO','両軸','TUNED',2.4,15000,1400,220,1.00,'HIGH','LOW',NULL,'HIGH','トルク特化型',0
WHERE NOT EXISTS (SELECT 1 FROM motor_model WHERE name='トルクチューン2Pro' AND is_deleted=0);

INSERT INTO motor_model
(name,series,shaft_type,motor_category,nominal_voltage,nominal_rpm,nominal_current_ma,nominal_torque_gcm,efficiency_index,stability_tendency,heat_tendency,brush_life_index,data_confidence,notes,is_deleted)
SELECT 'アトミックチューン2Pro','PRO','両軸','TUNED',2.4,16000,1350,200,1.05,'HIGH','MEDIUM',NULL,'HIGH','万能型',0
WHERE NOT EXISTS (SELECT 1 FROM motor_model WHERE name='アトミックチューン2Pro' AND is_deleted=0);

INSERT INTO motor_model
(name,series,shaft_type,motor_category,nominal_voltage,nominal_rpm,nominal_current_ma,nominal_torque_gcm,efficiency_index,stability_tendency,heat_tendency,brush_life_index,data_confidence,notes,is_deleted)
SELECT 'レブチューン2Pro','PRO','両軸','TUNED',2.4,20000,1450,170,1.20,'MEDIUM','MEDIUM',NULL,'HIGH','高回転安定型',0
WHERE NOT EXISTS (SELECT 1 FROM motor_model WHERE name='レブチューン2Pro' AND is_deleted=0);

INSERT INTO motor_model
(name,series,shaft_type,motor_category,nominal_voltage,nominal_rpm,nominal_current_ma,nominal_torque_gcm,efficiency_index,stability_tendency,heat_tendency,brush_life_index,data_confidence,notes,is_deleted)
SELECT 'ノーマル両軸','STD','両軸','NORMAL',2.4,11000,900,140,1.00,'HIGH','LOW',NULL,'HIGH','基準モーター両軸',0
WHERE NOT EXISTS (SELECT 1 FROM motor_model WHERE name='ノーマル両軸' AND is_deleted=0);

INSERT INTO motor_model
(name,series,shaft_type,motor_category,nominal_voltage,nominal_rpm,nominal_current_ma,nominal_torque_gcm,efficiency_index,stability_tendency,heat_tendency,brush_life_index,data_confidence,notes,is_deleted)
SELECT 'スプリントダッシュ','STD','片軸','DASH',2.4,26500,1700,175,1.35,'LOW','HIGH',NULL,'HIGH','ピーキー高速型',0
WHERE NOT EXISTS (SELECT 1 FROM motor_model WHERE name='スプリントダッシュ' AND is_deleted=0);

INSERT INTO motor_model
(name,series,shaft_type,motor_category,nominal_voltage,nominal_rpm,nominal_current_ma,nominal_torque_gcm,efficiency_index,stability_tendency,heat_tendency,brush_life_index,data_confidence,notes,is_deleted)
SELECT 'パワーダッシュ','STD','片軸','DASH',2.4,23000,1750,230,1.10,'LOW','HIGH',NULL,'HIGH','トルク特化型',0
WHERE NOT EXISTS (SELECT 1 FROM motor_model WHERE name='パワーダッシュ' AND is_deleted=0);

INSERT INTO motor_model
(name,series,shaft_type,motor_category,nominal_voltage,nominal_rpm,nominal_current_ma,nominal_torque_gcm,efficiency_index,stability_tendency,heat_tendency,brush_life_index,data_confidence,notes,is_deleted)
SELECT 'ライトダッシュ','STD','片軸','TUNED',2.4,17500,1150,160,1.05,'HIGH','MEDIUM',NULL,'MEDIUM','安定型',0
WHERE NOT EXISTS (SELECT 1 FROM motor_model WHERE name='ライトダッシュ' AND is_deleted=0);

INSERT INTO motor_model
(name,series,shaft_type,motor_category,nominal_voltage,nominal_rpm,nominal_current_ma,nominal_torque_gcm,efficiency_index,stability_tendency,heat_tendency,brush_life_index,data_confidence,notes,is_deleted)
SELECT 'ノーマル片軸','STD','片軸','NORMAL',2.4,10500,850,135,1.00,'HIGH','LOW',NULL,'HIGH','基準モーター片軸',0
WHERE NOT EXISTS (SELECT 1 FROM motor_model WHERE name='ノーマル片軸' AND is_deleted=0);

COMMIT;

-- ============================================================
-- IMPORTANT MODEL CODE MAPPING
-- ============================================================
-- Existing integer DB IDs remain the stable foreign-key values.
-- Confirmed model codes are:
--   1=TT2, 2=AT2, 3=RT2, 4=HD3, 5=PD (legacy hidden)
--   New rows require a separate stable model-code column if the
--   string IDs must be persisted as database keys. This migration
--   intentionally does not alter the existing schema.
-- ============================================================
