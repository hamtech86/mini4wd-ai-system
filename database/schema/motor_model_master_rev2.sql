-- ============================================================
-- motor_model_master_rev2.sql
-- MINI4WD AI SYSTEM
-- Confirmed Motor Model Master: 15 models
-- ============================================================
--
-- Purpose:
--   Apply the司令塔-confirmed Motor Model Master to an existing DB.
--
-- Scope:
--   motor_model master only.
--   motor_instance / measurement / break-in history are not modified.
--
-- Stable shared key:
--   motor_model_id
--
-- Compatibility fields:
--   nominal_voltage remains 2.4 V (existing schema convention).
--   brush_life_index is NULL because it is not defined by the
--   confirmed master source.
--
PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

-- Existing IDs are updated in place so existing Motor Instance
-- foreign references remain attached to the same motor_model_id.
UPDATE motor_model SET
    name='トルクチューン2', series='STD', shaft_type='片軸', motor_category='TUNED',
    nominal_voltage=2.4, nominal_rpm=14500, nominal_current_ma=1350,
    nominal_torque_gcm=210, efficiency_index=0.95,
    stability_tendency='HIGH', heat_tendency='LOW', brush_life_index=NULL,
    data_confidence='HIGH', notes='定番トルク型', is_deleted=0
WHERE motor_model_id='TT2';

UPDATE motor_model SET
    name='アトミックチューン2', series='STD', shaft_type='片軸', motor_category='TUNED',
    nominal_voltage=2.4, nominal_rpm=15500, nominal_current_ma=1300,
    nominal_torque_gcm=195, efficiency_index=1.00,
    stability_tendency='HIGH', heat_tendency='MEDIUM', brush_life_index=NULL,
    data_confidence='HIGH', notes='万能型', is_deleted=0
WHERE motor_model_id='AT2';

UPDATE motor_model SET
    name='レブチューン2', series='STD', shaft_type='片軸', motor_category='TUNED',
    nominal_voltage=2.4, nominal_rpm=19000, nominal_current_ma=1400,
    nominal_torque_gcm=165, efficiency_index=1.15,
    stability_tendency='MEDIUM', heat_tendency='MEDIUM', brush_life_index=NULL,
    data_confidence='HIGH', notes='高回転型', is_deleted=0
WHERE motor_model_id='RT2';

UPDATE motor_model SET
    name='ハイパーダッシュ3', series='STD', shaft_type='片軸', motor_category='DASH',
    nominal_voltage=2.4, nominal_rpm=23500, nominal_current_ma=1650,
    nominal_torque_gcm=200, efficiency_index=1.20,
    stability_tendency='LOW', heat_tendency='HIGH', brush_life_index=NULL,
    data_confidence='MEDIUM', notes='高負荷安定型', is_deleted=0
WHERE motor_model_id='HD3';

-- PD2 is a legacy master key and is not part of the confirmed
-- 15-model choice list. Keep the row for referential integrity,
-- but hide it from MotorRepository.get_all() / selection UI.
UPDATE motor_model
SET is_deleted=1
WHERE motor_model_id='PD2';

-- Add the eleven new stable IDs. Existing rows are left untouched
-- by these INSERT OR IGNORE statements, making the migration safe
-- to re-run for already-created rows.
INSERT OR IGNORE INTO motor_model
(motor_model_id,name,series,shaft_type,motor_category,nominal_voltage,nominal_rpm,nominal_current_ma,nominal_torque_gcm,efficiency_index,stability_tendency,heat_tendency,brush_life_index,data_confidence,notes,is_deleted)
VALUES
('MD_PRO','マッハダッシュPro','PRO','両軸','DASH',2.4,25500,1650,180,1.40,'LOW','HIGH',NULL,'HIGH','高回転ピーキー最上位',0),
('HD_PRO','ハイパーダッシュPro','PRO','両軸','DASH',2.4,24000,1600,190,1.30,'LOW','HIGH',NULL,'HIGH','バランス高回転型',0),
('LD_PRO','ライトダッシュPro','PRO','両軸','TUNED',2.4,18500,1200,165,1.15,'HIGH','MEDIUM',NULL,'HIGH','安定高速型',0),
('TT2_PRO','トルクチューン2Pro','PRO','両軸','TUNED',2.4,15000,1400,220,1.00,'HIGH','LOW',NULL,'HIGH','トルク特化型',0),
('AT2_PRO','アトミックチューン2Pro','PRO','両軸','TUNED',2.4,16000,1350,200,1.05,'HIGH','MEDIUM',NULL,'HIGH','万能型',0),
('RT2_PRO','レブチューン2Pro','PRO','両軸','TUNED',2.4,20000,1450,170,1.20,'MEDIUM','MEDIUM',NULL,'HIGH','高回転安定型',0),
('NOR_DBL','ノーマル両軸','STD','両軸','NORMAL',2.4,11000,900,140,1.00,'HIGH','LOW',NULL,'HIGH','基準モーター両軸',0),
('SPT','スプリントダッシュ','STD','片軸','DASH',2.4,26500,1700,175,1.35,'LOW','HIGH',NULL,'HIGH','ピーキー高速型',0),
('PD','パワーダッシュ','STD','片軸','DASH',2.4,23000,1750,230,1.10,'LOW','HIGH',NULL,'HIGH','トルク特化型',0),
('LD','ライトダッシュ','STD','片軸','TUNED',2.4,17500,1150,160,1.05,'HIGH','MEDIUM',NULL,'MEDIUM','安定型',0),
('NOR_STD','ノーマル片軸','STD','片軸','NORMAL',2.4,10500,850,135,1.00,'HIGH','LOW',NULL,'HIGH','基準モーター片軸',0);

COMMIT;

-- ============================================================
-- END OF Motor Model Master Rev2
-- ============================================================
