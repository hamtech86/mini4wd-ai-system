# 310-5 T18 durable-persistence remediation

Status: implementation candidate committed in PR #193; complete regression CI and hosted T18 profile pass. Target-host validation remains pending.

## Evidence from the 2026-11-08 target-host run

The profile completed and its JSON SHA-256 sidecar verified. It recorded 31 stages, 3,100 ADC batches, 37,200 ADC slots, 10,143 Evidence events, and 310 loss-window summaries. RawLog validation returned zero errors, the Evidence bundle verified, and all loss-window summaries passed.

The profile status is nevertheless **FAIL**: every stage exceeded the 8,000 ms budget. Stage elapsed time was p50 24,518.446 ms, p95 25,223.586 ms, and max/p99.9 32,578.374 ms.

Observed cumulative synchronization costs:

| Operation | Calls | Cumulative time |
| --- | ---: | ---: |
| Evidence file fsync | 10,143 | 393,453.462 ms |
| RawLog records file fsync | 3,196 | 122,668.360 ms |
| RawLog work-state file fsync | 3,197 | 132,303.325 ms |
| RawLog directory fsync | 3,207 | 72,429.335 ms |

The run used an in-memory Protocol V2 peer and the real host filesystem persistence path. No physical device was opened. This is a target-host software/persistence profile, not physical STOP or hardware-safety evidence.

## Root cause in the current persistence path

1. Each Evidence event is appended under the journal lock and individually file-fsynced. A received ADC batch creates multiple sequential Evidence events (RX bytes, decoded frame, accepted batch), so one telemetry batch incurs repeated durable writes.
2. Each RawLog `append_many` call fsyncs `records.jsonl`, then atomically replaces and fsyncs `work_state.json`, including a parent-directory fsync. The T18 run invokes this path approximately once per ADC batch.
3. The measured cumulative costs overlap by design: `rawlog_append_many` timing contains its internal fsync calls and must not be added to the fsync totals as a separate cost.

## Required remediation design

### A. Evidence journal transaction batches

- Add an append-many operation that validates and serializes a bounded ordered group, constructs the hash chain in memory, writes the concatenated JSONL payload under one exclusive lock, and performs one file fsync before returning.
- Preserve a distinct event ID and hash for every event; each event's `previous_hash` must reference the immediately preceding event in the same transaction or the prior durable chain head.
- Update the cached file signature and chain head only after the complete write and fsync succeed.
- On short write/fsync/lock failure, invalidate cached chain state and fail closed. A retry must re-read and validate the durable file; it must not silently append after an uncertain boundary.
- Keep command-intent, FRAME_TX intent/completion, HELLO/ARM/APPLY_ACK/DISARM ACK correlation, protocol errors, and other safety-transition evidence synchronously durable before the caller can advance the corresponding state.
- ADC telemetry may be grouped only within an explicitly bounded persistence window. A proposed upper bound is 10 batches (about one second at the current 100 ms batch cadence); this is a design ceiling, not permission to mark buffered records durable.
- Flush pending telemetry before DISARM completion, before any subsequent ARM/command transition, and before normal finalization. Do not put a flush/fsync dependency on the independent STOP transmission path.
- If a process crash loses an uncommitted telemetry group, preserve it as an attributable/unattributable sequence gap during restart reconciliation. Never synthesize missing raw ADC values or report the group as persisted.

### B. RawLog bounded checkpointing

- Preserve the current public RawLog v2 package schema and final two-file package (`manifest.json` and `records.jsonl`).
- Investigate replacing per-ADC-batch `work_state.json` atomic replacement with a recoverable checkpoint model. The durable records JSONL must remain authoritative; startup recovery must derive the last complete record sequence/count from the preserved source bytes and must not trust a stale checkpoint as proof that later records were committed.
- A candidate checkpoint cadence is no more than 10 ADC batches (about one second), with a durable records-file fsync at each checkpoint and a durable state checkpoint. Control/lifecycle records must force a checkpoint before the controller crosses a stage/ARM boundary.
- Do not weaken directory-fsync requirements at package publication, recovery-original preservation, or manifest-last commit.
- Keep the original crash source byte-for-byte preserved. Recovery must distinguish complete newline-terminated records, a partial tail, and a stale checkpoint; it must never rewrite the preserved original.

### C. STOP and failure behavior

- STOP transmission must remain independent of Evidence and RawLog locks, buffers, queue drains, and fsync.
- A STOP write result remains distinct from a physical output-state confirmation.
- Any persistence failure or uncertain command/ACK boundary must inhibit further ARM and keep the controller fail-closed.
- No automatic resume is permitted after recovery.

## Mandatory tests before a new T18 run

1. Evidence append-many: exact hash-chain verification across multiple events, including existing-file append and process restart.
2. Evidence failure injection: short write, fsync error, and interruption between write and fsync; retry must either validate and continue safely or fail closed.
3. Crash injection at every RawLog checkpoint boundary: before records fsync, after records fsync, during checkpoint replacement, after checkpoint fsync, and during final publication.
4. Recovery: preserve original bytes; rebuild sequence/count from complete records; discard only an unterminated tail from the derived package; never attribute ADC records to a missing PWM_STAGE.
5. Ordering: no DISARM/next ARM may pass an uncommitted prior-stage record boundary.
6. STOP: a deliberately blocked persistence writer must not delay the independent STOP writer; no fsync is allowed on the STOP critical path.
7. Regression: full RawLog/Sequence, Break-in, Battery, and full Python test suites.
8. Performance: repeat the full 31-stage production-path profile on the target host with real filesystem persistence. Require all 31 stages within 8,000 ms (including p99.9/max), all package/evidence/loss checks passing, and the separately specified save-stage maximum/p99.9 budget satisfied. Hosted-runner timings do not substitute for this result.

## First implementation candidate — hosted-runner result

The first PR #193 implementation passed the full 31-stage T18 production-path workflow on the GitHub-hosted runner after the Evidence JSONL newline defect was corrected.

- Profile status: PASS.
- Stage count: 31; ADC batches: 3,100; ADC slots: 37,200.
- Evidence events: 10,143; loss-window summaries: 310; all loss windows PASS.
- RawLog validation errors: 0; Evidence bundle verification: PASS.
- Latest verified PR head: `ea5cb5d816ca038063204e1c85d04cf35b742cb0`.
- GitHub Actions T18 run #41 (`42492559051`): PASS; all 31 stages, 3,100 ADC batches, 37,200 ADC slots, and 10,143 Evidence events.
- Hosted-runner stage elapsed p50: 191.596 ms; p95: 515.208 ms; p99.9/max: 1,501.335 ms against the 8,000 ms stage ceiling.
- GitHub Actions full regression run #1700 (`42492559087`): all four jobs PASS (Break-in, Battery, RawLog/Sequence, full pytest); full suite **622 passed, 2 xfailed**.
- T18 artifact: [run #41 artifact](https://github.com/hamtech86/mini4wd-ai-system/actions/runs/42492559051/artifacts/13622650255).

These results establish the PR candidate's hosted-runner software regression and production-path profile. They do **not** replace the required run on the user's target host/storage. The original target-host result remains FAIL until a new target-host profile passes.

## Current disposition

- PR #193 hosted CI: **PASS** (T18 run #41; full regression run #1700).
- Original 2026-11-08 T18 target-host performance: **FAIL**; target-host rerun is still required.
- 310-5: **NOT ACCEPTED**.
- 310-6: **BLOCKED**.
- PR #192 is included in the integration merge; its recovery-attribution correction remains intact.
- No Arduino connection, serial-device access, firmware upload, EEPROM/fuse operation, re-ARM, or motor energization is authorized by this work.


## 2026-11-09 integration verification

- Candidate head: `a82db73df401efa5c2208e6b0a58694de47f9b8b`.
- Hosted T18 production-path run #48: PASS; 31 stages, 3,100 ADC batches, 37,200 ADC slots, 10,143 Evidence events. Stage elapsed p50 181.824 ms, p95 215.770 ms, p99.9/max 1,496.823 ms (8,000 ms ceiling).
- Full regression run #1707: all four jobs PASS; 628 passed, 2 xfailed.
- The run uses GitHub-hosted storage and an in-memory protocol peer. It does not replace the required target-PC filesystem rerun or establish physical STOP/device-safe-state evidence.
