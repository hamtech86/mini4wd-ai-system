# 310-5 Host-side execution classification — 2026-11-02

## Purpose and authority

This note classifies software-only checks by whether they can be run without hardware, whether current code supports them, and what remains needed. It is an interim execution record, not a 310-5 completion application or a stage transition request.

No firmware or RawLog v2 schema change is authorized here. No PR merge or hardware operation is authorized.

## Host-side test classes

| Class | Presently runnable without hardware | Current status / evidence | Remaining need |
|---|---|---|---|
| Python sequence / protocol regressions | Yes, in CI using pytest and MockTransport | Draft PR #186; corrected HEAD `bfd673e9e5f89327aa3c6d06d324d482789aeb69`; Actions run `41536899145`: all four jobs success; full suite 324 passed | Extend cases only where behavior is supported by current API; late/stale ACK and reconnect/session binding still require explicit review |
| ACK timeout/mismatch, fragmented/coalesced frames, timestamp ordering | Yes, existing Python tests | Existing test source covers representative paths | Additional cases for late/duplicate ACK and command/session/epoch binding are not yet demonstrated |
| Transport write/flush error and STOP send failure | Mock-based tests can run | New STOP send-failure test added in PR #186 | pySerial physical behavior and timeout bounds remain unproven; configured write_timeout absent in reviewed source |
| Durable pre-send TX intent | Not as a passing test with current implementation | FAIL retained: no durable intent is written/fsynced before nonzero PWM send | Implementation and acceptance criteria decision needed; do not alter RawLog v2 schema by assumption |
| fsync failure/crash/latency distribution | Failure injection is host-testable, but not all paths currently present | NOT RUN in this execution; no measured latency distribution | Add controlled writer/fsync injection tests and repeatable timing harness; production filesystem latency evidence remains environment-specific |
| RawLog v2 artifact validation / recovery | Host-side tests possible | Existing package/recovery tests present; cross-artifact Evidence manifest consistency unresolved | Define the companion Evidence/package relationship with design authority; no schema invention |
| SRAM, stack, RX/TX ownership, ADC acquisition quality | Not established by Python tests | BLOCKED / NOT RUN | Exact MCU and board revision, firmware build setup, map/stack evidence, ownership contract, ADC reference/front-end and error contract; separate approval for hardware |
| Hardware STOP / energization / 310-second measurement | No | BLOCKED; not run | Explicit upper-command approval plus complete HW01–HW08 safety inputs and current-limit confirmation |

## New host-side regressions

Draft PR: https://github.com/hamtech86/mini4wd-ai-system/pull/186

Target test commit: `aba9b5a93110e0a5e6ae7ea172476f6c731f5c6e`

The added tests cover malformed ACK domain values, invalid codec consumed-byte counts, receive transport failure, STOP-send failure, and clearing buffered/pending protocol state on disconnect. They use in-memory transport and do not claim physical behavior.

## Execution record

- GitHub Actions workflow run `41536899145` on HEAD `bfd673e9e5f89327aa3c6d06d324d482789aeb69`: all four jobs completed successfully.
- `test-full-suite`: `python -m pytest -q --ignore=serial_command_test.py --ignore=serial_test.py tests/test_breakin_controller.py tests/test_anomaly_skip.py tests/test_recipe_engine.py` — **324 passed in 9.45s**.
- `test-raw-log-and-sequence`: `python -m pytest -q tests/test_raw_log_library.py tests/test_raw_log_v2.py tests/test_local_raw_log_breakin_controller.py tests/test_sequence_executor.py` — **38 passed in 0.34s**.
- `test-breakin`: `python -m pytest -q --ignore=serial_command_test.py --ignore=serial_test.py tests/test_breakin_controller.py tests/test_anomaly_skip.py tests/test_recipe_engine.py` — **19 passed in 0.67s**.
- `test-battery`: `python -m pytest -q tests/test_battery_measurement_parser.py tests/test_battery_benchmark.py tests/test_battery_benchmark_service.py tests/test_battery_repository.py` — **9 passed in 0.07s**.
- Note: the full-suite command is the workflow's configured command; it includes the new `tests/test_measurement_310_safety_regressions.py` via repository-wide discovery. The focused workflow jobs use explicit subsets.
- The initial run `41536236339` failed only because a new test expected the wrong MockTransport exception text; test assertion was corrected without product-code changes, then run `41536899145` passed.
- Local pytest/native firmware harness: NOT RUN in this record.
- Local pytest/native firmware harness: NOT RUN in this record.
- Hardware tests: BLOCKED / NOT RUN; no energization, Fuse operation, EEPROM interruption, ADC injection, or 310-second measurement.

## Preserved independent findings

- STOP request/attempt through the shared synchronous pySerial write/flush path is not an independent TX route; bounded latency remains unproven.
- Durable pre-send TX intent remains FAIL.
- fsync fault injection and latency distribution remain outstanding.
- RawLog / transport Evidence artifact and manifest alignment remains unresolved.
- SRAM/buffer ownership and firmware ADC acquisition quality remain unsupported by current Python-only evidence.
