# 310-5 Same-UART Priority STOP Candidate (2026-11-11)

## Purpose and scope

This change provides a software-only STOP transmission path for the existing single motor UART (/dev/ttyACM0). It removes the requirement for a second physical serial endpoint when the selected transport implements its own single-writer priority STOP operation.

It does not modify the Arduino, wiring, L298N, power supply, sensors, or other hardware. /dev/ttyUSB0 remains the separate battery-discharge FTDI endpoint and is not used for motor STOP.

## Host transport behavior

Normal ARM/PWM/DISARM and priority STOP share one serialized serial.write() owner.

- PySerialTransport.send() checks the permanent STOP inhibit, serializes only the short write() operation, and performs its flush wait outside the write lock.
- send_stop_priority() latches the host-side STOP inhibit before starting its worker. It can therefore write while a normal sender is waiting for flush(), without a second concurrent writer or frame interleaving.
- STOP is written as a leading COBS delimiter followed by the complete STOP frame. A delimiter after a complete frame is ignored; after a partial frame it terminates/discards that incomplete frame. STOP bytes are never spliced into a preceding frame.
- Normal writes that have not entered serial.write() are rejected after STOP is requested. A normal write already in progress is allowed to reach its bounded write boundary; STOP then takes the write lock.
- The caller waits no longer than stop_timeout_s for the priority STOP worker. A timeout, short write, serial exception, or unresolved write is UNKNOWN, never success.
- No RawLog append/fsync, ADC evidence flush, or normal-command queue is performed before the priority STOP write attempt. STOP evidence is appended best-effort afterward by the session layer.
- The STOP inhibit remains set for the lifetime of the transport. Reconnection or a new measurement requires a newly constructed transport/session and existing recovery/re-arm gates; this method does not auto-resume.

## Timing interpretation

At 57600 baud, 8N1, one wire byte takes approximately 173.6 microseconds. A maximum V2 wire frame of 188 bytes is approximately 32.64 ms; a STOP_REQ frame is approximately 36 bytes / 6.25 ms. These are serialization estimates only.

The implementation bounds the host caller's wait, but does not establish a hard physical STOP latency. OS/USB buffering, scheduler latency, UART faults, a wedged driver, firmware loop scheduling, and physical driver/motor response remain outside this host-only evidence.

## Acceptance evidence to collect

- Host unit tests: priority STOP can be written while normal flush is blocked; ordinary and STOP frames are serialized, not interleaved; normal TX is permanently rejected after STOP; same-UART production factory binding succeeds only for transports exposing the priority method; absent priority method and absent independent endpoint remains rejected.
- Existing protocol-v2 regression suite and full project regression suite.
- Target-host regression for the production transport path where practical, without connecting to or energizing the motor device.
- Physical STOP response, PWM=0, direction LOW at the pins, motor current cessation, and no-auto-resume remain NOT RUN / NOT PROVEN absent separate explicit hardware authorization and physical test.

## Residual failure handling

If the UART/USB/host path is disconnected, wedged, or reports a timeout, STOP delivery is UNKNOWN. The operator response remains: keep the L298N 12V driver supply OFF, do not resume or re-arm, and follow the established recovery procedure. This same-UART design is not an independent electrical cutoff.

HARDWARE_CURRENT_LIMIT_CONFIRMED=false remains unchanged. No hardware action is authorized by this document.
