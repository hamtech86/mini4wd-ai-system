# Battery Benchmark Specification v2

Battery Benchmark Result is the analysis-ready summary of a completed discharge Measurement Session. Raw time-series Measurement remains the source of truth.

## Required fields

- `start_voltage`: first valid voltage in the discharge measurement interval
- `end_voltage`: last valid voltage in the discharge measurement interval
- `avg_voltage`
- `avg_current`
- `avg_power`
- `max_current`
- `max_power`
- `discharge_time_s`: elapsed time from first to last valid measurement
- `voltage_drop`: `start_voltage - end_voltage`
- `capacity_mah`
- `energy_wh`
- `measurement_count`

## Derivation rules

1. Start/end voltage are derived automatically from raw Measurement data.
2. CH1 and CH2 are supported independently. The populated voltage channel (`voltage1` or `voltage2`) is used.
3. Discharge time is derived from `measurement.elapsed_time`.
4. Voltage drop is calculated only from start/end voltage, never max/min voltage.
5. Raw Measurement data is never deleted by Benchmark processing.
6. Only COMPLETE sessions are eligible for formal Benchmark Result registration.

## E2E acceptance criterion

Completion requires an existing real Measurement session to populate `start_voltage`, `end_voltage`, and `voltage_drop` in `battery_benchmark_result`, followed by verification against the raw Measurement rows.


## Validity and fail-closed derivation

- Every Measurement row in the selected channel's analysis input must contain finite numeric selected-channel voltage, current, and elapsed time.
- A missing, non-numeric, NaN, infinite, or selected-channel 0.0 voltage/current value makes derived Benchmark validity UNKNOWN. The row is not silently skipped and no partial Benchmark is produced.
- A 0.0 value in the non-selected channel does not invalidate the selected channel.
- Raw Measurement and RawLog values remain unchanged. No replacement threshold or inactive-sentinel meaning is inferred.

## Immutable registration and retry behavior

- A persisted result is identified by `session_id + analysis_version` under the existing unique constraint.
- Repeating registration with an exactly equal persisted payload is an idempotent no-op; it does not INSERT, UPDATE, REPLACE, or delete.
- A differing payload for the same key is a Conflict and is rejected. The original result remains unchanged.
- Comparison covers every persisted payload field. If any field cannot be compared, the retry is rejected as Conflict rather than assumed equal.
- Revision history is not introduced by this specification revision; it requires a separate schema design and approval.

## Capture restart protection

- A channel with STARTING/RUN/RUNNING/STOPPING state, any in-memory unpersisted Sample, or a completed-but-unregistered capture cannot be restarted.
- Samples are released from memory only after the relevant persistence boundary succeeds (DB commit in normal mode; successful RawLog save in Anonymous Mode).
- Failed persistence retains the capture for retry. No implicit discard operation is provided.
- CH1 and CH2 restart eligibility is evaluated independently. STARTALL is rejected if either target channel is not eligible; it must not clear either channel's pending data.

## Raw Sample state

- Each Measurement row preserves the Sample's own state value. Session/Measurement Outcome COMPLETE is not copied onto every Sample row.
- Raw Measurement values and state are not rewritten to make the Benchmark appear complete.
