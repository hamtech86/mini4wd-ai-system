# 310-5 host integration decisions and remaining gates — 2026-11-04

## 0. Candidate lineage and firmware identity

- Candidate branch: `safety/310-5-host-integration-candidate`.
- Candidate base: PR #186 HEAD `a7491c8fd7d214e23a6f649d262f978710474d6e`.
- Underlying 310-3 source base: `d9e718b607a873759fffd58fc75bf950af499095`.
- Observed candidate HEAD immediately before this documentation update: `3ea0a508f5d83836c218c8e0d65753dd4c316848`. Re-read the branch ref before integration because this report commit advances it.
- Firmware source reference: legacy `firmware/motor/MotoreRev.ino` at main snapshot `130e453ea3907f071209687a06c3e73535a8952d`, FW 3.03, declared build ID `ARM-STOP-ACK-ACS712-RAIL-20261023-01`.

The firmware reference above is a legacy source identity only. It is **not** identified as the accepted 310-4 concrete implementation, and no HEX/map/size/stack artifact attributable to this candidate was established. No firmware source or build was changed or produced. The candidate branch is not a PR and has no CI run; a single Draft PR must wait until the candidate tests have actually been run on a complete checkout, as required by the upper-command sequence.

## 1. T10/T17 RawLog manifest compatibility — read-only finding

### Verified existing contract

The 310-2 RawLog v2 implementation and its documentation explicitly define the public package as exactly:
- `manifest.json`
- `records.jsonl`

The writer's final package publication allows only those two public files (plus its temporary staging names while publishing). The validator's record type set is fixed to `SESSION_EVENT`, `PWM_STAGE`, `ADC_SAMPLE`, `CALIBRATION`, `EVENT`, and `DERIVED`. The private `.work` and `.recovery` trees are recovery implementation state, not public package extensions.

### Compatibility conclusion

Under the current authorization (no RawLog schema, writer, or validator changes), a third `transport-evidence.jsonl` file cannot be placed inside the RawLog package and claimed as a valid v2 package. Adding a new public record type or a new manifest inventory field would also require a contract decision and is not performed here.

A non-mutating external-sibling concept can be described, but it does **not** satisfy T17's requirement that the RawLog manifest inventory/hash/count the transport Evidence artifact:

- Keep the RawLog package byte-for-byte as the existing two-file package.
- Store transport Evidence in a separate sibling evidence bundle, not inside the RawLog package.
- The sibling bundle would need its own manifest containing the exact `log_id`, `measurement_session_id`, RawLog `manifest.json` SHA-256, RawLog `records.jsonl` SHA-256, Evidence file inventory/hash/count, and a versioned relationship identifier.
- Consumers must treat the two artifacts as separate objects and reject missing, mismatched, or untrusted cross-links. The RawLog package alone must never imply that companion Evidence exists or is valid.

This is only a compatibility proposal. Without a higher-level collection manifest or a separately approved RawLog contract revision, the sibling is not cryptographically inventoried by the RawLog manifest and cannot be represented as a completed T17 package.

### Decision

- Do not add a third file to a RawLog v2 package.
- Do not change `manifest.json`, the writer, validator, or record types.
- Keep L04/T17 **FAIL / unresolved contract mismatch**.
- Request a separate design-authority decision on whether a versioned outer collection manifest is acceptable or whether a future RawLog contract revision is required. Neither option is implemented or assumed.

## 2. T04/T05 production-path integration — protocol boundary

The current `SequenceController` production interface accepts `send_pwm(pwm)` and receives a two-field ACK result `(pwm, ack_utc)`. It does not expose a trustworthy command ID, session identity, full device boot epoch, or stage-context echo in the ACK path. The existing T04/T05 primitives can persist a host intent and compare a full five-field identity, but they cannot manufacture missing device-side identity.

Required integration sequence once the protocol authority supplies the concrete identity contract:
1. Allocate a unique command ID and bind it to the active measurement session, confirmed full device boot ID, and stage context.
2. Durably append and fsync the intent before entering the transport send callback.
3. Record the actual write/flush result, preserving UNKNOWN for partial/uncertain delivery.
4. Accept only an ACK that echoes and exactly matches the full identity tuple.
5. Durably append ACK Evidence before advancing the stage.
6. Keep the independent actuation re-arm gate latched on uncertain delivery, missing/mismatched ACK, Evidence failure, or unknown terminal state.

Until the firmware/wire contract provides a real full boot identity and matching ACK fields, production integration must not substitute a constant, zero, truncated boot ID, PWM-only ACK, or host-generated token as proof of device identity. No firmware or wire change is made in this branch. T04/T05 primitives remain candidate building blocks, not production-path PASS.

## 3. T09/T15 STOP transport — source-level confirmation

The candidate branch source was re-read at the current host-integration candidate ref:

- `measurement_310/transport.py::PySerialTransport.connect()` opens pySerial with a read `timeout`, but does not configure `write_timeout`.
- `PySerialTransport.send()` performs synchronous `write(payload)` followed by `flush()`; it checks for a short write only after flush returns.
- `ProtocolClient.send_stop()` delegates to the same `transport.send()` method used by `send_pwm()`. There is no independent STOP transport, queue, or bounded STOP deadline.
- `SequenceController.abort()` now attempts STOP before RawLog abort logging, but that changes call order only. If the shared write/flush is already blocked, the STOP call can still block behind it.
- `SequenceController._begin_stage()` still calls `send_pwm(index)` before recording a durable command intent. The host-only T04/T05 primitives are not wired into this production path.

Disposition:
- S01 STOP-before-log: limited host ordering improvement retained; not a delivery/physical-stop PASS.
- S02/S03 independent bounded STOP path: **FAIL**.
- T09/T15 hung shared write/flush, unknown partial delivery, and independent STOP behavior: **FAIL / NOT RUN** as applicable.
- No write-timeout, independent transport, firmware STOP latch, driver cutoff, or hardware behavior is implemented or claimed here. These are outside the current change scope and require separate design/authorization.

## 4. T18 host fsync profile — execution plan

The required measurement is host/storage-specific and must be collected on the actual approved host and storage target, not inferred from a cloud or development environment.

Minimum profile:
- At least 10,000 samples per measured operation.
- Separate file-fsync and directory-fsync latency distributions.
- Report p50, p95, p99, p99.9, maximum, sample count, and failures.
- Record OS/kernel, Python version, filesystem type/mount, storage device identity where available, mount options, and test path.
- Report the measured sequence's combined durability budget and compare it against the 10,000ms stage interval after reserving the approved STOP/abort budget.
- Preserve raw sample output and a SHA-256 digest of the report and sample file.

A reusable host-only runner is prepared at `measurement_310/fsync_profile.py`, with percentile helper tests at `tests/test_measurement_310_fsync_profile.py`. It requires at least 10,000 samples and explicit `--stop-reserve-ms` and `--margin-ms` inputs; it writes raw CSV, JSON summary, and SHA-256 sidecars. Existing output names are opened exclusively so prior evidence is not overwritten. Fsync failures are recorded and force a non-passing result.

Host-side development smoke run: 10,000 file-fsync samples and 10,000 directory-fsync samples completed in the isolated execution environment (Python 3.13.5 / Linux 6.18.57 x86_64), with zero reported fsync failures. File fsync p50/p95/p99/p99.9/max = 189,581 / 349,377 / 549,022 / 2,133,141 / 5,551,282 ns; directory fsync = 194,017 / 377,669 / 719,685 / 1,985,888 / 4,678,851 ns; paired sum p50/p95/p99/p99.9/max = 410,907 / 659,986 / 1,182,099 / 2,799,541 / 5,697,528 ns. The smoke run used zero STOP reserve and zero margin solely to exercise the runner; those are **not approved timing values**, so its budget result is not an acceptance result. The local sample SHA-256 was `a29c5d50e9ff5f09b39a2f185714e68c28c480567781d39656f6f88e9c28e678`. This environment is not the approved target host/storage and is not a complete repository checkout. Therefore T18 formal target profile remains **NOT RUN**. A profile from a different host must not be substituted. Run it only on the approved target storage after the reserve and margin values have been authorized, for example:

```bash
python -m measurement_310.fsync_profile --output-dir /path/on/approved/storage --samples 10000 --stage-ms 10000 --stop-reserve-ms APPROVED_VALUE --margin-ms APPROVED_VALUE
```

Replace the two uppercase placeholders with the approved numeric values; do not use invented defaults. Exit code 0 means the measured p99.9 and maximum plus margin are both below the remaining budget and no fsync failures were recorded; exit code 2 means the profile did not meet that condition.

## 5. Isolated host test execution — 2026-11-04

A host-only isolated test harness was assembled from the candidate source/test files fetched through the GitHub repository API. The harness did not require serial devices and did not open hardware ports.

Environment:
- Python 3.13.5
- pytest 9.0.2
- Linux 6.18.57 x86_64 (glibc 2.41)

Exact test command:
```bash
python -m pytest -q \
  tests/test_measurement_310_rearm_gate.py \
  tests/test_measurement_310_fsync_profile.py \
  tests/test_measurement_310_command_intent.py \
  tests/test_measurement_310_evidence_gate.py \
  tests/test_measurement_310_loss_accounting.py \
  tests/test_measurement_310_sequence_accounting.py \
  tests/test_measurement_310_epoch_checkpoint.py \
  tests/test_measurement_310_session_tag_allocator.py
```

Result: **125 passed, 0 failed in 0.41s**.

The test set covers R01 re-arm gate, T18 percentile helpers, T04 durable intent and ACK correlation, T05 evidence gate, T11 loss accounting, uint16 sequence accounting, full-width boot-epoch checkpointing, and T01 session-tag allocation.

Corrections made after execution exposed test-fixture defects:
- R01 short-write test now matches a newline byte, not a literal backslash+n.
- Sequence half-range test now expects accepted delta 32767 to advance the tracker, while ambiguous/stale deltas do not.
- Session-tag allocator fixtures now explicitly provide trusted `initial_high_water=0` when creating a new journal; the dedicated missing-high-water test remains unchanged and must fail closed.
- Durable intent journal now rejects command ID reuse found in persisted history, including after construction of a new journal object.

**Scope limitation:** This was an isolated host harness, not a complete repository checkout. It does not validate the repository's complete package initializer/import graph, all 310 tests, RawLog v2 integration, production SequenceController/ProtocolClient integration, or the full project suite. It is not a CI run and does not change formal T01–T18 acceptance status. No CI was triggered.

## 6. Verification and acceptance boundary

- The R01 source and tests are on the independent host-integration candidate branch.
- R01 isolated host regression: 25/25 passed after fixing the test sentinel; complete repository regression remains NOT RUN.
- T18 helper tests: 3/3 passed in the same isolated harness; development-only 10,000-sample smoke run completed, but formal approved-host profile remains NOT RUN.
- T04/T05 production integration remains blocked by missing concrete ACK/device-epoch identity.
- T10/T17 remains FAIL pending a design-authority decision; no RawLog mutation was made.
- T18 remains NOT RUN pending a 10,000-sample profile on the approved host/storage.
- No CI dispatch, PR merge, firmware modification, RawLog schema/writer/validator change, hardware operation, or stage transition was performed.
- Formal T01–T18 PASS remains 0. R01 remains FAIL. 310-5 acceptance remains pending.
