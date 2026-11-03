# 310-5 T09/T15 host STOP arbitration fixtures (candidate)

Date: 2026-11-03
Branch: `safety/310-5-host-integration-candidate`
Authority: upper-command decision comment `6602410842`

## Scope

These are deterministic host-side regression fixtures for the existing
`SequenceController.abort()` path. They do not change firmware, wire format,
RawLog schema, accepted 310-4 documents, or hardware.

## Covered ordering

1. The controller enters STOPPING before invoking the injected STOP callback.
2. The STOP callback is attempted before aborted-stage/session evidence append.
3. If STOP callback raises, the controller records the failure in its fault
   state and still attempts best-effort abort evidence logging.
4. Successful STOP callback plus successful logging leaves the host controller
   ABORTED; failed STOP callback leaves it FAULT.

Tests added to `tests/test_measurement_310.py`:
- `test_abort_attempts_stop_before_any_abort_record_append` (success/failure parameterization)
- `test_stop_callback_failure_does_not_prevent_best_effort_abort_logging`

## Explicitly not covered

- Independent STOP UART path, queue bypass, preemption, TX drain bypass, or
  write-timeout behavior.
- A blocked/hung STOP callback; the current callback is synchronous and can
  block the caller indefinitely.
- Concurrent races among user STOP, safety STOP, timeout, storage failure,
  disconnect, and repeated abort calls.
- Any numeric latency/deadline guarantee.
- MCU output disable, driver cutoff, current decay, or rotor stop.

The candidate `ProtocolClient.send_stop()` uses the same
`SerialTransport.send()` path as PWM. The current PySerial adapter performs
synchronous write/flush without a demonstrated independent bounded STOP path.
Therefore these fixtures establish call ordering only, not STOP priority or
physical safety.

## Execution status

Authored only; NOT RUN in this environment. No CI dispatch. No physical
hardware activity. Formal T09/T15 acceptance remains NOT PASS pending
upper-command review and the required independent-path/concurrency evidence.

## Re-entrant/repeated request latch (2026-11-03 follow-up)

The controller now returns immediately when `abort()` is called while state is
STOPPING, ABORTED, FAULT, or COMPLETED. This prevents a synchronous re-entrant
callback from recursively invoking STOP and prevents later sequential abort
calls from duplicating STOP/log records. The first abort request owns the
transition; nested requests do not replace its reason.

Implementation commit: `0fbffdbd9667cba836cd0ddb1b202817d49de0f3`.
Regression tests: `e39294ae2e7155928267604bd62d9223d38e995d` (initial fixture),
`0452902fa573adf09359970147a8884cd8f2d325` (first-request-wins assertion).

This is a re-entrancy/sequential idempotence latch only. It is NOT a
thread-synchronization primitive: simultaneous calls from multiple threads can
still race between the state check and STOPPING assignment. No claim of
concurrent arbitration or STOP deadline is made. Tests remain NOT RUN.


## Atomic host-thread entry latch (2026-11-03 follow-up)

The abort entry now uses a non-blocking `threading.Lock` around the state
check and transition to STOPPING. A concurrent caller that arrives while the
first caller is in the STOP callback returns without sending another STOP.
The lock is released before invoking the callback, so synchronous callback
re-entry does not deadlock. This protects the abort-entry decision among
threads in this Python process; it does not establish transport-level STOP
priority, cancellation of an in-flight PWM write, or a bounded STOP deadline.

Implementation: `43071b42f15b61634e6659d7f990b509de978714`.
Concurrent-caller regression test: `e7270ac73c331ac94147d8e21f36a73f4d056539`.
Tests remain NOT RUN; no CI and no hardware activity.
