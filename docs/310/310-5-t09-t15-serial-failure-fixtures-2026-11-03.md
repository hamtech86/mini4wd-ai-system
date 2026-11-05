# 310-5 T09/T15 serial write failure fixtures (2026-11-03)

## Scope

Host-only deterministic tests using a fake pySerial module and fake serial object.
No operating-system serial port is opened. No hardware, firmware, CI, or real
transport timing is exercised.

## Cases added

- `write()` raises after an unknown amount of progress: surfaced as
  `TransportError`; transmission outcome remains unknown.
- `write()` returns fewer bytes than requested: `flush()` is still called by
  the current adapter, then the short write is rejected.
- `flush()` raises after `write()`: surfaced as `TransportError`; bytes may
  already have been queued or transmitted, so the outcome is unknown.
- Full write and successful flush: send returns normally.

## Interpretation

A write/flush exception is not evidence that no bytes reached the device.
The host must treat the command delivery outcome as uncertain. In particular,
a failed STOP send does not prove that STOP was not received, and a returned
send call does not prove that the MCU acted on it.

The fixtures verify call ordering and error propagation only. They do not
measure or bound real pySerial, OS, USB, driver, or UART latency. They do not
establish STOP priority over an in-flight PWM send.

## Status

Tests authored; NOT RUN. No CI dispatch, no hardware activity. T09/T15 remain
NOT PASS pending execution evidence and upper-command review.
