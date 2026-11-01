# 310-3 Python sequence and serial integration

## Scope
Python orchestration only. No Arduino firmware, physical serial port, motor output,
or real-hardware test is included. The wire protocol is intentionally injected
through `MessageCodec`; 310-4 must supply and approve its concrete implementation.

## Components
- `measurement_310.engine`: clock-injected PWM 0..30 scheduler, ACK-gated stage
  start, monotonic duration accounting, fail-closed timeout, STOP attempt, RawLog v2.
- `measurement_310.transport`: raw-byte serial transport, codec contract,
  in-memory mock and protocol-neutral command client. Serial framing is not assumed.
- `raw_log_v2`: consumed as-is; no public schema or storage contract changes.

## Important semantics
A command-send timestamp is not an application acknowledgement. An ACK is not
proof of physical motor output. Missing/mismatched ACKs abort without advancing.
The 10-second stage timer starts at ACK receipt and uses the monotonic clock.
Host send/receive timestamps are captured on the host side; serial receive does
not impose a newline or other framing rule.
Aborted work remains in the private incomplete-work area for startup recovery.
A STOP send attempt is not evidence of physical stopping.

## Protocol questions reserved for 310-4
Frame encoding, delimiters, escaping, checksum/CRC, command identifiers,
ACK correlation, device identity and boot/session identity, ADC line grammar,
device timestamp wrap/epoch semantics, device-state vocabulary, heartbeat,
timeouts/retries, STOP priority and idempotency remain unspecified.

## Limitations requiring review
The current implementation is an integration scaffold, not authorization to
energize hardware. Per-channel raw ADC record mapping and human visual EVENT
logging use existing schema records. Calibration ingestion, concrete firmware
codec binding, device telemetry/state parsing and firmware message semantics
are deferred until 310-4. No unknown record_type is introduced.

## Verification boundary
The pySerial adapter is lazy and was not instantiated against a device. All
sequence and transport tests use injected clocks and in-memory mock transport.
CI is required for regression evidence; local git/pytest execution was blocked
by the execution environment's DNS failure when resolving github.com.
