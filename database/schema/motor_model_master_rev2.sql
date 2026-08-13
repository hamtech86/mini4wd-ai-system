-- ============================================================
-- motor_model_master_rev2.sql
-- MINI4WD AI SYSTEM
-- Confirmed Motor Model Master: 15 models
-- ============================================================
-- Existing motor_model_id INTEGER PK is preserved.
-- model_code stores the confirmed stable IDs (MD_PRO, HD_PRO, ...).
-- Existing Motor Instance foreign keys therefore remain valid.

PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

-- Add the stable logical Motor Model ID without changing the
-- existing INTEGER foreign-key structure.
ALTER TABLE motor_model ADD COLUMN model_code TEXT;

-- Existing models: preserve DB IDs 1-5 and map them to the
-- confirmed master IDs.
UPDATE motor_model SET
    model_code='TT2', name='トルクチューン2', series='STD', shaft_type='片軸', motor_category='TUNED',
    nominal_voltage=2.4, nominal_rpm=14500, nominal_current_ma=1350, nominal_torque_gcm=210,
    efficiency_index=0.95, stability_tendency='HIGH', heat_tendency='LOW', brush_life_index=NULL,
    data_confidence='HIGH', notes='定番トルク型', is_deleted=0
WHERE motor_model_id=1;

UPDATE motor_model SET
    model_code='AT2', name='アトミックチューン2', series='STD', shaft_type='片軸', motor_category='TUNED',
    nominal_voltage=2.4, nominal_rpm=15500, nominal_current_ma=1300, nominal_torque_gcm=195,
    efficiency_index=1.00, stability_tendency='HIGH', heat_tendency='MEDIUM', brush_life_index=NULL,
    data_confidence='HIGH', notes='万能型', is_deleted=0
WHERE motor_model_id=2;

UPDATE motor_model SET
    model_code='RT2', name='レブチューン2', series='STD', shaft_type='片軸', motor_category='TUNED',
    nominal_voltage=2.4, nominal_rpm=19000, nominal_current_ma=1400, nominal_torque_gcm=165,
    efficiency_index=1.15, stability_tendency='MEDIUM', heat_tendency='MEDIUM', brush_life_index=NULL,
    data_confidence='HIGH', notes='高回転型', is_deleted=0
WHERE motor_model_id=3;

UPDATE motor_model SET
    model_code='HD3', name='ハイパーダッシュ3', series='STD', shaft_type='片軸', motor_category='DASH',
    nominal_voltage=2.4, nominal_rpm=23500, nominal_current_ma=1650, nominal_torque_gcm=200,
    efficiency_index=1.20, stability_tendency='LOW', heat_tendency='HIGH', brush_life_index=NULL,
    data_confidence='MEDIUM', notes='高負荷安定型', is_deleted=0
WHERE motor_model_id=4;

UPDATE motor_model SET
    model_code='PD', name='パワーダッシュ', series='STD', shaft_type='片軸', motor_category='DASH',
    nominal_voltage=2.4, nominal_rpm=23000, nominal_current_ma=1750, nominal_torque_gcm=230,
    efficiency_index=1.10, stability_tendency='LOW', heat_tendency='HIGH', brush_life_index=NULL,
    data_confidence='HIGH', notes='トルク特化型', is_deleted=0
WHERE motor_model_id=5;

-- New confirmed models. Existing names/codes are used as the
-- idempotency key so this migration can safely be rerun only on a
-- database where model_code has not already been populated.
INSERT INTO motor_model
(model_code,name,series,shaft_type,motor_category,nominal_voltage,nominal_rpm,nominal_current_ma,nominal_torque_gcm,efficiency_index,stability_tendency,heat_tendency,brush_life_index,data_confidence,notes,is_deleted)
SELECT 'MD_PRO','マッハダッシュPro','PRO','両軸','DASH',2.4,25500,1650,180,1.40,'LOW','HIGH',NULL,'HIGH','高回転ピーキー最上位',0
WHERE NOT EXISTS (SELECT 1 FROM motor_model WHERE model_code='MD_PRO');

INSERT INTO motor_model
(model_code,name,series,shaft_type,motor_category,nominal_voltage,nominal_rpm,nominal_current_ma,nominal_torque_gcm,efficiency_index,stability_tendency,heat_tendency,brush_life_index,data_confidence,notes,is_deleted)
SELECT 'HD_PRO','ハイパーダッシュPro','PRO','両軸','DASH',2.4,24000,1600,190,1.30,'LOW','HIGH',NULL,'HIGH','バランス高回転型',0
WHERE NOT EXISTS (SELECT 1 FROM motor_model WHERE model_code='HD_PRO');

INSERT INTO motor_model
(model_code,name,series,shaft_type,motor_category,nominal_voltage,nominal_rpm,nominal_current_ma,nominal_torque_gcm,efficiency_index,stability_tendency,heat_tendency,brush_life_index,data_confidence,notes,is_deleted)
SELECT 'LD_PRO','ライトダッシュPro','PRO','両軸','TUNED',2.4,18500,1200,165,1.15,'HIGH','MEDIUM',NULL,'HIGH','安定高速型',0
WHERE NOT EXISTS (SELECT 1 FROM motor_model WHERE model_code='LD_PRO');

INSERT INTO motor_model
(model_code,name,series,shaft_type,motor_category,nominal_voltage,nominal_rpm,nominal_current_ma,nominal_torque_gcm,efficiency_index,stability_tendency,heat_tendency,brush_life_index,data_confidence,notes,is_deleted)
SELECT 'TT2_PRO','トルクチューン2Pro','PRO','両軸','TUNED',2.4,15000,1400,220,1.00,'HIGH','LOW',NULL,'HIGH','トルク特化型',0
WHERE NOT EXISTS (SELECT 1 FROM motor_model WHERE model_code='TT2_PRO');

INSERT INTO motor_model
(model_code,name,series,shaft_type,motor_category,nominal_voltage,nominal_rpm,nominal_current_ma,nominal_torque_gcm,efficiency_index,stability_tendency,heat_tendency,brush_life_index,data_confidence,notes,is_deleted)
SELECT 'AT2_PRO','アトミックチューン2Pro','PRO','両軸','TUNED',2.4,16000,1350,200,1.05,'HIGH','MEDIUM',NULL,'HIGH','万能型',0
WHERE NOT EXISTS (SELECT 1 FROM motor_model WHERE model_code='AT2_PRO');

INSERT INTO motor_model
(model_code,name,series,shaft_type,motor_category,nominal_voltage,nominal_rpm,nominal_current_ma,nominal_torque_gcm,efficiency_index,stability_tendency,heat_tendency,brush_life_index,data_confidence,notes,is_deleted)
SELECT 'RT2_PRO','レブチューン2Pro','PRO','両軸','TUNED',2.4,20000,1450,170,1.20,'MEDIUM','MEDIUM',NULL,'HIGH','高回転安定型',0
WHERE NOT EXISTS (SELECT 1 FROM motor_model WHERE model_code='RT2_PRO');

INSERT INTO motor_model
(model_code,name,series,shaft_type,motor_category,nominal_voltage,nominal_rpm,nominal_current_ma,nominal_torque_gcm,efficiency_index,stability_tendency,heat_tendency,brush_life_index,data_confidence,notes,is_deleted)
SELECT 'NOR_DBL','ノーマル両軸','STD','両軸','NORMAL',2.4,11000,900,140,1.00,'HIGH','LOW',NULL,'HIGH','基準モーター両軸',0
WHERE NOT EXISTS (SELECT 1 FROM motor_model WHERE model_code='NOR_DBL');

INSERT INTO motor_model
(model_code,name,series,shaft_type,motor_category,nominal_voltage,nominal_rpm,nominal_current_ma,nominal_torque_gcm,efficiency_index,stability_tendency,heat_tendency,brush_life_index,data_confidence,notes,is_deleted)
SELECT 'SPT','スプリントダッシュ','STD','片軸','DASH',2.4,26500,1700,175,1.35,'LOW','HIGH',NULL,'HIGH','ピーキー高速型',0
WHERE NOT EXISTS (SELECT 1 FROM motor_model WHERE model_code='SPT');

INSERT INTO motor_model
(model_code,name,series,shaft_type,motor_category,nominal_voltage,nominal_rpm,nominal_current_ma,nominal_torque_gcm,efficiency_index,stability_tendency,heat_tendency,brush_life_index,data_confidence,notes,is_deleted)
SELECT 'LD','ライトダッシュ','STD','片軸','TUNED',2.4,17500,1150,160,1.05,'HIGH','MEDIUM',NULL,'MEDIUM','安定型',0
WHERE NOT EXISTS (SELECT 1 FROM motor_model WHERE model_code='LD');

INSERT INTO motor_model
(model_code,name,series,shaft_type,motor_category,nominal_voltage,nominal_rpm,nominal_current_ma,nominal_torque_gcm,efficiency_index,stability_tendency,heat_tendency,brush_life_index,data_confidence,notes,is_deleted)
SELECT 'NOR_STD','ノーマル片軸','STD','片軸','NORMAL',2.4,10500,850,135,1.00,'HIGH','LOW',NULL,'HIGH','基準モーター片軸',0
WHERE NOT EXISTS (SELECT 1 FROM motor_model WHERE model_code='NOR_STD');

COMMIT;

-- Expected active models after migration: 15.
