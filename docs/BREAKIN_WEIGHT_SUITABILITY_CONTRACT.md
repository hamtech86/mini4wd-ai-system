# Break-in UI Weight Suitability Contract

The Analysis Engine now exposes vehicle-weight suitability through:

`AnalysisResult.performance.weight_suitability`

Fields:

- `recommended_min_g`
- `recommended_max_g`
- `upper_limit_g`
- `current_reference_g` (130 g)
- `comparison_weight_g` (140 g)
- `target_acceleration_mps2`
- `drivetrain_efficiency`
- `tire_diameter_mm`
- `gear_ratio`
- `points`

Each point contains:

- `weight_g`
- `required_torque_gcm`
- `available_torque_gcm`
- `surplus_torque_gcm`
- `torque_margin`
- `status` (`RECOMMENDED`, `ACCEPTABLE`, `LIMIT`, `UNSUITABLE`)

The default profile evaluates 115–155 g in 5 g steps. The 130 g reference and 140 g comparison are explicitly retained for UI display.

The old linear `estimated_weight = torque * torque_gain` field remains only for compatibility. It is not the physical suitability result.

## UI mapping

Recommended first display:

- Recommended Weight: `recommended_min_g–recommended_max_g g`
- Upper Limit: `upper_limit_g g`
- 130 g Margin: point where `weight_g == 130`
- 140 g Margin: point where `weight_g == 140`
- Weight Profile: all nine points from 115 g through 155 g

The result is produced by the Analysis Engine and is therefore available to the break-in UI without coupling UI code to the calculation formula.
