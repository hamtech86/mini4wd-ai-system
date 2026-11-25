# Battery Capture Contract Evidence Recovery Report

- Date: 2026-11-25
- Scope: CR-01 .. CR-06 / Battery 5A / CH1 / CH2
- Target code acceptance: PR #218, accepted code HEAD `91c635dd5c129633898566adf929a8dc2f7386ab`
- Evidence-only branch: `docs/battery-capture-contract-evidence-recovery-20261125`
- Baseline matrix: `docs/battery_capture_contract_evidence_matrix.md` (blob `8a73a16b292d9c517ac5eb1f285806e822bb0f59`)
- No firmware, DB schema, Migration, DB data, main, or hardware changes were made.

## Executive result

The existing evidence is sufficient to establish the command/frame vocabulary and several local software behaviors. It is not sufficient to define a complete end-to-end Capture Contract. In particular, the following are not established by current authoritative evidence: CaptureStarted/CaptureEnded envelope linkage; timeout/error/cancel outcome mapping; COMPLETE minimum sample/record requirements; duplicate/gap/order policy; byte-preserving RawLog and hash/ID linkage; timestamp/sequence contract; and formal Aggregate eligibility.

Do not fill these gaps by inference. Keep unknown records opaque and out of formal COMPLETE/Aggregate acceptance until the responsible contract is approved. Physical 5A E2E remains NOT RUN under Issue #16.

### Accepted decisions explicitly excluded from re-review

- CH1 and CH2 are independent measurement streams; STARTALL is a control operation, not a measurement channel.
- No cross-channel average/sum/fallback for Battery benchmark values.
- Selected-channel voltage/current 0.0 is Validity UNKNOWN; raw values remain unchanged; derived Benchmark/Aggregate acceptance is blocked. Non-selected-channel zero does not invalidate the selected channel.
- PR #218 A1-A7 and V1/V2, CH independence, Scope Key all-row checks, and registration-time Scope revalidation remain accepted. No item below reopens them.
- DB GL-04 Scope Key / RawLog Reference / Sample Reference field mapping is already answered in Issue #207 comment #7101200440; no DB re-query is requested.

## Evidence baseline and search scope

1. Battery spec: `docs/battery_benchmark_spec_v2.md`, blob `1ff1e0b50731efba2dabf8569fbb6d42634ce1e2` on PR #218 branch.
2. Existing matrix: `docs/battery_capture_contract_evidence_matrix.md`, blob `8a73a16b292d9c517ac5eb1f285806e822bb0f59`.
3. Host serial: `battery_system/serial.py`, blob `f5113138143cb0698364240d69ef7ee23a37ac3d`.
4. Battery UI: `ui/battery_tab_ui.py`, blob `57de86e766e341aa884493d1b1a9e6a8f235bde6` at accepted HEAD.
5. RawLog library: `raw_log_library/manager.py`, blob `4af6a4fc85b6de91b320494afab1884e2a4a3ac2`.
6. Standalone parser: `measurement/battery_measurement_parser.py`; tests `tests/test_battery_measurement_parser.py`.
7. External firmware source: `hamtech86/mini4wdprototype/2ch5Abattery/2ch5Abattery.ino`, blob `5c9cd31ce5c187ab437e92b2cab5b523418fd620` on external repo main.
8. Relevant tests: `tests/test_anonymous_mode.py`, `tests/test_battery_tab_safety.py`, `tests/test_battery_benchmark.py`, `tests/test_battery_benchmark_session.py`.
9. Governance/decision records: Issue #16 comments #7080826275, #7103030682, #7103139429, #7105933799; PR #218 acceptance comment #6056751043; Issue #207 comment #7101200440.
10. Targeted GitHub code searches and commit-message searches were run for Capture lifecycle, ACK/ERROR, RawLog/hash, sequence, millis wrap, COMPLETE eligibility, and Measurement Outcome. Commit-message searches returned no matching commits for those exact terms. This is a bounded search result, not proof that every historical commit or external artifact has been exhaustively inspected. The matrix and named current source blobs are the positive evidence baseline.

---

## 1. CR-01 — Capture Lifecycle

### A. Current status

- DEFINED: Firmware command vocabulary `START1`, `START2`, `STARTALL`, `STOP1`, `STOP2`, `STOPALL`; ACK responses; firmware states RUN / COMPLETE / TIMEOUT / STOP; startup sensor failure `ERROR,INA3221`.
- IMPLEMENTED: Host sends START/STOP commands; DATA parsing; Anonymous Mode disconnect finalization as `DISCONNECTED_INCOMPLETE`; UI state handling for a subset of states.
- TEST_COVERED: Parser tests; Anonymous disconnect/incomplete RawLog test; START/retry safety tests.
- NOT_DEFINED: Formal CaptureStarted/CaptureEnded event and Measurement Envelope linkage; CANCEL / INTERRUPTED event semantics; TIMEOUT and ERROR outcome mapping; ACK correlation to a specific capture; reconnect semantics.
- NOT_IMPLEMENTED: Host-side durable ACK/INFO/ERROR event journal; formal Capture event envelope; normal DB capture's complete event history.
- NOT_RUN: Real device lifecycle / 5A E2E.

### B. Evidence recovery

**RECOVERABLE**
- External firmware source defines command handling and ACKs. `processCommand()` emits ACK after START/STOP; `getState()` emits RUN, COMPLETE, TIMEOUT, or STOP in DATA; `setup()` emits `ERROR,INA3221` on INA initialization failure.
- `battery_system/serial.py`: `start()` / `stop()` only send command text; `read_lines()` decodes incoming lines; `parse_data()` accepts DATA only.
- `ui/battery_tab_ui.py`: `poll_serial()` recognizes DATA and optionally STATUS lines. It does not journal ACK, INFO, DEBUG, or ERROR frames. The DATA terminal recognition branch handles COMPLETE, ERROR, CANCEL/CANCELLED, STOPPED; it does not include firmware's literal STOP or TIMEOUT.
- `_status()` handles STOP / STOPPED / ERROR / CANCEL variants if called, but that does not establish that the current firmware's STOP/TIMEOUT DATA frames reach that handler.
- `tests/test_anonymous_mode.py::test_battery_anonymous_mode_preserves_incomplete_rawlog_on_disconnect` covers Anonymous disconnect preservation, not a formal Measurement Outcome.
- Issue #16 comment #7080826275 records the earlier firmware/UI mismatch and missing event mapping.

### C. Unresolved handling

- Reason: The current firmware exposes a state vocabulary, but the host does not have a complete event-to-capture journal or formal Outcome mapping. Firmware does not emit CANCEL or INTERRUPTED. Current firmware does not emit STATUS frames, although UI has a STATUS parser.
- Additional evidence needed: approved event semantics and mapping for STOP, TIMEOUT, ERROR, disconnect, user cancel, and process interruption; whether/how command ACKs are bound to a capture identity.
- Owner: Battery Owner for host-side evidence inventory; Firmware Owner / external repository maintainer for any authoritative firmware behavior confirmation; Central Command for contract decisions.
- Next action: Central Command decides the intended event vocabulary and outcome mapping before any implementation work. Firmware owner confirms whether current deployed firmware matches the cited blob.
- Completion condition: One approved lifecycle table mapping command/event/frame → capture state → Measurement Outcome, plus tests for every supported event and explicit unsupported events.
- If evidence cannot be obtained: retain raw frames where available, classify outcome UNKNOWN/INCOMPLETE, exclude from COMPLETE/Aggregate; do not infer successful completion from silence or Session closure.

**Classification:** Existing command/state vocabulary = RECOVERABLE. Deployed-device equivalence and physical event behavior = CONDITIONALLY_RECOVERABLE. CANCEL/INTERRUPTED semantics and missing ACK-to-envelope mapping = NO_CURRENT_BASIS until a decision is issued.

---

## 2. CR-02 — COMPLETE Eligibility

### A. Current status

- DEFINED: Firmware COMPLETE is caused by voltage cutoff (`voltage <= VOLTAGE_CUTOFF`); TIMEOUT is a distinct firmware state. Battery spec v2 lists Benchmark fields and says only COMPLETE sessions are eligible. The v2 validity section requires finite selected-channel voltage/current/elapsed time for every selected-channel row.
- IMPLEMENTED: UI recognizes a subset of COMPLETE signals; analysis and registration reject missing, nonnumeric, non-finite and selected-channel zero values; normal BatteryTab registration requires a nonempty sample list and completed flag.
- TEST_COVERED: Selected-channel invalid/missing/zero checks, including first/middle/last positions, CH1/CH2, and normal BatteryTab registration zero cases.
- NOT_DEFINED: Minimum sample count beyond nonempty; required event/record set; start/end validity policy beyond the spec's field derivation; gap tolerance; duplicate policy; arrival-order policy; acceptable sampling interval.
- NOT_IMPLEMENTED: Duplicate/gap/order quality gate; explicit minimum count gate; formal evidence-set eligibility object.
- NOT_RUN: Real COMPLETE capture against the device and expected raw-to-result values.

### B. Evidence recovery

**RECOVERABLE**
- Firmware `getState()` / `updateChannel()`: COMPLETE is set on voltage cutoff; TIMEOUT is separate.
- `docs/battery_benchmark_spec_v2.md`: required fields include start_voltage, end_voltage, avg/max values, duration, voltage_drop, capacity, energy, measurement_count; start/end are described as first/last valid voltage; only COMPLETE sessions eligible.
- `ui/battery_tab_ui.py::register_results()`: normal DB path requires `completed[ch]` and nonempty samples. It does not impose a minimum count greater than one.
- `BatteryTab._stats()` sorts by elapsed time and computes metrics. It does not reject duplicate elapsed values or detect original arrival order; repeated timestamps yield zero-width integration intervals. Sorting means an out-of-order arrival can be normalized rather than flagged.
- `analysis/battery_benchmark_session.py::extract_battery_benchmark()` also sorts by elapsed time.
- `analysis/battery_benchmark.py` tests cover selected-channel validity. Relevant tests include `test_incomplete_selected_sample_at_any_position_fails_closed`, `test_incomplete_elapsed_time_fails_closed`, `test_zero_selected_current_has_unknown_validity`, and `test_nonselected_channel_zero_does_not_invalidate_selected_channel`.
- `tests/test_battery_tab_safety.py::test_normal_battery_tab_zero_selected_sample_never_inserts` covers the four CH × V/I zero registration cases.
- Spec v2's stated E2E criterion requires start_voltage/end_voltage/voltage_drop in `battery_benchmark_result`; current normal BatteryTab insert payload shown in `register_results()` does not supply those keys. No evidence in the reviewed code establishes that the E2E criterion is satisfied.

### C. Unresolved handling

- Reason: “COMPLETE” is presently a firmware cutoff state and a UI registration precondition, not a complete data-quality contract. The required minimum sample count, required records, gap/duplicate/order policy are not specified. Do not infer a numeric threshold.
- Additional evidence needed: Central Command-approved eligibility table; if eligibility depends on device sampling behavior, a captured real trace and hardware timing evidence.
- Owner: Central Command for eligibility rules; Battery Owner for code/test inventory; Firmware Owner for actual sampling/terminal behavior; user/equipment owner for real capture fixture.
- Next action: decide whether a one-sample capture is eligible, what records are mandatory, and whether duplicate/gap/order anomalies reject or quarantine a capture. Do not implement until approved.
- Completion condition: approved rule set, tests for accepted/rejected boundary cases, and later Issue #16 E2E evidence.
- If evidence cannot be obtained: keep outcome/validity UNKNOWN or INCOMPLETE and exclude the derived result from formal Benchmark/Aggregate. Preserve all raw rows.

**Classification:** Firmware cutoff meaning and current software behavior = RECOVERABLE. Real sample cadence / actual device trace = CONDITIONALLY_RECOVERABLE. Minimum count, duplicate/gap/order policy and unapproved thresholds = NO_CURRENT_BASIS.

---

## 3. CR-03 — RawLog Contract

### A. Current status

- DEFINED: Firmware DATA frame is a 10-field CSV line: `DATA, BATTERY_DISCHARGER_V1, CHn, elapsed_ms, current_A, voltage_V, reserved, PWM, reserved, state`; baud rate 57600. Firmware also emits DEBUG, INFO, ACK, and ERROR frames.
- IMPLEMENTED: Host decodes serial bytes as UTF-8 with `errors="replace"`; Anonymous Mode stores selected decoded line strings; RawLog Library stores a UTF-8 text body plus separate JSON metadata and CSV index.
- TEST_COVERED: CRLF line preservation at the decoded-string layer; Anonymous saved text and retry tests.
- NOT_DEFINED: Battery-specific RawLog schema/version and strict byte-level framing contract; exact full-stream inclusion policy; hash algorithm/target and immutable byte identity contract.
- NOT_IMPLEMENTED: SHA-256/body hash; Battery Measurement ID ↔ RawLog Object ID ↔ Sample Reference linkage in the capture path; normal DB capture RawLog persistence/linkage; binary byte-preserving capture.
- NOT_RUN: Physical source-byte vs saved-byte/hash comparison.

### B. Evidence recovery

**RECOVERABLE**
- External firmware `sendData()` emits DEBUG then a 10-field DATA frame; `processCommand()` emits INFO/ACK/ERROR as applicable.
- `battery_system/serial.py::read_lines()` preserves line terminators after decoding but uses UTF-8 replacement decoding. Invalid byte sequences therefore cannot be proven byte-identical after this boundary.
- `RawLogLibrary.register()` writes the supplied Python string as UTF-8 text with newline translation disabled; `read_raw()` reads text with newline translation disabled. This preserves decoded text line endings, not arbitrary original serial bytes.
- `ui/battery_tab_ui.py::poll_serial()` in Anonymous Mode appends STATUS, valid DATA, and malformed DATA frames. It does not append DEBUG, INFO, ACK, or ERROR lines to the Anonymous RawLog. Therefore current Anonymous RawLog is not proven to be a complete wire transcript.
- Anonymous RawLog metadata includes log_id, channel, acquired_at, measurement_session_id, notes; current BatteryTab sets measurement_session_id to None. No SHA-256 is calculated in the reviewed manager or BatteryTab path.
- Normal DB registration persists Measurement rows but does not call RawLogLibrary; the code path does not link a RawLog object to the DB Measurement rows.
- Tests: `tests/test_anonymous_mode.py::test_battery_serial_read_lines_preserves_original_line_endings`, `test_battery_anonymous_mode_allows_instance_free_channel_and_saves_rawlog`, `test_battery_anonymous_mode_simultaneous_channels_save_separate_rawlogs`.

### C. Unresolved handling

- Reason: The present path stores decoded selected lines for Anonymous Mode, not a byte-exact full serial stream. No hash or end-to-end object identity chain is implemented. Normal DB capture and Anonymous RawLog are separate paths.
- Additional evidence needed: approved RawLog schema/version, frame inclusion rules, exact bytes/hash target, ID linkage contract, and a source-byte fixture or physical serial capture.
- Owner: Central Command for contract; Battery Owner for host capture implementation after approval; Firmware Owner for frame/version guarantees; user/equipment owner for physical source-byte comparison. DB field mapping is already answered; do not re-query DB.
- Next action: decide whether the canonical evidence is (a) raw serial byte stream, (b) selected decoded records, or (c) both with separate hashes. Decide which control/diagnostic frames are mandatory. Then specify hash target and identity linkage.
- Completion condition: versioned contract, tests that compare exact bytes including CRLF/LF and malformed bytes, hash verification, and linked RawLog/Measurement/Sample references; normal DB and Anonymous paths both demonstrate the approved behavior.
- If evidence cannot be obtained: label current objects as decoded-text RawLogs with partial-frame coverage; do not claim byte preservation or complete RawLog linkage; exclude them from evidence requiring those properties.

**Classification:** Existing frame format and text persistence behavior = RECOVERABLE. Physical byte equivalence and deployed firmware match = CONDITIONALLY_RECOVERABLE. Canonical byte/hash/linkage rules = NO_CURRENT_BASIS pending decision.

---

## 4. CR-04 — Timestamp / Sequence

### A. Current status

- DEFINED: Firmware computes per-channel elapsed time from `millis() - startTime`, in milliseconds; each channel has its own startTime. STARTALL invokes the two channel starts sequentially.
- IMPLEMENTED: Host parser converts elapsed_ms to elapsed seconds; normal UI stores host-side `session_started` from local `datetime.now()` at command initiation.
- TEST_COVERED: Parser elapsed conversion and basic channel parsing.
- NOT_DEFINED: Sequence/sample number; duplicate identity; arrival-order guarantee; millis rollover contract; UTC/timezone/clock accuracy; host clock to device elapsed correlation; STARTALL inter-channel start skew bound.
- NOT_IMPLEMENTED: Sequence counter, duplicate detection, monotonic-order validation, wrap reconstruction, synchronized host/device timestamp model.
- NOT_RUN: Physical timing accuracy, rollover boundary, or STARTALL skew measurement.

### B. Evidence recovery

**RECOVERABLE**
- Firmware `Channel.startTime` is `unsigned long`; `startChannel()` sets it to `millis()`; `sendData()` emits `millis() - startTime` as elapsed milliseconds. Each channel is initialized by its own call.
- `BatterySerial.parse_data()` converts elapsed_ms to seconds; standalone parser retains elapsed_ms as integer.
- `BatteryTab.start_channel()` captures local host wall time using `datetime.now().isoformat(timespec="seconds")` before sending START. It does not establish UTC or an offset-aware timestamp, and does not bind that value to ACK or first DATA.
- `BatteryTab._stats()` sorts samples by elapsed time and does not check duplicates or preserve/validate arrival order.
- `analysis/battery_benchmark_service.py` reads Measurements ordered by elapsed_time, id. This is a query order, not proof of original arrival order.
- No sequence field appears in the reviewed 10-field DATA frame or BatterySample structure.

### C. Unresolved handling

- Reason: elapsed time exists, but there is no sequence identity or explicit cross-clock relationship. Sorting cannot prove source order; duplicates can remain indistinguishable.
- Additional evidence needed: Central Command decision for sequence semantics and timestamp basis; Firmware Owner confirmation of target MCU millis width and runtime behavior; physical STARTALL skew/timing measurements if a tolerance is required.
- Owner: Central Command for logical contract; Firmware Owner for firmware clock details; Battery Owner for host timestamp capture; user/equipment owner for physical timing evidence.
- Next action: decide whether sequence is required and whether host timestamps are metadata only or part of the authoritative timeline. Define rollover and duplicate behavior only after confirming target platform details.
- Completion condition: approved time/sequence contract, parser and ordering tests including duplicates/out-of-order/wrap, and physical timing evidence where required.
- If evidence cannot be obtained: preserve elapsed_ms as received and host start time as separate uncorrelated metadata; do not sort-and-claim source order, deduplicate, or infer UTC correspondence.

**Classification:** Existing elapsed-time implementation = RECOVERABLE. MCU-specific rollover behavior and measured start skew = CONDITIONALLY_RECOVERABLE. Sequence/duplicate/time-correlation policy = NO_CURRENT_BASIS.

---

## 5. CR-05 — Partial Capture / Retry

### A. Current status

- DEFINED: Battery spec v2 says failed persistence retains samples; restart is blocked until persistence succeeds; CH restart eligibility is independent; STARTALL is blocked if either target has pending samples. Anonymous disconnect is currently labeled DISCONNECTED_INCOMPLETE in code.
- IMPLEMENTED: Normal DB sample retention on commit failure; Anonymous local RawLog retry; restart guard; per-channel buffers; disconnect finalization in Anonymous Mode.
- TEST_COVERED: V1 commit-failure and Anonymous RawLog failure/retry tests; Anonymous disconnect test; restart guard tests.
- NOT_DEFINED: Formal partial-to-outcome mapping; replay/retransmission semantics; duplicate frame semantics; idempotent RawLog save across mid-write failure; normal DB RawLog retry/linkage.
- NOT_IMPLEMENTED: Protocol-level replay detection; capture-level RawLog idempotency key; full normal DB RawLog persistence/retry.
- NOT_RUN: Physical disconnect/reconnect, serial replay, and real filesystem interruption tests.

### B. Evidence recovery

**RECOVERABLE**
- `BatteryTab.set_connected(False)` finalizes active Anonymous captures with DISCONNECTED_INCOMPLETE. This behavior does not cover normal DB mode.
- Anonymous RawLog failure retains samples and capture buffers; the V1 test `test_anonymous_rawlog_save_failure_retains_capture_until_retry_then_allows_start` verifies retry through actual `start_channel(1)`, no START on failed save, buffer/capture retention, and next START after successful save.
- `test_db_commit_failure_retains_samples_and_retry_allows_next_capture` verifies DB rollback, sample and COMPLETE status retention, successful retry, and next START after persistence.
- `RawLogLibrary.register()` performs multiple filesystem writes in sequence: raw body, metadata JSON, then index append. There is no transaction or idempotency key spanning these writes. Current flaky-save tests fail before the underlying register writes; they do not cover a failure after one or more files have been written. A retry after a partial filesystem write is therefore not proven idempotent.
- Firmware has no replay/sequence identity in the DATA frame; current host code does not detect repeated DATA frames.

### C. Unresolved handling

- Reason: tested retry paths prove selected application-level retention/retry cases, not all crash points, replay, or cross-mode behavior. The anonymous save retry does not establish exactly-once persistence.
- Additional evidence needed: approved idempotency identity and duplicate policy; fault-injection tests at each RawLog write boundary; normal DB capture RawLog linkage design; actual disconnect/reconnect trace if physical behavior is required.
- Owner: Battery Owner for local persistence behavior; Central Command for replay/partial policy; user/equipment owner for physical communication interruption.
- Next action: request Central Command decision on whether retry guarantees are at-least-once, at-most-once, or exactly-once, and what duplicate evidence is retained. Do not retrofit a guessed policy.
- Completion condition: approved retry contract; failure-injection tests before/after each write; repeated-frame tests; end-to-end retry evidence for normal DB and Anonymous paths.
- If evidence cannot be obtained: retain failed capture buffers; mark persistence outcome UNKNOWN; do not claim exactly-once or promote partial capture to COMPLETE.

**Classification:** Current tested retention/retry behavior = RECOVERABLE. Physical communication interruption and filesystem crash behavior = CONDITIONALLY_RECOVERABLE. Exactly-once/replay/partial-promotion policy = NO_CURRENT_BASIS.

---

## 6. CR-06 — Outcome / Aggregate

### A. Current status

- DEFINED: Central Command record #7103030682 and Issue #16 comment #7080826275 state that “COMPLETE session eligible” means Measurement Outcome=COMPLETE, not Session Lifecycle=CLOSED. CC-01 requires Session Lifecycle and Measurement Outcome to be separate.
- IMPLEMENTED: Current Battery UI uses a completed flag and stores `measurement_session.result="COMPLETE"` in the legacy registration path. Analysis validity checks block selected-channel unknown values.
- TEST_COVERED: Tests cover local COMPLETE registration preconditions and selected-channel validity. No end-to-end test proves CC-01 Outcome mapping or Aggregate admission.
- NOT_DEFINED: Battery mapping from STOP/TIMEOUT/ERROR/disconnect/partial to formal Measurement Outcome; required evidence for Outcome=COMPLETE; Battery Aggregate acceptance rule and revision lineage.
- NOT_IMPLEMENTED: A distinct formal Battery Measurement Outcome envelope and complete Aggregate gate integration.
- NOT_RUN: Real E2E and Aggregate acceptance verification.

### B. Evidence recovery

**RECOVERABLE**
- Issue #16 comment #7080826275 explicitly says COMPLETE eligibility refers to Measurement Outcome, not Session Lifecycle; #7103030682 assigns remaining Capture contract to Battery Owner and says unknown items remain UNKNOWN/NOT_DEFINED and DB side remains opaque/excluded.
- `docs/battery_benchmark_spec_v2.md` still phrases eligibility as “Only COMPLETE sessions”; the governance clarification supplies the intended interpretation.
- `ui/battery_tab_ui.py::register_results()` writes `measurement_session.result="COMPLETE"`; this is current legacy implementation evidence, not proof of a separate Outcome entity.
- PR #218 acceptance comment #6056751043 explicitly excludes Capture Contract, real 5A E2E, physical discharge, DB design approval, FW/control changes and schema/DDL/Migration from code acceptance.

### C. Unresolved handling

- Reason: The logical separation is decided, but Battery implementation still uses legacy Session result storage and lacks a complete formal Outcome mapping / Aggregate gate.
- Additional evidence needed: approved mapping table and exact Aggregate admission criteria; DB contract mapping is already answered and is not a blocker for asking the logical decision.
- Owner: Central Command for Outcome/Aggregate semantics; Battery Owner for mapping current event evidence to the approved contract; DB Owner only if later implementation requires a separately authorized integration clarification.
- Next action: Central Command decides the Battery Outcome mapping and whether unknown/partial states are excluded, quarantined, or retained as opaque-only. Do not ask DB to re-answer field mapping.
- Completion condition: approved Outcome mapping, implementation plan approved separately, tests for all terminal states, and later E2E/Aggregate evidence.
- If evidence cannot be obtained: Session Lifecycle remains independent; no Aggregate inclusion is inferred from Session CLOSED or a legacy result field; unknown outcomes remain opaque and excluded.

**Classification:** CC-01 separation and interpretation = RECOVERABLE / already decided. Formal Battery mapping and Aggregate rule = NO_CURRENT_BASIS pending Central Command decision. End-to-end proof = CONDITIONALLY_RECOVERABLE (requires later implementation approval and real fixture/device gate).

---

## Deliverable 2 — Unrecovered item disposition list

### 2.1 Additional repository investigation can resolve

| Item | Classification | Search target / action | Owner | Completion condition |
|---|---|---|---|---|
| Exact UI handling of firmware STOP/TIMEOUT and ignored frames | RECOVERABLE | `ui/battery_tab_ui.py::poll_serial`, `_status`; add a source-to-host event coverage table after decision | Battery | Every firmware frame/state has an explicit supported/ignored disposition |
| Current COMPLETE precondition and actual minimum currently enforced | RECOVERABLE | `BatteryTab.register_results()`, `_stats()`, spec v2 | Battery | Document current behavior separately from future policy |
| RawLog multi-file partial-write failure behavior | RECOVERABLE | `raw_log_library/manager.py::register`; fault injection at raw/metadata/index boundaries | Battery | No ambiguous duplicate or lost evidence after injected failure |
| Current normal DB path lacks RawLog persistence | RECOVERABLE | `ui/battery_tab_ui.py::register_results()` and RawLog call sites | Battery | Code-path inventory and explicit non-coverage statement |

### 2.2 Requires other department, user, external evidence or hardware

| Item | Classification | Required cooperation | Owner | Completion condition |
|---|---|---|---|---|
| Deployed firmware equivalence to cited source blob | CONDITIONALLY_RECOVERABLE | Firmware owner confirms deployed binary/build/source identity | Firmware Owner / user | Build identity tied to the captured device |
| Actual serial bytes, frame timing, STARTALL skew, disconnect/reconnect behavior | CONDITIONALLY_RECOVERABLE | User/equipment and a later explicitly authorized capture | User / Firmware Owner | Reproducible raw capture and test conditions |
| Byte-for-byte source-vs-RawLog and SHA evidence | CONDITIONALLY_RECOVERABLE | Physical serial byte fixture or controlled capture | User / Battery | Exact source/captured bytes and approved hash target verified |
| Real 5A RawLog→Measurement→Benchmark E2E | CONDITIONALLY_RECOVERABLE | Issue #16 gate, real hardware, measurement setup, explicit user authorization | Battery + user | Separate Issue #16 acceptance; currently NOT RUN |
| Physical millis rollover / clock accuracy, if required | CONDITIONALLY_RECOVERABLE | Confirm target MCU and controlled time-boundary test | Firmware Owner + user | Platform-specific evidence and approved test |

### 2.3 No current basis; requires specification decision or explicit hold

| Item | Classification | Required decision / treatment | Decision owner |
|---|---|---|---|
| CANCEL / INTERRUPTED semantics | NO_CURRENT_BASIS | Define whether these are host-only events, firmware states, or unsupported; until then UNKNOWN/INCOMPLETE | Central Command |
| ACK-to-Capture identity / CaptureStarted-CaptureEnded envelope linkage | NO_CURRENT_BASIS | Define event identity and correlation before implementation | Central Command |
| Minimum COMPLETE sample count / required record set | NO_CURRENT_BASIS | Set explicit acceptance criteria; no numeric threshold inferred | Central Command |
| Gap tolerance / duplicate / out-of-order policy | NO_CURRENT_BASIS | Decide reject vs quarantine vs accepted-with-quality-flag; no silent sorting/deduplication policy inferred | Central Command |
| Sequence number and duplicate identity | NO_CURRENT_BASIS | Decide whether sequence is required and its scope/uniqueness | Central Command |
| millis wrap reconstruction and host UTC correlation | NO_CURRENT_BASIS | Define authoritative clock and wrap semantics after target MCU confirmation | Central Command |
| RawLog byte contract, schema version, SHA-256 target and ID-link chain | NO_CURRENT_BASIS | Approve byte/text source, included frame types, schema version, hash target, and identity chain | Central Command |
| Partial-to-COMPLETE promotion and exactly-once retry semantics | NO_CURRENT_BASIS | Decide promotion and retry guarantees; until then partial/unknown is not COMPLETE | Central Command |
| Battery Outcome mapping and Aggregate eligibility | NO_CURRENT_BASIS | Approve event→Outcome mapping and Aggregate admission/exclusion rules | Central Command |

---

## Deliverable 3 — Central Command decision requests

The following are discrete decisions; Battery Owner does not choose defaults.

### CC-CR01 — Lifecycle / terminal event mapping
Choose:
- A. Firmware event vocabulary only; host CANCEL/INTERRUPTED remain unsupported.
- B. Host may create CANCEL/INTERRUPTED events, explicitly distinguished from firmware events.
- C. Extend the firmware contract later (requires separate firmware authorization).

Impact/risk: A leaves user cancellation/process interruption unrepresented unless retained as external metadata. B requires a host event journal and correlation semantics. C requires a new firmware change gate. Until decided, CANCEL/INTERRUPTED and ACK linkage remain UNKNOWN.

### CC-CR02 — COMPLETE minimum evidence
Choose:
- A. Any nonempty finite sample set plus firmware COMPLETE (current minimum behavior; not yet approved as a complete quality contract).
- B. A defined minimum sample/record set and validity checks.
- C. Keep COMPLETE as a device terminal fact, but require a separate quality eligibility result before Benchmark/Aggregate.

Impact/risk: A may accept undersampled captures. B requires explicit values and test boundaries. C preserves device outcome but separates it from analytical eligibility. No count or threshold is proposed by Battery.

### CC-CR03 — Ordering / duplicates / gaps
Choose:
- A. Reject any duplicate or non-monotonic sequence/time evidence.
- B. Quarantine affected capture while retaining raw data.
- C. Allow a documented tolerance/quality state (requires explicit limits and rationale).

Impact/risk: A is conservative but may reject benign repeats. B preserves evidence without admitting uncertain aggregates. C requires numeric/policy values not present today. No silent sort/deduplicate behavior should be treated as a contract.

### CC-CR04 — RawLog canonical source and hash
Choose:
- A. Preserve raw serial bytes as canonical evidence and hash those bytes.
- B. Preserve decoded text records and hash canonical encoded text.
- C. Preserve both raw bytes and decoded parsed records, with separate hashes and explicit linkage.

Impact/risk: A offers strongest wire fidelity but requires a byte-oriented receive/storage path. B is simpler but cannot claim arbitrary byte fidelity after replacement decoding. C offers traceability but adds storage/link complexity. Also decide whether DEBUG/INFO/ACK/ERROR are part of the capture evidence.

### CC-CR05 — Timestamp authority
Choose:
- A. Device elapsed_ms is authoritative; host time is descriptive metadata only.
- B. Host UTC is authoritative for wall-clock correlation; device elapsed remains per-capture duration.
- C. Retain both with an explicit synchronization/correlation model.

Impact/risk: A cannot compare captures by absolute time. B does not fix device sample order. C needs a clock-sync method and uncertainty evidence. STARTALL per-channel start skew also needs a decision if simultaneous timing is required.

### CC-CR06 — Partial capture / retry guarantees
Choose:
- A. At-least-once persistence with duplicate evidence retained and reconciled.
- B. At-most-once persistence, where ambiguous writes remain quarantined.
- C. Exactly-once logical persistence using an approved stable capture/idempotency key and atomic commit strategy.

Impact/risk: Current RawLog Library multi-file writes do not prove any of these guarantees. C requires an idempotency key and atomicity design; no such key is inferred here. Until decided, a retry success does not prove exactly-once.

### CC-CR07 — Outcome / Aggregate boundary
Choose:
- A. Map only firmware COMPLETE to Measurement Outcome COMPLETE; all other/unknown terminal states remain non-COMPLETE.
- B. Define a fuller explicit mapping for STOP/TIMEOUT/ERROR/disconnect/cancel/interruption.
- C. Keep outcomes opaque and exclude from Aggregate until each mapping is separately approved.

Impact/risk: A is conservative but leaves several terminal categories unmapped. B is expressive but requires event semantics from CC-CR01. C avoids false eligibility but blocks Aggregate admission for unknown states. Session Lifecycle must remain independent in every option.

## Current Gate decision

- Evidence inventory for CR-01..CR-06: completed to the extent of the identified repository, spec, test, Issue, PR, and cited external firmware sources.
- Contract completeness: NOT COMPLETE; gaps are explicitly classified above.
- New specification or implementation: NOT STARTED; awaits Central Command decisions and separate authorization.
- Physical 5A E2E / discharge: NOT RUN; Issue #16 separate gate; explicit user authorization required.
- PR #218: must remain OPEN / DRAFT / UNMERGED. Code acceptance at exact HEAD `91c635dd5c129633898566adf929a8dc2f7386ab` remains intact and is not reopened by this report.

