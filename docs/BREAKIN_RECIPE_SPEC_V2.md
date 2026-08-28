# MOTOR_BREAKIN_V3 — Break-in Recipe Specification v2

## Purpose

Recipes define the motor conditioning process. They do not decide whether a motor is good or bad. Final classification is performed by the Analysis Engine after the common 3 V benchmark.

## Recipes

| Recipe | Brush | Objective | 3 V benchmark target |
|---|---|---|---|
| `ATOMIC_25K` | Copper | Speed | 25,000 rpm class |
| `TORQUE_TUNE_23K` | Copper | Torque + usable speed | 23,000 rpm class |
| `TUNE_OPTIMIZED` | Copper | Overall optimization | No hard RPM pass line |
| `DASH_OPTIMIZED` | Carbon | Overall Dash optimization | No hard RPM pass line |

The RPM values are targets, not absolute pass/fail limits.

## Common benchmark

Every recipe ends with `BENCHMARK_3V`.

- Target motor voltage: 3.00 V
- Tolerance during the start condition: ±0.10 V
- Direction: FWD
- Official measurement duration: 30 s
- Voltage is controlled by PWM feedback using the measured `motor_voltage` field.

### Condition-based benchmark start

The official 30-second measurement does **not** start at the UI button press and does not use a fixed settling delay.

Before the official window begins, the controller enters `STABILIZING` and waits for a measurable, stable operating condition:

- Motor voltage is within 2.90–3.10 V.
- Measured motor current is at least 0.05 A.
- The conditions remain valid for at least 0.50 s.
- Voltage spread during that stability window is no more than 0.10 V.
- PWM spread during that stability window is no more than 5 counts.

When these conditions are met, that instant becomes `BENCHMARK_START` and the 30-second official measurement window begins.

Stabilization samples are not part of the official benchmark sample set and must not be exported as AI-analysis RAW LOG data. This also prevents a stopped motor or a manually-started motor from contributing pre-start zero-current samples to benchmark results.

If the start condition is not established within 15 s, the benchmark aborts with `BENCHMARK START TIMEOUT` and the motor is emergency-stopped.

## Safety

The controller applies these defaults unless explicitly overridden:

- Motor temperature: 70 °C maximum
- Current: 5.0 A maximum
- PWM: 245 maximum

A safety violation causes an emergency stop and an ERROR session result.

## Architecture

`config/breakin_recipes.yaml` → `RecipeEngine` → `BreakinRecipe` → `BenchmarkBreakinController` → `BreakinController`

The RecipeEngine validates the declarative recipe and never sends hardware commands. The benchmark-aware controller owns benchmark start detection and hardware execution. Analysis owns final performance/brush/usage judgement.

## Versioning

Recipe catalog version is `2.1`. Individual recipes can evolve independently by changing the catalog while keeping the RecipeEngine/controller contract stable.
