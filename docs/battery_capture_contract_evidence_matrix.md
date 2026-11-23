# Battery GL-04 Capture Contract Evidence Matrix

Date: 2026-11-23
Scope: Battery 5A / CH1 / CH2. Evidence inventory only; no firmware, DB schema, physical test, or merge authorization.

## Evidence baseline
- Spec: `docs/battery_benchmark_spec_v2.md`, main blob `cafca0ba66d582d0c8679a5610cc8de71626283e`.
- Firmware: `hamtech86/mini4wdprototype/2ch5Abattery/2ch5Abattery.ino`, main blob `5c9cd31ce5c187ab437e92b2cab5b523418fd620`.
- Host serial: `battery_system/serial.py`, blob `f5113138143cb0698364240d69ef7ee23a37ac3d`.
- Standalone parser: `measurement/battery_measurement_parser.py`, blob `0d01febf9fc1828f16cb45422978df9eed709f7e`; tests `tests/test_battery_measurement_parser.py`, blob `772b98b1a3e123be2b8dd50c047de46409bbb9e3`. Production integration was not found; parser sets non-selected channel columns to 0.0 and uses channel in instance_id, so it is not treated as persisted contract.
- RawLog: `raw_log_library/manager.py`, blob `4af6a4fc85b6de91b320494afab1884e2a4a3ac2`; Anonymous Mode tests `tests/test_anonymous_mode.py`, blob `54095ee50b33c1079556308287a43a1722ee3304`.
- Remediation branch: `fix/battery-ch1-ch2-independent-analysis-20261122`; PR #218.

## Evidence matrix

| # | Area | Defined by spec/FW | Code implementation | Automated tests | Physical verification | UNKNOWN / NOT_DEFINED |
|---|---|---|---|---|---|---|
| 1 | Capture start/end, STOP, ERROR, CANCEL, interruption | FW commands START1/2/ALL and STOP1/2/ALL with ACK. States RUN, COMPLETE (voltage cutoff), TIMEOUT, STOP. INA init failure emits ERROR,INA3221. | Host transport sends start/stop and parses DATA. No Measurement Envelope CaptureStarted/CaptureEnded journal. Current FW emits state in DATA, not STATUS. | Parser tests cover CH1/CH2 DATA and malformed frames. Anonymous tests cover COMPLETE and disconnect-incomplete. No complete ACK/ERROR event journal test. | Standalone Serial/UI basic check is recorded in BATTERY_SYSTEM_STATUS.md; not 5A E2E. | CANCEL/INTERRUPTED FW events not found. ACK-to-Capture linkage undefined. TIMEOUT terminal mapping not established. ERROR/ACK/INFO RawLog preservation incomplete. |
| 2 | COMPLETE eligibility, samples, gaps, duplicates, order | Spec v2 lists start/end voltage, avg/max V/I/P, duration, drop, capacity, energy, count; only COMPLETE sessions eligible. FW COMPLETE means voltage <= cutoff; TIMEOUT is separate. | UI uses terminal state/sample presence for registration; exact validity and required-record contract incomplete. PR #218 now rejects selected-channel zero as UNKNOWN. | Unit/parser tests exist. No authoritative fixture for minimum sample count, duplicate handling, monotonicity, gap tolerance, or start/end validity. | Real 5A RawLog -> Measurement -> Benchmark Result E2E NOT RUN. | Minimum count, required record set, missing/duplicate/out-of-order handling, valid start/end rule NOT_DEFINED. |
| 3 | RawLog bytes, framing, schema, IDs, hash | FW DATA is a 10-field CSV line: DATA, model, CH, elapsed_ms, current_A, voltage_V, reserved, PWM, reserved, state; 57600 baud. | BatterySerial decodes bytes as UTF-8 with replacement. RawLog manager stores decoded text as UTF-8 .log with newline preservation. Metadata has log_id/channel/session metadata. | Serial test checks CRLF text preservation; Anonymous tests check saved text and retry. No byte-for-byte binary roundtrip/hash test. | No physical source-vs-captured byte/hash comparison. | Battery RawLog schema version and byte contract NOT_DEFINED. SHA-256/body hash, MeasurementID/RawLogObjectID/SampleReference links not implemented in current Battery capture path. |
| 4 | Timestamp, sequence, wrap | FW elapsed is millis()-channel.startTime, integer milliseconds. Each CH gets its own startTime; STARTALL calls startChannel twice sequentially. | Host parser converts elapsed_ms to seconds. Host UI start time is local wall clock to seconds. | Parser tests check elapsed conversion. No sequence/monotonicity/wrap/host-clock correlation tests found. | No physical timing accuracy or CH start skew measurement in this evidence set. | Sequence number absent; duplicate detection, millis wrap, UTC/timezone, clock error, exact start timestamp relation NOT_DEFINED. |
| 5 | CH1/CH2 identity and Scope | FW DATA carries CH1/CH2. STARTALL is two independent starts, not an ALL Measurement. | BatterySerial returns channel. Anonymous RawLog metadata stores channel and creates separate logs. Existing DB schema lacks Scope Key; PR #218 requires explicit Scope Key and fails closed without it. | Parser tests cover both CH identities; Anonymous tests assert separate CH1/CH2 RawLogs. | Standalone UI basic check only; no end-to-end DB Scope persistence check. | DB field mapping is documented by DB response, but Battery full Owner capture integration is incomplete. Notes/column names are not identity evidence. |
| 6 | Partial capture, communication loss, save failure, retry | FW STOP/TIMEOUT exist; full retry protocol not defined by FW. | Anonymous Mode stores per-CH capture and labels disconnect DISCONNECTED_INCOMPLETE; local save failure retryable. Normal DB path lacks equivalent raw evidence and idempotency link. | Anonymous tests cover disconnect-incomplete, separate CH logs, save retry, anonymous startup. No full malformed/duplicate/out-of-order journal suite. | No physical comm-loss/reconnect/DB-failure test in this matrix. | ACK/INFO/ERROR preservation, DB retry/idempotency, frame replay/duplicate semantics, partial-to-complete promotion NOT_DEFINED. |
| 7 | Outcome vs Session Lifecycle / Aggregate eligibility | CC-01 separates Session Lifecycle from Measurement Outcome. Battery spec "COMPLETE sessions" means Measurement Outcome=COMPLETE, not Session Lifecycle=CLOSED. | Legacy Battery UI/DB still stores/reads Session result/status COMPLETE; distinct Battery Outcome envelope and formal Aggregate gate not fully integrated. PR #218 blocks unknown Scope/selected-zero validity at local result registration. | Manual registration helper checks COMPLETE + quality/operator confirmation; no end-to-end CC-01 Outcome mapping test. | E2E NOT RUN. | Battery mapping STOP/TIMEOUT/ERROR/disconnect/partial to Outcome, required COMPLETE evidence, and Current Aggregate acceptance NOT_DEFINED. Unknown validity stays opaque/excluded. |

## Selected-channel 0.0 decision

**UNKNOWN validity; 0.0 is not an established inactive sentinel.**

Evidence:
- Firmware `readCurrent()` computes `fabs(shuntVoltage) / SHUNT_RESISTOR`, then sets current to `0.0f` whenever it is below `0.01f`. A DATA current of 0.0 can therefore represent a below-threshold reading. There is no separate sentinel flag.
- Firmware voltage is calculated from ADC average and VREF; no explicit voltage-zero sentinel contract was found.
- DATA carries channel and state but no per-field validity bit.
- The separate parser writes 0.0 into non-selected channel columns, but it is not confirmed as the production BatteryTab capture/persistence path. Its synthetic non-selected zero must not be conflated with selected-channel raw zero.

Required handling:
1. Preserve the original RawLog / Raw Measurement row unchanged.
2. If the explicitly selected CH has voltage==0.0 or current==0.0, set Validity=UNKNOWN and reject the derived Benchmark from COMPLETE evidence / Current Aggregate. Do not silently drop that sample and calculate an apparently complete result.
3. A zero in the non-selected CH does not invalidate the selected CH.
4. Do not invent numeric physical ranges or replacement thresholds.

## PR #218 change

The previous branch silently filtered selected-channel zero values from derived samples. This has been replaced with fail-closed UNKNOWN handling in:
- `analysis/battery_benchmark.py`
- `analysis/battery_benchmark_session.py`
- `ui/battery_database_ui.py`

Regression tests cover selected-channel zero voltage/current, non-selected-channel zero isolation, and the legacy extractor. Exact-head CI for the matrix commit `ac6db58afe19ea70982e6ceac3869ec9462ea44a` passed:
- Break-in and Battery Tests run #1931 (`45207546430`): all four jobs SUCCESS, including Battery tests, RawLog/sequence, Break-in, and full pytest suite.
- DB Path Safety Phase 2 run #660 (`45207546113`): isolated DB integration and full repository pytest suite SUCCESS.

This verifies automated software tests only; physical 5A E2E remains NOT RUN.

## Gate classification

- CH1/CH2 independence and no cross-channel averaging: DECIDED; do not reopen.
- Selected-channel 0.0 validity: UNKNOWN / NOT_DEFINED; B — IMPLEMENTATION_VERIFICATION; no design-review stop.
- Full Capture Contract: DOCUMENT PARTIAL; IMPLEMENTATION PARTIAL; real 5A E2E VERIFICATION NOT RUN; APPROVAL PENDING.
- DB GL-04 field mapping: already answered; no re-query.
- Physical 5A E2E / discharge: separate gate, NOT RUN, requires separate explicit authorization.
- No firmware, DB schema, migration, main, merge, or physical measurement changes in this branch.
