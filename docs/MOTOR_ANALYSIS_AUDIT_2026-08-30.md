# Motor Analysis Audit — 2026-08-30

## Finding
The current Motor Analysis implementation had two distinct problems:

1. `brush_peak_current` was being treated as a shaft-load proxy for torque. In MOTOR_BREAKIN_V3 it is a brush-event peak and is not a calibrated shaft-load current. This can produce a grossly inflated torque estimate.
2. `WEIGHT_PER_TORQUE = 1.0726072607` was a hard-coded torque-to-weight multiplier. This is not the formally audited supported-weight definition and must not be treated as a physical law.

## Contract retained
- Measurement V/I is the source input.
- Measured RPM is never used.
- 3.0 V and 2.8 V are independent reference estimates.
- All RPM/torque/weight outputs are estimates.
- 130 g is not an input to the motor-performance estimate.

## Change
`analysis/performance.py` was corrected so brush-event peak current is no longer used as motor torque. Torque falls back to the motor-model current/torque relationship using `current_avg`, while the supported-weight conversion remains explicitly isolated pending the audited formal definition.

Commit: `c50c52ea4527228729ef07109987c3b62d67c5a6`

## Remaining issue
The supported-weight formula itself still requires restoration from the audited Motor Analysis definition. The current YAML coefficient must not be interpreted as a physical truth. No 130 g anchoring is permitted.
