-- ============================================================
-- initial_data.sql
-- Motor Database System
-- Revision 1
-- SQLite3
-- Initial Master Data
-- ============================================================


PRAGMA foreign_keys = ON;


-- ============================================================
-- schema_info update
-- ============================================================

UPDATE schema_info

SET
    schema_version = 'Rev.1',
    updated_at = CURRENT_TIMESTAMP

WHERE
    schema_version = 'Rev.1';



-- ============================================================
-- motor_model
-- Initial motor master data
--
-- Note:
-- Actual measured values should be updated later.
-- Values below are reference specifications only.
-- ============================================================



INSERT INTO motor_model
(
    name,
    series,
    shaft_type,
    motor_category,
    nominal_voltage,
    nominal_rpm,
    nominal_current_ma,
    nominal_torque_gcm,
    efficiency_index,
    stability_tendency,
    heat_tendency,
    brush_life_index,
    data_confidence,
    notes
)

VALUES

(
    'Torque Tune 2',
    'TT2',
    'FA130',
    'TORQUE',
    2.4,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    0.5,
    'Initial master entry. Replace with measured data.'
),


(
    'Atomic Tune 2',
    'AT2',
    'FA130',
    'BALANCE',
    2.4,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    0.5,
    'Initial master entry. Replace with measured data.'
),


(
    'Rev Tune 2',
    'RT2',
    'FA130',
    'HIGH_RPM',
    2.4,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    0.5,
    'Initial master entry. Replace with measured data.'
),


(
    'Hyper Dash 3',
    'HD3',
    'FA130',
    'SPEED',
    2.4,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    0.5,
    'Initial master entry. Replace with measured data.'
),


(
    'Power Dash 2',
    'PD2',
    'FA130',
    'POWER',
    2.4,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    0.5,
    'Initial master entry. Replace with measured data.'
);



-- ============================================================
-- END OF initial_data.sql Rev.1
-- ============================================================

