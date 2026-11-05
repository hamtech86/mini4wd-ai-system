# 310-5 T18 production append-path profile — review plan

Date: 2026-11-06  
Candidate: PR #190 / `integration/310-5-unified-candidate`

## Why the synthetic fsync PASS is not end-to-end T18

The accepted `310-5-T18-fsync-v1` run qualifies only isolated host filesystem fsync latency. Source inspection shows the production persistence path performs more work per ADC sample:

1. `SequenceController.tick()` iterates each sample returned from an ADC_BATCH and calls `record_adc_sample()`.
2. `record_adc_sample()` creates one ADC_SAMPLE record and calls the controller's RawLog append path.
3. `RawLogV2Session.append()` appends and fsyncs `records.jsonl`.
4. The same append then calls `_atomic_replace_json(work_state.json)`, which fsyncs a temporary state file, replaces the state file, and fsyncs the work directory.

Therefore, each ADC_SAMPLE append currently includes two file fsyncs and one directory fsync, plus serialization, open/close, replace and directory metadata work.

The adopted ADC cadence is 12 slots per ADC_BATCH and 100 batches per 10-second stage (two six-channel scans per 100 ms). This corresponds to 1,200 ADC_SAMPLE records per full 10-second stage. The host processes the 12 samples sequentially.

The protocol Evidence path adds durable hash-chained appends for RX_BYTES, FRAME_RX_DECODED and ADC_BATCH_ACCEPTED per batch, plus periodic loss-window summaries and stage-context events. `TransportEvidenceJournal.append()` fsyncs each event.

The synthetic fsync profile's p50 values (file 44.087744 ms; directory 22.068950 ms) make this production workload a significant throughput risk, but they are not a substitute for measuring the actual writer path. No production-path FAIL is claimed until that measurement is run.

## Added production-path benchmark

`measurement_310/rawlog_stage_profile.py` measures:
- At least 10,000 actual `RawLogV2Session.append()` calls using ADC_SAMPLE-shaped records.
- The actual `TransportEvidenceJournal.append()` code path with three synthetic Evidence events per 12-sample ADC_BATCH, plus periodic loss summaries and stage-context events.
- Per-sample RawLog append latency, Evidence append latency, total 12-sample batch latency, and full 1,200-sample stage-group latency.
- The strict 10,000 ms stage budget, 1,000 ms STOP reserve and 1,000 ms additional margin. A full stage group must finish in less than 8,000 ms after reserving both.
- Progress output every ten batches. It writes uniquely named CSV/JSON/SHA-256 artifacts to the selected existing target-storage directory.

Default run: 10,008 sample commits (834 complete 12-sample batches), producing eight full 1,200-sample stage groups plus a 408-sample partial group.

The benchmark uses the real RawLog and Evidence append implementations but synthetic ADC_BATCH contents. It does not open serial ports or hardware.

## Remaining limits after this benchmark

The script does not include final RawLog package publication/finalization, crash recovery, target-host backup/restore, or injected power-loss failures. Those remain separate T18 evidence requirements. A passing append benchmark would not by itself complete T18.

No Arduino upload, physical serial connection, motor energization, EEPROM/fuse operation, or physical test is authorized. `HARDWARE_CURRENT_LIMIT_CONFIRMED=false` remains unchanged.
