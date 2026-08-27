-- ============================================================
-- initial_data.sql
-- Motor Database System
-- Revision 2
-- SQLite3
-- Initial motor master data
-- ============================================================

PRAGMA foreign_keys = ON;

UPDATE schema_info
SET schema_version = 'Rev.2', updated_at = CURRENT_TIMESTAMP
WHERE schema_version = 'Rev.1';

-- Reference values are centered on the manufacturer's published
-- specification ranges. Torque is stored in g·cm for the Analysis model.
-- 1 mN·m = 10.19716213 g·cm.

INSERT INTO motor_model
(
    name, series, shaft_type, motor_category,
    nominal_voltage, nominal_rpm, nominal_current_ma,
    nominal_torque_gcm, efficiency_index, stability_tendency,
    heat_tendency, brush_life_index, data_confidence, notes
)
VALUES
(
    'Atomic Tune 2',
    'AT2',
    'FA130',
    'BALANCE',
    2.7,
    13800,
    2000,
    16.83,
    NULL,
    NULL,
    NULL,
    NULL,
    0.85,
    'Reference midpoint from Tamiya published specification: 2.4-3.0V, 12700-14900rpm, recommended load torque 1.5-1.8mN·m, current 1.8-2.2A. Torque midpoint 1.65mN·m converted to 16.83g·cm. Replace with project-specific measured master data when available.'
);

-- ============================================================
-- END OF initial_data.sql Rev.2
-- ============================================================
