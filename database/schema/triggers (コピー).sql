-- ============================================================
-- triggers.sql
-- Motor Database System
-- Revision 1
-- SQLite3
-- ============================================================

PRAGMA foreign_keys = ON;

-- ============================================================
-- motor_model
-- updated_at
-- ============================================================

CREATE TRIGGER IF NOT EXISTS trg_motor_model_updated

AFTER UPDATE

ON motor_model

FOR EACH ROW

BEGIN

UPDATE motor_model

SET

updated_at = CURRENT_TIMESTAMP

WHERE

motor_model_id = NEW.motor_model_id;

END;





-- ============================================================
-- motor_instance
-- updated_at
-- ============================================================

CREATE TRIGGER IF NOT EXISTS trg_motor_instance_updated

AFTER UPDATE

ON motor_instance

FOR EACH ROW

BEGIN

UPDATE motor_instance

SET

updated_at = CURRENT_TIMESTAMP

WHERE

instance_id = NEW.instance_id;

END;





-- ============================================================
-- schema_info
-- updated_at
-- ============================================================

CREATE TRIGGER IF NOT EXISTS trg_schema_info_updated

AFTER UPDATE

ON schema_info

FOR EACH ROW

BEGIN

UPDATE schema_info

SET

updated_at = CURRENT_TIMESTAMP;

END;





-- ============================================================
-- END OF triggers.sql
-- ============================================================


