# 310-5 monotonic-state rollback audit — 2026-11-05

Status: source-review finding / acceptance blocker
Branch: `safety/310-5-host-integration-candidate`
PR: #187 (Draft / Open / Unmerged)
Scope: host-side T01 session-tag allocator and T03 device-epoch checkpoint only.

## Executive result

A source review found two rollback cases that the current regression suite does not establish as safe:

- **T01:** the append-only tag journal and its hash-checked anchor are stored as two files on the same host filesystem. Restoring both files from the same older backup restores a mutually consistent old pair. The current code can accept that pair and reissue a tag already allocated after the backup.
- **T03:** the epoch checkpoint has an integrity checksum but no monotonic freshness anchor. Replacing it with an older, valid checkpoint for the same full `boot_id64` is accepted as `RESUME_SAME_EPOCH`, which can rewind the restored extended sequence.

These are not hypothetical checksum collisions. They are rollback/replay of authentic earlier state. A checksum or hash chain detects corruption and inconsistent partial rollback; it does not prove freshness when the entire locally stored state is rolled back together.

**Disposition: T01 and T03 are NOT PASS.** No local-file-only claim of rollback resistance is justified. No firmware, RawLog v2 package/schema/writer/validator, or physical hardware change is made by this audit.

## T01 — session-tag allocator

### Source behavior reviewed

`measurement_310/session_tag_allocator.py`:
- appends allocation records to a JSONL journal;
- validates record order, namespace, tag progression, and hash chain;
- writes a separately hashed anchor file;
- checks the anchor against the complete journal state before allocating;
- rejects a missing or mismatched anchor.

The existing test `test_old_backup_is_not_used_as_recovery_source` restores only the journal while leaving the newer anchor in place. That is a useful partial-rollback test, but it does not cover restoring both files to a matching older snapshot.

### Missing adversarial case

1. Allocate tag N and preserve a consistent copy of both journal and anchor.
2. Allocate tag N+1 (and optionally later tags).
3. Restore both journal and anchor from the older snapshot.
4. Attempt allocation.

Because the restored journal hash, high-water value, and anchor all agree, the current local verification has no independent fact proving that N+1 was ever allocated. It may allocate N+1 again.

### Required closure

A monotonic freshness witness must reside outside the rollback domain of the journal/anchor pair, or be provided by a trusted external service/device whose state cannot be rolled back with that pair. Examples for design evaluation include a remote append-only allocator, a separately administered durable counter service, or a qualified hardware monotonic counter. These are alternatives for authority review, not selected implementations.

Required evidence:
- explicit trust and failure model for the independent witness;
- crash/restart tests at every journal, anchor, and external-witness update boundary;
- restore both local files to an older consistent snapshot and prove allocation is refused or resumes strictly above the external high-water;
- concurrent allocator and namespace-isolation tests;
- behavior when the witness is unavailable, reset, or reports a lower value must fail closed;
- no tag is returned to the caller until the authoritative allocation is durably committed.

A second file, hash chain, or backup on the same rollback domain is not an independent monotonic witness.

## T03 — device epoch checkpoint

### Source behavior reviewed

`measurement_310/epoch_checkpoint.py`:
- serializes full-width `boot_id64`, extended sequence, and uint16 wire sequence;
- verifies a SHA-256 checksum and strict field set;
- resumes when the observed full `boot_id64` equals the checkpoint's boot ID;
- uses temp-file fsync, atomic replace, and directory fsync for writes.

These controls detect malformed/tampered checkpoints and avoid treating HELLO/ARM/STOP/session boundaries as reboot. They do not establish checkpoint freshness.

### Missing adversarial case

1. Persist checkpoint C1 for boot identity B at extended sequence S.
2. Later persist checkpoint C2 for the same B at sequence S+k.
3. Restore the authentic bytes of C1.
4. Observe the same full boot identity B.

The current resolver accepts C1 as `RESUME_SAME_EPOCH`. Its checksum remains valid. The tracker can therefore resume from S rather than S+k.

### Required closure

The host needs an independently durable high-water/freshness witness for the last accepted sequence/checkpoint, outside the checkpoint file's rollback domain. Alternatively, the system must explicitly classify continuity as unresolved after any restart where freshness cannot be independently proven; it must not claim a continuous sequence or silently accept a potentially stale checkpoint.

Required evidence:
- restore an older valid checkpoint for the same full boot ID and prove it is rejected or explicitly unresolved;
- prove same-epoch session boundaries preserve sequence when the independent high-water confirms it;
- prove a changed boot ID alone does not establish a real reboot absent the already-required independent reboot confirmation;
- test witness loss, corruption, rollback, and unavailable states fail closed;
- ensure sequence gaps remain accounted and no missing samples are synthesized.

The checkpoint's SHA-256 is an integrity check, not a monotonic counter.

## Cross-cutting design constraints

- Do not solve either issue by silently changing the RawLog v2 package contract. RawLog v2 remains exactly `manifest.json` plus `records.jsonl` under the current authority boundary.
- Do not invent a firmware-provided monotonic counter or assume EEPROM/MCU behavior. Any device-side witness requires a separately accepted firmware design and qualification.
- Do not treat host wall-clock timestamps, filesystem mtimes, ordinary file locks, or a second local file as rollback-proof monotonic state.
- If no independent witness is available, the safe outcome is unresolved/fail-closed, not a guessed high-water or a new epoch.

## Acceptance matrix update

| Gate | Finding | Disposition |
|---|---|---|
| T01 | Consistent rollback of journal + anchor is not detected by the present local design | NOT PASS |
| T03 | Authentic older same-boot checkpoint can be accepted and rewind sequence state | NOT PASS |

This audit is a source-level finding and a test-gap analysis. It is not a completed fix, a complete T01/T03 verification, or a 310-5 acceptance report. The branch remains Draft-only; no PR merge or stage transition is requested.

## Next authorized host-only work

1. Add deterministic adversarial tests that demonstrate the two rollback cases against the current implementation, keeping them as explicit failing acceptance fixtures or a separately marked reproducer until an independent witness design is approved.
2. Submit the witness/failure-model choice for command-authority decision before implementing a concrete external persistence backend.
3. After that decision, implement the selected host-side interface and test power-loss, crash, restore, and witness-unavailable boundaries.
4. Re-run complete repository CI against the exact resulting code/test HEAD and report exact run IDs and counts.

No Arduino upload, physical serial connection, motor energization, 310-second measurement, fuse/EEPROM operation, or hardware test was performed. `HARDWARE_CURRENT_LIMIT_CONFIRMED=false` remains in force.


## CI evidence for the audit commit

The audit document commit `eeab6869f5f26cd558fa7179e4c4a62bb47fd03b` triggered GitHub Actions run #1411:
https://github.com/hamtech86/mini4wd-ai-system/actions/runs/41945548129

All four repository jobs completed successfully:
- `test-breakin`: success
- `test-battery`: success
- `test-raw-log-and-sequence`: success
- `test-full-suite`: success; **528 passed in 12.59s**

This run verifies the repository checkout and existing test suite at the audit commit. It does not execute the adversarial paired-rollback reproducer described above, so it does not close T01/T03. No T01/T03 PASS is inferred from this CI result.


## Adversarial rollback fixtures executed — Actions run #1413

The two adversarial fixtures described above were added to the candidate tests and executed in a complete repository checkout at PR #187 HEAD `48506b941529d7cf82a12f2710c94f400f4dda0b`.

Workflow: https://github.com/hamtech86/mini4wd-ai-system/actions/runs/41945899970

All four jobs completed successfully:
- `test-breakin`: success
- `test-battery`: success
- `test-raw-log-and-sequence`: success
- `test-full-suite`: success; **528 passed, 2 xfailed in 11.85s**

The two expected failures are the explicit rollback fixtures:
- `test_paired_backup_rollback_does_not_reissue_a_previously_allocated_tag`: XFAIL (T01)
- `test_authentic_older_checkpoint_for_same_boot_is_not_accepted_after_rollback`: XFAIL (T03)

Both are marked `xfail(strict=True)` because the safe behavior is not implemented. Their XFAIL status confirms the current implementation does not meet the asserted rollback-safe behavior; it does not count as a passing acceptance test. CI green therefore means the repository suite completed with the known T01/T03 blockers explicitly exposed, not that T01/T03 are closed.

The PR remains Draft/Open/Unmerged. No firmware, RawLog v2 schema/writer/validator, merge, CI dispatch, physical serial connection, motor energization, 310-second measurement, or hardware test was performed. `HARDWARE_CURRENT_LIMIT_CONFIRMED=false` remains in force.
