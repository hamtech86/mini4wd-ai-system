# 310-5 T18 host filesystem fsync profile — limited acceptance record

Date: 2026-11-06  
Authority: 310 process upper-command review  
Candidate PR: #190  
Candidate branch: `integration/310-5-unified-candidate`  
Candidate HEAD at review start: `9c126b890d637a32d964695c0b8a3fbf461376de`

## Decision

**PASS — limited to the T18 synthetic host-filesystem fsync profile on the recorded Linux host and storage.**

This is not a PASS for the complete T18 end-to-end save pipeline, 310-5, or any physical safety requirement. The measurement does not qualify actual RawLog record/manifest publication, production workload equivalence, power-loss persistence, STOP-path independence, MCU/driver behavior, or hardware operation.

## Measurement identity

- Profile: `310-5-T18-fsync-v1`
- Samples: 10,000
- File fsync samples: 10,000
- Directory fsync samples: 10,000
- Paired file + directory samples: 10,000
- Stage budget: 10,000 ms
- STOP reserve: 1,000 ms
- Additional margin: 1,000 ms
- Available profile budget: 9,000,000,000 ns
- Script exit code: `0`
- Wall time: 14m44.746s
- File and directory fsync failures: 0
- `budget.profile_within_budget`: `true`

## Host and storage

- System: Linux x86_64
- Kernel: `5.15.0-190-generic`
- Python: `3.10.12`
- Target path: `/home/hamui/mini4wd-ai-system/artifacts/310-t18-run`
- Device: `/dev/sda3`
- Filesystem: `ext4`
- Mount point: `/`
- Mount options: `rw,relatime,errors=remount-ro`
- `st_dev`: `2051`

## Measured latency distribution

All values below are milliseconds.

| Distribution | p50 | p95 | p99 | p99.9 | Maximum |
|---|---:|---:|---:|---:|---:|
| File fsync | 44.087744 | 44.182545 | 56.513235 | 161.813288 | 220.194866 |
| Directory fsync | 22.068950 | 22.605251 | 44.245682 | 217.663550 | 651.174569 |
| Paired sum | 66.155738 | 72.162060 | 110.172843 | 261.742767 | 684.258623 |

The paired p99.9 plus the 1,000 ms margin is 1,261.742767 ms. The paired maximum plus the 1,000 ms margin is 1,684.258623 ms. Both are strictly below the 9,000 ms available budget.

No file or directory fsync failures were recorded.

## Artifact integrity checks

Artifacts retained on the target host in:

`~/mini4wd-ai-system/artifacts/310-t18-run/`

- `310-fsync-report.json`
- `310-fsync-report.sha256`
- `310-fsync-samples.csv`

Checks observed:
- CSV has 10,001 lines (header plus 10,000 samples).
- CSV SHA-256: `1a0891adc4d68905d30ac190f833bb94244cc031c061c3fdd4ff47e8bfaaa420`.
- CSV SHA-256 exactly matches `samples_sha256` in the JSON report.
- `sha256sum -c 310-fsync-report.sha256` returned `310-fsync-report.json: OK`.
- JSON reports 10,000 file, directory, and paired samples; both failure counts are zero; profile budget result is true.

## Qualification boundary

This is a synthetic host-filesystem benchmark on the identified local ext4 storage. The benchmark's paired sum is a profile estimate, not a guarantee for a different journal or production RawLog workload. The 14m44.746s wall time is the duration of this 10,000-sample benchmark; it is not a claim that a 10-second production stage stores 10,000 records.

The run does not test or prove:
- the complete production RawLog save/finalize/recovery pipeline within its 10-second stage budget;
- power-loss or brownout durability, hardware write-cache behavior, or filesystem recovery;
- independent physical STOP circuitry or measured STOP latency;
- MCU STOP parsing, L298N cutoff, BOD/voltage-monitor behavior, EEPROM power-fail integrity;
- current limit, direction polarity, ADC calibration/settling, or analog accuracy;
- serial hardware interoperability or any motor/310-second physical measurement.

No Arduino upload, physical serial connection, motor energization, EEPROM/fuse operation, or physical test was performed. `HARDWARE_CURRENT_LIMIT_CONFIRMED=false` remains unchanged.

## Upper-command disposition

T18 host-filesystem fsync profile evidence is accepted **only within the scope stated above**. No broader T18 end-to-end acceptance is inferred. 310-5 remains open; no stage handoff, PR merge, or hardware authorization is granted by this record.
