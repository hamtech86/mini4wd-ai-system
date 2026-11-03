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

## Status

T01–T18 formal acceptance remains unchanged: 0 PASS. This ledger does not authorize 310-6.
