# 310-5 T09/T15 transport blocking-point review (2026-11-03)

## Scope

Host-source inspection only. No serial device opened, no CI dispatched, no firmware
or wire protocol changes. This document records what the current Python transport
can and cannot establish. It does not authorize hardware tests.

## Observed call path

- `ProtocolClient.send_pwm()` encodes PWM and calls `self.transport.send(...)`.
- `ProtocolClient.send_stop()` encodes STOP and calls the same
  `self.transport.send(...)`.
- `PySerialTransport.send()` invokes pySerial `write(payload)`, then
  `flush()`, then checks the returned byte count.
- The current `PySerialTransport` constructor configures a read timeout but does
  not configure a write timeout.
- No transport-level priority queue, STOP-reserved writer, independent STOP
  channel, or cancellation of an in-flight write is present in this path.

## Consequences

1. The controller's non-blocking abort-entry lock prevents duplicate/reentrant
   abort transitions among threads in one process. It does not interrupt an
   already executing PWM send.
2. A STOP caller can be delayed by the same serial writer/driver path used by
   PWM. A host lock around the abort state does not grant STOP transport priority.
3. Because write timeout is not configured and flush is synchronous, the
   inspected source does not establish a finite upper bound for STOP completion.
   Do not infer a deadline from the read timeout.
4. A successful return from `send_stop()` means only that the host transport
   call returned without raising. It is not proof of MCU receipt, output cutoff,
   current decay, or rotor stop.

## Required design decisions before a bounded/priority implementation

- Define whether STOP may use a second independent physical UART/channel or must
  share the existing UART. This is a system/hardware architecture decision; do
  not invent a second channel in host code.
- Define whether a currently executing PWM write may finish, be cancelled, or
  cause a fail-closed transport fault before STOP is attempted.
- Define the maximum allowed host-side STOP dispatch latency and which operations
  are included (queue wait, write, flush, OS/driver buffering).
- Define whether STOP retries are allowed after uncertain write/flush outcome,
  and how duplicate STOP frames are handled by firmware.
- Define the expected behavior if the transport thread is permanently blocked.

## Host-only acceptance evidence still needed

- Deterministic fake-transport tests for PWM blocked while STOP is requested.
- Tests for write exception, short write, flush exception, and unknown partial
  transmission outcome.
- Tests proving the selected arbitration policy does not silently discard STOP.
- If a bounded deadline is claimed, tests must cover every blocking operation
  and use a deadline mechanism whose bound is actually enforceable. A test using
  only a fake clock cannot prove OS/driver write or flush bounds.

## Status

This is an inspection/design artifact, not implementation acceptance.
T09/T15 remain NOT PASS. Tests are NOT RUN. No CI, no hardware, and no physical
safety claim. Formal 310-5 remains 0/18 PASS pending upper-command review.
