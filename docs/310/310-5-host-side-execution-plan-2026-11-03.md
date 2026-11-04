# 310-5 Host-side execution plan (candidate only)

Date: 2026-11-03
Candidate branch: `safety/310-5-host-integration-candidate`
Starting HEAD: `a7491c8fd7d214e23a6f649d262f978710474d6e`
Authority: upper-command decision comment `6602410842`

This is an execution ledger, not a specification amendment, acceptance record, or hardware authorization.

## Guardrails

- Host-side implementation and deterministic host/simulator tests only.
- No firmware, RawLog schema/type, workflow, Issue #35, or accepted 310-4 document changes.
- No PR merge, CI dispatch, energized hardware, EEPROM power interruption, fuse/ISP operation, ADC reference measurement, motor operation, or 310-second measurement.
- Tests not executed and source-only findings remain NOT RUN.
- STOP transmission attempt is not proof of MCU output-off, driver cutoff, or rotor stop.
- Preserve `HARDWARE_CURRENT_LIMIT_CONFIRMED=false`.

## Work sequence and exit evidence

| Work item | Host-side scope | Required evidence before status can advance |
|---|---|---|
| T01 | Session-tag allocator, journal integrity, namespace binding, exhaustion, concurrency and injected crash boundaries | Allocation history; journal bytes and hashes; crash-point matrix; proof that uncertain/rollback state blocks HELLO; duplicate allocation count = 0 |
| T02 | uint16 sequence extension and duplicate/gap classification | Fixtures for 65534, 65535, 0, 1; exact/conflicting duplicates; gaps; deltas 32767/32768; host restart; full-epoch strict ordering; validator output |
| T03 | Full boot_id64 identity and durable checkpoint model | Full identity mapping; low32 collision fixture; checkpoint crash/corruption matrix; proof that session changes do not reset epoch and unknown state is unresolved |
| T04 | Exact ACK correlation by command, context, session and full epoch | Raw RX fixture set; exact-match decision trace; wrong-field and stale-frame rejection; no stage advance without matching durable ACK |
| T05 | Durable intent before any nonzero command write | Injected intent fsync failure proves zero command bytes; write/partial/error records; completion and recovery hashes; original evidence preservation |
| T09/T15 | Host/simulator STOP arbitration independent of writer queue, TX drain, fsync and ADC batch | Deterministic congestion/failure traces; STOP scheduling/order; no invented latency limit; physical cutoff remains unproven |
| T10/T17 | Read-only manifest contract compatibility investigation; no schema change | Exact validator/writer code references; manifest inventory/hash/count capability result; sibling compatibility decision; loss-accounting fixtures |
| T11 | Per-channel, epoch-local, half-open-window loss accounting | Expected/attempted/valid/invalid/missing counts; wrap/gap/drop/unattributable cases; append-only corrections; deterministic totals |
| T18 | Host benchmark harness and at least 10,000 commits | Exact host/OS/filesystem/mount/storage/runtime profile; per-operation mean/max/p50/p95/p99/p99.9; injected failures; stage budget and STOP reserve analysis; byte-identical backup restore |

## Current verified baseline

- PR #185 HEAD: `d2be96981673e250ba2cbd7f552f91a27a3016c7`; host-side STOP-before-log ordering and 3 tests.
- PR #186 HEAD: `a7491c8fd7d214e23a6f649d262f978710474d6e`; includes PR #185 history and adds host regression coverage.
- PR #185 CI run `41462228503` and PR #186 CI run `41538695288` succeeded on their respective separate PR HEADs. These are not CI results for this candidate branch and do not establish physical safety.
- Candidate source inspection: `SequenceController._begin_stage` calls `send_pwm(index)`; `ProtocolClient.poll_ack()` yields only (PWM, host receive UTC). Therefore the current ACK cannot be correlated to command ID, session, full boot epoch, or stage context. Do not synthesize these fields or treat PWM equality as exact identity.\n- Candidate source inspection: PySerialTransport send is synchronous write/flush; STOP uses the same transport. No independent/bounded STOP path is established.\n- T04/T05 modules are standalone primitives, not integrated into SequenceController/ProtocolClient production path. Their tests have not been run in this environment.\n- T05 EvidenceGate records intent before its callback, latches on uncertain send/evidence failure, and attempts STOP; this remains host policy behavior, not a physical stop guarantee.

## Initial blockers retained

1. Existing synchronous serial write/flush path is shared by PWM and STOP. No bounded independent STOP path is established.
2. Existing ACK lacks exact command/context/session/full-epoch binding.
3. Durable intent is not yet integrated before production-path nonzero PWM.
4. Existing RawLog v2 final-package contract permits only `manifest.json` and `records.jsonl`; the required Evidence sibling inventory is not represented by the current manifest contract. Compatibility must be solved without changing records schema.
5. No T18 10k+ benchmark evidence or latency distribution exists.\n6. No candidate-local tests have been executed; no formal acceptance can be inferred from authored tests or previous PR CI.

## T11 candidate implementation update (2026-11-03)

- Added `measurement_310/loss_accounting.py`: pure deterministic accounting per channel, full boot epoch, and half-open window; separates valid/invalid attempts, exact duplicates, conflicting duplicates, missing, excess, and unattributable records. Unknown expected count leaves missing as null. Stable JSON and SHA-256 digest are provided.
- Added `tests/test_measurement_310_loss_accounting.py`: coverage authored for expected/missing, invalid, duplicate/conflict, half-open boundary, channel/epoch isolation, unattributable observations, deterministic serialization, and invalid inputs.
- Commits: implementation `4adfbf230484411f11c58bdce4fc08c1fe01f777`; tests `2e4812f0083627f45f4dd32601f933d29402fbbd`.
- Tests have NOT been executed. This is host-only candidate code and does not infer missing records from sequence gaps automatically; upstream attribution and expected-count source remain required. No RawLog schema changed.\n- Follow-up hardening commits `363de0ef77dcd20de8b2a02531dddcc73d6dc492` and `ecdba6bb636431ab9c7c9d332e08a1c051e677a7` validate integer-only expected counts and window bounds, classify malformed observation identity/time fields as unattributable, and add excess/malformed-input boundary fixtures. These tests also remain NOT RUN.

## T09/T15 host STOP-ordering update (2026-11-03)

- Added two regression test cases (one parameterized for STOP success/failure) to `tests/test_measurement_310.py`: STOP callback is invoked before abort evidence append; STOP callback failure still permits best-effort logging and leaves controller FAULT.
- Added `docs/310/310-5-t09-t15-stop-arbitration-fixtures-2026-11-03.md` to state exact coverage and exclusions.
- Test changes commit `0cdc36795d1946b3b619817730f787d064dc52ea`; fixture document commit `8b96752d159c7c69cae2bdbf0375bf1b488978d1`.
- Tests NOT RUN. This does not cover a hung callback, concurrent abort arbitration, queue bypass, independent UART path, or latency bounds. Current STOP/PWM share synchronous transport; physical cutoff remains unproven.

## Status

T01–T18 formal acceptance remains unchanged: 0 PASS. This ledger does not authorize 310-6.


T09/T15 follow-up (2026-11-03): `abort()` now latches re-entrant and sequential calls while STOPPING/ABORTED/FAULT/COMPLETED, avoiding repeated STOP callback and duplicate abort records. Implementation `0fbffdbd9667cba836cd0ddb1b202817d49de0f3`; regression tests `0452902fa573adf09359970147a8884cd8f2d325`; scope note `839a7e5426c8334163b8407f2577df418e78da64`. Tests NOT RUN. This is not thread synchronization; true simultaneous-call arbitration, hung STOP callbacks, independent UART priority, bounded latency, and physical cutoff remain unverified.


T09/T15 concurrency follow-up (2026-11-03): the abort state check and STOPPING
latch are now atomic among Python threads in one process via a non-blocking
lock. The lock is released before STOP callback invocation, preserving safe
same-thread re-entry behavior. Implementation
`43071b42f15b61634e6659d7f990b509de978714`; concurrent caller regression
`e7270ac73c331ac94147d8e21f36a73f4d056539`; scope note
`7c8b1b944bc06b73754cca50b6de86cc0edc36d2`. Tests NOT RUN. This does not
provide UART priority, in-flight PWM cancellation, cross-process arbitration,
or bounded STOP latency.


T09/T15 transport blocking review (2026-11-03): inspected
`measurement_310/transport.py`. PWM and STOP share
`ProtocolClient.transport.send()`; PySerialTransport synchronously performs
`write()` then `flush()`, with read timeout configured but no write timeout.
No priority queue, independent STOP path, or in-flight PWM cancellation exists.
The review artifact is
`docs/310/310-5-t09-t15-transport-blocking-review-2026-11-03.md`
(commit `5f238c83706e3de464469032d016ab638975891e`). No code change was made
because channel topology, STOP-vs-in-flight-PWM policy, and latency bound require
authority-level decisions. Tests NOT RUN; no CI/hardware. T09/T15 remain NOT PASS.


T09/T15 serial failure fixtures (2026-11-03): added fake-pySerial host tests for
write exception with unknown partial progress, short write, flush exception
after write, and successful full write+flush. Test commit
`91ebe8e4d22e527acfd3b266d601e5ae29d95ca4`; fixture note
`5edd9c1adfe7802b34b24b5dc980e6d537598a03`. No real port is opened. A write or
flush exception leaves delivery uncertain; it does not prove STOP was not
received. Tests NOT RUN; no CI/hardware. T09/T15 remain NOT PASS.


T09/T15 ambiguous STOP outcome follow-up (2026-11-03): added a deterministic
host test that connects `SequenceController.abort()` to
`ProtocolClient.send_stop()` with a failing MockTransport. It checks error
propagation, FAULT latching, best-effort abort evidence, explicit
`device_state=unknown`, and absence of automatic retry. Test change commits
`af3967af6f37e968946f40adbfe9ffb5d3e1f840` and
`53656ad4848d7237aab96af95cf2602d6b09616a`; fixture note
`92f785a19e3776fe972b2c2033d6b48bde65ddfa`. This is a host mock only:
an empty mock sent list does not establish whether bytes reached real hardware
in an ambiguous write/flush failure. No retry semantics are selected; firmware
duplicate handling and transport policy remain authority-level questions.
Tests NOT RUN; no CI/hardware. T09/T15 remain NOT PASS.


## T11 verification follow-up (2026-11-04)

- Isolated local reproduction of the fetched candidate T11 implementation and its 17 parameterized test cases initially found one failure: `expected=True` raised `TypeError`, while the existing test contract requires `ValueError` for boolean/negative invalid counts.
- Corrected `_validate_window()` to reject bool explicitly as an invalid sample-count value before the integer type check.
- Fix commit: `8f87b9ea2fb2e5bd761dfa847d3850a3a41a29b4`.
- Re-running the isolated reconstructed T11 suite after the correction: 17 passed. This was not a checkout-based run of the complete repository suite and is not represented as CI evidence.
- Additional cross-window probe found an unresolved accounting contract issue: an observation with missing channel identity is counted as `unattributable=1` in each window that receives the same observation collection. Two channel windows therefore sum to 2 for one physical observation. A record with missing timestamp is likewise counted in every window because it cannot be temporally scoped.
- T11 therefore remains NOT PASS until the caller/API contract guarantees globally unique attribution of unattributable records (or separates global unassignable diagnostics from per-window summaries) and tests cover multiple channels/epochs/windows. Do not sum per-window `unattributable` values without a defined deduplication/ownership rule.


## T11 collection-wide attribution correction (2026-11-04)

- Added `summarize_many(windows, observations)` and `BatchLossSummary`.
- The batch API validates windows, rejects overlap within the same channel/full-epoch pair, attributes each fully identified observation to at most one half-open window, and counts incomplete/malformed identity or timestamp records once in the collection-wide `unattributable` field.
- Per-window summaries produced by the batch API contain zero unattributable records; callers must use the batch-level count and must not sum single-window `summarize()` unattributable counts across repeated collections.
- Implementation commit: `ca35b97d62edebd8eef656f063a7f6ede244e9ed`.
- Regression tests commit: `3c89090c1dfe569c29cbbc8a125e3b4d4ccdf563`.
- Added coverage for missing channel across channels, missing timestamp across windows, attribution by channel/epoch/time, and overlapping-window rejection.
- This closes the identified double-counting path for callers using the batch API. The original single-window API remains intentionally single-window; callers aggregating across windows must migrate to `summarize_many()`.
- Execution of the updated test module is pending; T11 is not yet PASS.


## R01 recovery/re-arm fail-closed correction (2026-11-04)

- Inspection confirmed `SequenceController.startup_recover()` previously treated successful RawLog work-area recovery as sufficient to permit `start()`. This repaired storage state but did not reconcile whether the previous nonzero PWM intent was written, acknowledged, or stopped.
- Changed the controller to latch `_recovery_requires_review` whenever one or more incomplete work items were recovered. `start()` now raises `SequenceError` and sends no PWM until command-outcome reconciliation exists. The latch is fail-closed for the lifetime of this controller instance.
- Added a regression test that creates an interrupted work item, runs successful RawLog recovery, then asserts re-arm raises and the PWM send callback count remains zero.
- Implementation commit: `f1c3fb593c8d7b9909ab0b6aaad0de06bdc9542a`.
- Test commit: `82360713a38107d6d31cd22289d9b6a9d7d068cb`.
- This is a conservative host-side containment correction, not full R01 acceptance: it blocks all re-arm after recovered incomplete work, including cases that might later be proven safe. It does not reconcile intent/write/flush/ACK/terminal evidence, and it does not prove physical PWM=0 or driver cutoff. Test execution remains pending.

## Work accounting and stopping explanation (2026-11-04)

- Scope: 37 original matrix entries plus independent R01 = 38 verification entries.
- Previously reported matrix distribution: 4 limited software-scope PASS candidates (not formal PASS), 11 FAIL, 18 BLOCKED, 4 NOT RUN. R01 independently FAIL. T01-T18 formal PASS remains 0.
- Thus 34 entries are not formally accepted: 12 provisional FAIL including R01, 18 BLOCKED, and 4 NOT RUN. Four limited-scope PASS candidates remain subject to evidence/scope confirmation.
- Corrective actions recorded in this candidate branch: (1) T11 boolean expected-count exception classification; (2) T11 collection-wide attribution API and cross-window duplicate-count prevention; (3) R01 recovered-incomplete-work re-arm inhibition. These are three concrete corrective changes, affecting two verification entries (T11 and R01). They are not counted as formal PASS because the updated repository tests have not been run and remaining T11/R01 acceptance conditions are broader.
- No full repository checkout or CI run was available in this work session. GitHub Actions dispatch, merge, and all hardware operations remain prohibited. Tests must not be described as executed merely because test code was added.
- Prior premature stopping was a process error: work was reported after a bounded subtask/commit instead of continuing through the remaining authorized host-side scope. It was not caused by a new technical blocker or by a need for another user instruction. Continue the remaining host-side implementation, tests, and documentation in the current authorization; stop only at an actual authority/safety boundary or when the authorized scope is exhausted.


## T04 ACK identity validation follow-up (2026-11-04)

- Adversarial source review found that `AckIdentity` had no runtime validation. Python considers `True == 1`; therefore a malformed ACK with `boot_id64=True` could compare equal to a trusted command epoch of 1 and pass the equality-only correlator.
- Added independent validation of every ACK identity string and the full uint64 epoch, explicitly rejecting bool, negative, overflow, float, and non-integer epoch values. `AckCorrelator.correlate()` now rejects non-`AckIdentity` objects without consuming pending identity; `register()` rejects non-`CommandIdentity` objects.
- Implementation commit: `33a08033f27d9534db68242415aae62b42485e9b`.
- Added malformed-field and non-object regression tests: `eacca44ed9a577043db3bfa820051ceac388d893`.
- This hardens the standalone host correlator only. It does not integrate the correlator with the current production protocol, whose ACK still contains only PWM and host receive time. T04 remains NOT PASS; tests are not yet executed.

## R01 restart-persistence follow-up (2026-11-04)

- Adversarial restart review found a bypass in the earlier in-memory latch: after process A recovered and removed a pending `.work` area, process B could see no pending work, construct a fresh controller with an empty latch, and re-arm.
- Added a durable host-side marker `.310-rearm-inhibited` under the RawLog root. When pending work is discovered, the marker is created and file/directory fsynced BEFORE RawLog recovery can remove the work area. Any later controller process sees the marker and remains inhibited. Symlinks/non-regular marker paths fail closed.
- Implementation commit: `17b7f8df1fdd5fa4f9a5920bf62f9e7515cd63dc`.
- Added a two-controller restart regression test proving that a second controller cannot send PWM after the first has recovered the incomplete work: `0521209a5a50c9d6ac264b6e09b761d7d8b8e47e`.
- The marker is intentionally not auto-cleared. A safe reconciliation/clear protocol does not yet exist; manual deletion would defeat the inhibit and is not authorized as an automatic action. This is conservative containment, not full R01 acceptance. The new test has not been executed.

## Updated work accounting (2026-11-04)

- Additional corrective actions since the previous ledger entry: ACK identity runtime validation (T04) and persistent re-arm inhibition across process restarts (R01).
- Total concrete corrective actions now recorded: five (two T11 accounting corrections, two R01 recovery/re-arm corrections, one T04 ACK-validation correction), affecting three verification entries: T04, T11, R01.
- These are implementation changes, not formal verification passes. Updated repository tests remain unexecuted in this environment; no full checkout, CI run, or hardware test is claimed.
