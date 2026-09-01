# Battery Analysis Specification

Status: REBUILD / single source of truth

## Scope
This document is the authoritative specification for Battery Analysis only. It is separate from battery hardware control, firmware, break-in recipes, and Motor Analysis. Issue #5 is coordination history, not the calculation specification.

## Input boundary
- Analysis consumes the approved Battery Measurement / Benchmark Result data produced by the battery evaluation pipeline.
- Measurement and benchmark records are treated as immutable inputs.
- Analysis must not silently alter raw measurements.

## Separation of responsibilities
- Battery control / discharge execution: hardware-control scope.
- Battery Benchmark: produces benchmark results from measurement data.
- Battery Analysis: interprets approved benchmark results into analysis results.
- Motor Analysis: completely separate scope.

## Current analysis outputs
Battery Analysis may expose the metrics already defined by the approved battery-analysis contract, including electrical metrics, capacity/energy, voltage-drop information, stability metrics, and warnings where approved inputs and thresholds exist.

Metrics whose required approved inputs or thresholds are not defined must remain unevaluated rather than being fabricated. In particular, ranking, voltage-drop-rate, and internal-resistance conclusions must not be invented when the required approved inputs/specification are absent.

## Data integrity
- Do not mutate Measurement or Benchmark Result inputs.
- Do not import Motor Analysis calculations or motor-model assumptions.
- Do not use historical gain logic from unrelated scopes.
- Do not add a metric merely because a historical chat mentioned it; the metric must be defined in this specification or formally added to it.

## Verification
Verify the complete path independently:
Measurement -> Benchmark Result -> Battery Analysis Result -> UI.

The analysis result must be traceable to the approved battery input records and the formulas/thresholds defined here.

## Unresolved items
Any numerical coefficient, threshold, ranking rule, or derived metric not explicitly approved in this specification is unresolved and must not be invented. Add it here before treating an implementation as final.
