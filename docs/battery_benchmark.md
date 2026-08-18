# Battery Database + Benchmark Analysis

The Battery 5A Standalone firmware is an immutable measurement anchor.

Flow:

`Battery Model -> Battery Instance -> Measurement Session -> Measurement -> Feature Extraction -> Benchmark Result`

Measurement rows remain raw facts and are never overwritten by analysis.

Implemented benchmark features include average/max voltage/current/power, discharge time, voltage drop, capacity (Ah/mAh), energy (Wh), and voltage/current/power variability. Scores and internal resistance remain unset until validated reference methods are supplied.
