# 310-5 T18 production-path verification gap — 2026-11-06

Candidate: PR #190 / `integration/310-5-unified-candidate`

## Current evidence boundary

The accepted `310-5-T18-fsync-v1` run is a limited PASS for the synthetic target-host filesystem workload only. It is not a measurement of the 310 production sequence.

The current `measurement_310/rawlog_stage_profile.py` is deliberately scoped as a RawLog append microbenchmark. It invokes the real `RawLogV2Session.append()` and `TransportEvidenceJournal.append()` implementations with synthetic records. It does not execute the production host orchestration path.

In particular, it does not execute:

1. `ProtocolV2HostSession` handshake, RX framing, ACK correlation, or ADC_BATCH acceptance.
2. `DeviceLossWindowAccumulator` production accounting.
3. `SequenceController.tick()` and `record_adc_sample()`.
4. The 31 real stage transitions, stage DISARM/ARM handling, or 10,000 ms stage deadlines.
5. `SequenceController._finish_stage()`, `_complete()`, RawLog package publication, or Evidence companion-manifest finalization.

The microbenchmark report therefore sets `stage_budget_assessed=false` and `t18_end_to_end_pass=false`. Its synthetic timestamps and batch groupings are not evidence of device cadence or stage timing.

## Production persistence cost to measure

Source inspection shows that each `SequenceController.record_adc_sample()` calls the RawLog append path. `RawLogV2Session.append()` persists the record and updates `work_state.json` through the atomic replacement path. The protocol session separately persists transport Evidence events.

The end-to-end profile must time the actual production calls and include:
- Protocol v2 frame receipt, decode, session/epoch validation and ADC_BATCH acceptance.
- Device sequence and loss-window accounting.
- Every ADC_SAMPLE append through `SequenceController.record_adc_sample()`.
- Evidence journal appends associated with the accepted batches.
- All 31 stage transitions and stage completion records.
- RawLog finalization and Evidence companion-manifest finalization.

Use an injected deterministic clock and in-memory protocol transport to avoid physical hardware and avoid waiting 310 wall-clock seconds. The storage and Evidence writes must remain real writes on the selected target filesystem; do not replace them with mocks. Advance the injected clock only to model the specified stage boundaries, while measuring actual host execution time with a monotonic performance clock.

## Required acceptance criteria for a future production-path profile

- At least one complete 31-stage sequence with 1,200 ADC slots per 10-second stage, using the accepted Protocol v2 channel order and production loss accounting.
- Every accepted slot must traverse the actual host protocol session, sequence controller and RawLog append path. Any dropped, duplicated, reordered or unresolved slot must be accounted for, not silently synthesized away.
- Actual Evidence events must be emitted through the production journal.
- Stage timing must include all work performed within each stage, including storage and evidence writes; no assumed 100 ms batch cadence may substitute for measured execution.
- Every stage's measured persistence workload must complete within the 8,000 ms processing allowance (10,000 ms stage minus 1,000 ms STOP reserve and 1,000 ms margin).
- Final RawLog publication and Evidence companion-manifest finalization must complete and verify successfully.
- Report per-stage and aggregate p50/p95/p99/p99.9/max, failures, counts, and artifact hashes.
- Run on the approved target host/storage. The earlier synthetic fsync profile is not interchangeable with this profile.

## Current status

- Target-host synthetic filesystem fsync profile: limited PASS only.
- RawLog append microbenchmark: software microbenchmark only; no stage-budget result.
- Full production-path harness: implemented; hosted-runner and approved target-host profile results are still pending final verification.
- T18 end-to-end acceptance: BLOCKED pending production-path profile and the remaining separately required recovery/backup evidence.
- Physical safety qualification: NOT RUN. No Arduino upload, serial hardware connection, motor energization, EEPROM/fuse operation, or physical test is authorized. `HARDWARE_CURRENT_LIMIT_CONFIRMED=false` remains unchanged.
