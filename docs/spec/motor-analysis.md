# Motor Analysis Specification

Status: REBUILD / single source of truth

## Scope
This document is the authoritative specification for Motor Analysis only. It replaces conflicting historical analysis instructions for this scope. Issue #5 is coordination history, not the calculation specification.

## Mandatory outputs
1. Estimated no-load RPM
2. Estimated torque
3. Estimated brush peak life-cycle
4. Estimated supported vehicle weight

RPM and torque are displayed independently at 3.0 V and 2.8 V where applicable.

## Input boundary
- Analysis input is the motor's raw log measurements, primarily measured motor voltage and current.
- Measured RPM is not an analysis input.
- Motor Model nominal data may be used as reference data for the estimator, but must not be emitted as if it were the individual motor's measured performance.
- Verification samples such as Cal7570 are individual raw-log data sets.

## Data separation
### Break-in recipe
Tune Basic is a break-in recipe. A motor that was processed with Tune Basic may provide a verification log. That fact describes the source/history of the sample only.

Tune Basic is NOT:
- a brush-peak reference;
- a brush-life reference;
- an RPM reference;
- a torque reference;
- a vehicle-weight reference;
- a voltage-conversion reference.

### Atomic Tune
Atomic Tune may exist as a motor model / relative-comparison reference elsewhere in the project. It is NOT the reference for brush peak or brush life-cycle.

## Brush peak / life-cycle
Brush peak is an estimated motor state in which brush/commutator bedding-in is associated with maximum motor performance. It is inferred from observed changes/stability in the relevant current signals, including A1 / ACS712 channel 2 where available.

The following are explicitly NOT valid brush-life bases:
- Atomic Tune = 100%;
- brush_peak_current = 1.498 A as a fixed lifetime reference;
- Tune Basic completion;
- arbitrary absolute cycle counts.

Temporary lifecycle notation:
- peak = 0
- opening state = +10 (provisional)
- post-peak = negative values
- damaged / unevaluable = -∞

The +10 scale remains provisional until sufficient logs are accumulated and validated.

## Prohibited legacy paths
Do not use or reintroduce legacy gain-based calculation paths such as voltage_gain/current_gain/torque_gain or measured-average-RPM substitution for the individual estimate.

## Implementation rule
Every displayed value must trace through the current Motor Analysis result contract. Independent legacy calculators must not provide competing values.

## Verification
Use raw-log samples to verify the complete path:
raw log -> feature extraction -> Motor Analysis -> result contract -> UI.
The verification sample's break-in recipe history must not alter the estimator's reference basis unless a future specification explicitly defines such a relationship.

## Unresolved items
Any numerical coefficient not explicitly approved in this specification is not to be invented. It must remain unresolved until formally specified and then be added here before implementation is treated as final.
