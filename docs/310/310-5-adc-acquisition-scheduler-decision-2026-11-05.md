# 310-5 ADC acquisition scheduler decision — 2026-11-05

Status: command-authority implementation decision for the isolated protocol-v2 firmware candidate. This decision does not authorize upload, serial hardware connection, motor energization, or physical measurement.

## Adopted raw acquisition cadence

Adopt the existing v0.5 §4.3 cadence for the 310 protocol-v2 raw acquisition path:

- Scan 1 starts at T.
- Scan 2 starts at T + 25,000 µs.
- The next Scan 1 starts at T + 100,000 µs.
- The pattern repeats with alternating scan-start intervals of 25,000 µs and 75,000 µs.
- Channel order in each scan is A0, A1, A4, A5, A2, A3.
- Each actual conversion retains its own micros() midpoint timestamp and the context token captured immediately before conversion.

The cadence is a deterministic acquisition schedule, not uniform 20 Hz sampling. No Nyquist=10 Hz statement, uniform-sampling assumption, PWM-ripple claim, commutation-transient claim, or peak-current claim is permitted. The resulting records support raw-data collection and later low-frequency stable-window analysis only after explicit settling/window/uncertainty rules are defined.

## Overrun and loss semantics

- At most one slot is serviced per foreground loop pass.
- RX is serviced before each slot; STOP is processed synchronously by the device state machine before reply transmission.
- The RX foreground drain is bounded to 32 bytes per pass; TX service remains bounded to 16 bytes per pass.
- ADC conversion wait is bounded to 2,000 µs. A conversion timeout disables further ADC conversion attempts until reset and records CONVERSION_TIMEOUT; later slots record PRECONDITION_INVALID.
- If a scan has not completed by the next scan boundary, each remaining slot in that scan is recorded as NOT_ACQUIRED; overdue conversions are never replayed in a burst.
- A missed slot has no trustworthy stage snapshot because its scheduled time is in the past; its context token is zero and host mapping must remain unresolved.
- Every scheduled slot, including NOT_ACQUIRED, consumes one device-owned uint64 sample sequence.
- The two six-channel scans form one 12-slot ADC_BATCH. A batch that cannot be retained by the single TX workspace is accounted as loss and leaves the sequence gap visible.

## STATUS loss counter semantics

STATUS reports the full saturating uint32 loss counter and the next uint64 sample sequence. The batch loss snapshot remains the low eight bits. UINT32_MAX is the saturated terminal sentinel; the counter never wraps. Sample flags remain reserved-zero in protocol v2, so no separate saturation bit is added to the wire layout.

## Qualification boundary

This decision and its native/AVR CI evidence are software-only. It does not establish analog settling, current calibration, BOD behavior, EEPROM power-fail behavior, current limiting, direction polarity, physical STOP, sustained physical UART behavior, or host/device hardware interoperability. Those remain explicit qualification gates. HARDWARE_CURRENT_LIMIT_CONFIRMED=false remains unchanged.
