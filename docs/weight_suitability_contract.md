# Motor Weight Suitability Contract

## Purpose

Expose the motor-side compatible vehicle-weight analysis as an Analysis Engine result so the UI does not calculate suitability itself.

## Contract

- Weight range: 115–155 g
- Step: 5 g
- Reference vehicle: 130 g
- Comparison vehicle: 140 g
- Tire diameter: 24 mm
- Gear ratio: 3.5:1
- Result source: `PerformanceResult.weight_suitability`
- Measurement data remains read-only
- The UI displays the returned points/statuses and does not recalculate torque or weight

## Status

`RECOMMENDED`, `ACCEPTABLE`, `LIMIT`, and `UNSUITABLE` are calculated by `WeightSuitabilityAnalysis` from available estimated motor torque and configured margins.

The current implementation is explicitly a benchmark calibration. Course, roller, brake, and grip factors are excluded until calibration data is available.
