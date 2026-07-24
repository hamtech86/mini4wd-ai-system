ALTER TABLE measurement_session
ADD COLUMN updated_at DATETIME;

UPDATE measurement_session
SET updated_at = CURRENT_TIMESTAMP;

