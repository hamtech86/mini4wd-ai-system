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
- Tolerance: 0.05 V
- Direction: FWD
- Duration: 120 s
- Voltage is controlled by PWM feedback using the measured `motor_voltage` field.

This makes the final comparison independent of small PWM/supply differences.

## Safety

The controller applies these defaults unless explicitly overridden:

- Motor temperature: 70 °C maximum
- Current: 5.0 A maximum
- PWM: 245 maximum

A safety violation causes an emergency stop and an ERROR session result.

## Architecture

`config/breakin_recipes.yaml` → `RecipeEngine` → `BreakinRecipe` → `BreakinController`

The RecipeEngine validates the declarative recipe and never sends hardware commands. The controller owns hardware execution. Analysis owns final performance/brush/usage judgement.

## Versioning

Recipe catalog version is `2.0`. Individual recipes can evolve independently by changing the catalog while keeping the RecipeEngine/controller contract stable.
