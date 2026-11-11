# 310-5 target-host T18 production profile result — 2026-11-11

## Disposition

- Target-host T18 profile: **PASS**
- Profile checksum verification: **PASS**
- Persistence completion maximum observed: **PASS against the 10,000 ms single-run budget**
- Persistence p99.9: **NOT MEASURABLE from this run** (the top-level `sequence_complete` operation was observed once)
- 310-5 formal acceptance: **NOT ACCEPTED**
- 310-6: **BLOCKED**
- No hardware qualification or energization was performed or authorized.

This is target-host software/storage evidence only. It does not prove physical STOP behavior, reset/BOD behavior, current limiting, wiring, thermal safety, or physical no-auto-resume.

## Run identity

| Field | Value |
|---|---|
| Run date | 2026-11-11 (local target-host time) |
| Target host | User's Linux Mint 21.2 host |
| Code HEAD | `7d53858db2f7b07a1f1b5d6d17036fa13a4ff089` |
| Output directory | `~/mini4wd-ai-system-310-5-targethost-20261110/artifacts/310-t18-target-host-20261110-01` |
| RawLog evidence pointer | https://github.com/hamtech86/mini4wd-raw-logs/blob/main/log1111 |
| Profile file | `t18-production-profile.json` |
| Checksum result | `t18-production-profile.json: OK` |
| Profile status | `PASS` |

The user-provided execution output reports 31 stages, 3,100 ADC_BATCH, 37,200 ADC slots and 10,143 evidence events. The output directory contains the profile JSON, checksum, stage CSV and `rawlog/` tree.

## Stage timing (observational only)

| Metric | Measured |
|---|---:|
| p50 | 6,499.264817 ms |
| p95 | 9,534.410281 ms |
| p99 | 15,280.459091 ms |
| p99.9 | 15,280.459091 ms |
| max | 15,280.459091 ms |

Stage timing is observational under the accepted risk-based policy; the obsolete 8,000 ms stage ceiling is not an acceptance gate. The stage maximum must not be substituted for the duration of the persistence completion operation.

## Persistence diagnostics

The profile reports observational wrappers around production methods. Nested phase totals overlap and must not be added together. Durability operations were unchanged (`durability_operations_changed=false`).

| Operation | Count | Maximum |
|---|---:|---:|
| `sequence_complete` | 1 | 9,362.612762 ms |
| `rawlog_finalize` | 1 | 6,946.039029 ms |
| `evidence_bundle_finalize` | 1 | 2,372.405689 ms |
| `evidence_manifest_write` | 1 | 2,328.941614 ms |
| `rawlog_validate_package` | 1 | 2,714.450488 ms |
| `rawlog_parse_jsonl` | 1 | 1,967.440309 ms |
| `rawlog_publish_package` | 1 | 1,570.722631 ms |

The single observed `sequence_complete` duration is below 10,000 ms by 637.387238 ms. This supports a **maximum-observed single-run** result only; it does not establish a percentile or a repeatable worst-case bound. In particular, p99.9 for `sequence_complete` is not measurable with count=1.

### fsync observations

| Target | Count | Maximum |
|---|---:|---:|
| Command Intent file | 93 | 64.512343 ms |
| Command Intent directory | 93 | 77.109359 ms |
| Evidence file | 843 | 328.071091 ms |
| Evidence directory | 2 | 21.718001 ms |
| RawLog records file | 3,196 | 316.083173 ms |
| RawLog work-state file | 322 | 190.054801 ms |
| RawLog directory | 332 | 141.482206 ms |
| Other file | 4 | 576.776807 ms |
| Other directory | 1 | 41.724748 ms |

The `rawlog_append_many` wrapper was observed 3,195 times, maximum 499.819043 ms. Its aggregate and nested fsync totals are diagnostic and are not additive.

## Interpretation and remaining gates

1. T18 profile execution and profile checksum verification passed on the target host.
2. The observed `sequence_complete` operation completed in 9.363 seconds, below the 10-second single-run budget.
3. Stage p99/p99.9/max exceeded 10 seconds, but stage elapsed is not the persistence-operation budget and is not an acceptance gate under the risk-based policy.
4. A single `sequence_complete` sample cannot establish p99.9. Do not mark persistence p99.9 as PASS.
5. The output confirms no change to durability operations. Preserve the generated output and RawLog tree; do not rerun over this output path.
6. No real serial port was opened, no Arduino firmware was uploaded, no motor was energized, and no 310-second hardware measurement was run.

Physical items remain separately BLOCKED/NOT RUN as applicable: physical STOP outcome and independent cutoff qualification; MCU reset interval and safe outputs; power supply/current-limit confirmation; wiring and driver verification; thermal safety; physical no-auto-resume. Keep `HARDWARE_CURRENT_LIMIT_CONFIRMED=false`.

**Final status: T18 target-host diagnostic PASS (with persistence p99.9 unmeasured); 310-5 NOT ACCEPTED; 310-6 BLOCKED.**
