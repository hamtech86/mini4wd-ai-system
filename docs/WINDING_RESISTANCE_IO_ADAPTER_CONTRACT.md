# Winding resistance measurement I/O adapter contract

## Scope and enablement gate

This contract defines the boundary between the pure winding-measurement policy/aggregation code and Arduino hardware I/O. It is not authorization to energize the motor or inject current.

**Current status: injection is disabled.** The independent hardware current limiter has not yet been demonstrated from circuit/part evidence and an actual test. A software ACS712 reading, UI checkbox, or hardwareCurrentLimitConfirmed flag alone is not proof of an independent limiter.

## Required interlocks

1. The winding measurement request is accepted only from IDLE with explicit ARM and confirmed independent current limiting.
2. Normal DRIVE and winding measurement are mutually exclusive. A start request while DRIVE is active is rejected and outputs remain OFF.
3. On STOP, timeout, ARM loss, current-limit confirmation loss, ADC/measurement fault, or adapter internal fault, the adapter synchronously commands all relevant bridge and injection outputs OFF before returning control.
4. Any output pulse is bounded by a monotonic deadline. Deadline expiry forces OFF; no wait loop may block STOP processing.
5. The adapter must verify/read back the output-off state where hardware permits. Failure to establish OFF latches an abort and prevents re-arm.
6. Injection and rotor movement must never be active together. Transition requires confirmed OFF and a dead-time interval.
7. ADC V and I values are accepted only as a synchronized pair from the same injection window. Timestamp and acquisition status travel with the pair; a stale or incomplete pair is invalid.
8. MOVE has a separately bounded duration and direction. Completion is followed by OFF and settle before another injection request.
9. Any abort requires explicit user re-arm; automatic restart is prohibited.

## Policy/action mapping

| Policy state/action | Adapter responsibility | Fail-safe outcome |
|---|---|---|
| IDLE / start | Check DRIVE inactive, ARM, limiter evidence | Reject and keep OFF if any check fails |
| SETTLE | Keep all drive/injection outputs OFF; check stable/settled input | Timeout => OFF + abort |
| INJECT request | Start only bounded injection pulse after interlocks | Pulse deadline/STOP/fault => immediate OFF |
| SAMPLE request | Acquire paired V/I inside valid window; no new output transition | Missing/stale/invalid pair => OFF + report invalid |
| OFF | Force outputs OFF and confirm before next phase | Cannot confirm OFF => latched abort |
| MOVE request | After OFF/dead-time, bounded movement pulse | Timeout/STOP/ARM loss => immediate OFF |
| AGGREGATE | Outputs remain OFF; summarize accepted samples | Empty/insufficient/invalid-required set => no result |
| COMPLETE | Keep outputs OFF; report result | No automatic reactivation |
| ABORTED | Force OFF, retain cause, require explicit re-arm | Stay fail-closed |

## Sample and result handling

- Use the fixed-memory aggregator; maximum 32 V/I pairs.
- Preserve the first invalid reason and separately record rejected-sample count/reasons in AUX diagnostics.
- A result must identify whether it used strict all-points acceptance or partial valid-points mode. Never silently drop invalid samples.
- Median/min/max and accepted count are reported only when the selected acceptance policy is satisfied.
- Keep the existing DATA 26-column schema unchanged; detailed synchronized sample/diagnostic output belongs in AUX.

## Required adapter tests before hardware connection

- Start request while normal DRIVE active.
- STOP and timeout during every energized/request phase.
- ARM and independent-limit confirmation loss in every phase where output may be active.
- Output-off confirmation failure.
- Injection/movement mutual exclusion and dead-time.
- Injection and MOVE deadline expiration.
- Missing/stale/non-synchronized ADC pair.
- Aggregator empty, capacity overflow, strict/partial invalid policy, sign/range/current-resolution rejection.

## Explicit non-claim

Host policy and calculation tests do not establish the electrical current limit, switching transient safety, Arduino timing under load, sensor calibration, or actual motor behavior. Those remain separate evidence gates before physical injection is enabled.
