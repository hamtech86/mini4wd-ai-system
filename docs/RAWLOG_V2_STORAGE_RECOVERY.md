# RawLog v2 storage/recovery implementation notes (310-2)

## Scope and package boundary

The independent raw_log_v2 package does not alter the legacy raw_log_library v1 API. The public v2 package remains exactly manifest.json + records.jsonl. Private work/recovery metadata is not part of the public schema.

## Directories

- .work/<log_id>/records.jsonl: append-only in-progress JSONL.
- .work/<log_id>/work_state.json: private mutable recovery metadata, never a manifest.
- .recovery/<log_id>/<recovery_id>/original/: byte-preserving copy of every regular work file at recovery start.
- .recovery/<log_id>/<recovery_id>/recovery_record.json: source hashes, file list, recovery time, tail information, validation results and final package reference.
- .recovery/<log_id>/<recovery_id>/publication_state.json: private resumable publication journal, separate from immutable originals.
- <log_id>/: final two-file package only.

Recovery ID is deterministic from relative file names and original bytes. Repeated recovery verifies existing files and never replaces them. Each original file is first written and fsynced to a private staging file, then hard-linked into original/ without replacement. A crash during staging leaves no partial original file; a retry discards an incomplete staging file and resumes. Partial preservation resumes by adding only missing files; conflicting bytes fail closed. The recovery record is also published through a staged, fsynced hard link, and the publication journal uses atomic private-state replacement.

## Append and finalization

Each append writes one UTF-8 JSON object plus LF using O_APPEND, handles short writes and calls fsync before returning. Work-state counts update only after records fsync. records.jsonl is never truncated or repaired.

Final publication reserves the destination with exclusive directory creation. Both records.jsonl and manifest.json are written to staging files, fsynced, then published by same-filesystem hard links that atomically refuse replacement. manifest.json is published last and is the completion marker. A crash during either staging write leaves no partial public file; retry discards an incomplete staging file and resumes. A directory without manifest.json is not a complete package. Interrupted publication resumes only when the private publication intent and existing bytes match exactly. Conflicts fail closed.

## Crash recovery

At application startup, call list_incomplete_work() or recover_pending() before starting a new measurement. Discovery is deterministic and read-only; each returned work area is then recovered independently. Orphaned or malformed work areas fail closed and remain preserved for inspection.

Recovery first snapshots and fsyncs all work files into .recovery. Only newline-terminated JSON-object lines are candidates for the recovered package. An unterminated tail is retained only in the preserved original and excluded from final records.jsonl. Invalid complete lines are also retained in the original and excluded from recovered JSONL; they are listed in recovery_record.json. No missing PWM_STAGE is synthesized. The incomplete manifest counts only records actually included. Validator errors, including record_seq gaps caused by rejected lines, are recorded; recovery never rewrites record IDs, sequence numbers or record content to disguise invalid source data.

The work directory is removed only after original preservation and final package are fsynced and verified. For a normal-finalize package discovered after a manifest-last crash, startup recovery verifies both publication-intent hashes and explicitly fsyncs the final package directory before marking the work state published or deleting `.work`; a failed fsync leaves `.work` intact. Recovery originals are not automatically deleted or overwritten.

## Filesystem guarantees and limits

- fsync(file) requests persistence of file content; fsync(directory) requests persistence of directory-entry changes. Actual guarantees depend on OS, filesystem, mount options, storage device and hardware write cache.
- The implementation fails closed if directory fsync is unavailable.
- Exclusive mkdir provides a destination reservation under normal POSIX directory semantics.
- manifest publication uses a hard link and requires same-filesystem hard-link support. Unsupported filesystems fail closed; no unsafe copy/replace fallback is used.
- os.replace is used only for mutable private state files, never for records.jsonl, preserved originals or a published manifest.
- Network filesystems, removable media, Windows filesystems, unusual mount options, controller caches and power-loss behavior are not certified by software tests.
- A crash after destination reservation but before manifest publication can leave a directory without a manifest. It is not a complete package and can be resumed only with the matching private publication journal.

## Verification

Tests use temporary directories and synthetic records only. They do not open serial ports, use Arduino tooling or energize hardware.
