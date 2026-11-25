# Battery Capture Contract — Logical Contract & Implementation Plan

- Date: 2026-11-25
- Authority: Central Command decision, PR #218 comment #7161905985
- Evidence baseline: `docs/battery_capture_contract_evidence_recovery_report.md`, commit `db7961832aabafa84eff7b6b3f97b377e3041394`
- Accepted Battery code baseline: PR #218 exact HEAD `91c635dd5c129633898566adf929a8dc2f7386ab`
- Document branch: `docs/battery-capture-contract-logical-plan-20261125`
- Purpose: record the seven logical decisions, current implementation/test status, fail-closed behavior, and a proposed implementation/test plan for separate approval.
- Revision: v3 consolidated consistency pass responding to Central Command instructions #7173638386 and #7173763360; no implementation authorization is implied.

> **Document hierarchy and current authority (Central Command instruction #7173763360):** Sections §8–§11 are historical proposals, candidate inventories and planning notes only. They are not current task instructions, design authority, or implementation permission. The controlling statement of current implementation feasibility, blocked work, stop conditions, approvals and status is §14.1–§14.5. Where earlier sections conflict with §14, §14 controls. In particular, Capture Key design, Capture-level idempotency/retry, Capture boundary/assembly, formal Owner Envelope persistence, and Battery-specific RawLog reconciliation remain BLOCKED or NOT AUTHORIZED as specified in §14; do not execute old P5 or test-inventory proposals.
- **This document does not authorize implementation.** No source code, Firmware, DB schema/DDL/Migration, DB data, main branch, or hardware was changed.

## 1. Authority and non-regression boundaries

The following Central Command decisions are authoritative for this contract:

- PR #218 comment #7161905985: CC-CR01 through CC-CR07.
- PR #218 review #6056751043: accepted Battery code scope at exact HEAD `91c635dd5c129633898566adf929a8dc2f7386ab`.
- Issue #207 comment #7101200440: DB GL-04 Scope Key / RawLog Reference / Sample Reference mapping. This mapping is already answered; no DB re-query is part of this plan.

Explicitly out of scope for re-review:

- CH1 / CH2 are independent measurement streams; STARTALL is a control operation only.
- No cross-channel average, sum, or fallback.
- Selected-channel Voltage or Current 0.0 remains Validity UNKNOWN and fail-closed; raw evidence is unchanged; non-selected-channel zero does not invalidate the selected channel.
- PR #218 A1-A7, V1/V2, Scope Key all-row checks and registration-time Scope Key revalidation remain accepted.
- No change to the existing A7 same-payload no-op / different-payload Conflict decision.

## 2. Status vocabulary

Status columns are deliberately independent:

- **DECIDED**: logical rule approved by Central Command.
- **DOCUMENTED**: recorded in this logical contract document.
- **IMPLEMENTED**: current accepted code implements the approved rule end-to-end.
- **TESTED**: automated tests exercise the approved rule, not merely a nearby legacy behavior.
- **NOT RUN**: required physical/device/E2E verification has not been performed.

A decision or documentation entry does not imply implementation or test completion.

## 3. Capture Contract logical matrix

| ID | Logical contract / decision | DECIDED | DOCUMENTED | IMPLEMENTED at accepted HEAD | TESTED at accepted HEAD | NOT RUN / unresolved |
|---|---|---|---|---|---|---|
| CC-CR01 Lifecycle | Preserve Firmware-origin events as observed; create Host-origin CANCEL / INTERRUPTED separately; START request, ACK, first DATA, STOP request, terminal DATA are distinct events; unprovable ACK correlation stays UNKNOWN. | YES | YES | PARTIAL: command send / DATA parse / subset of status handling exist; no durable complete event journal or formal event-to-Capture linkage. | PARTIAL: parser and Anonymous disconnect/retry tests cover selected behavior; new source-aware event journal/mapping not tested. | Device lifecycle E2E; deployed Firmware equivalence; ACK correlation. |
| CC-CR02 COMPLETE | Firmware COMPLETE means voltage-cutoff terminal fact only. Benchmark/Aggregate require a separate Quality/Eligibility=PASS. No minimum Sample count, required record set, or gap tolerance is invented. If eligibility depends on an undefined condition, UNKNOWN / NOT ELIGIBLE. | YES | YES | PARTIAL: current COMPLETE flag and selected-row validity checks exist; independent full Quality/Eligibility gate does not. | PARTIAL: selected-channel validity and 0.0 fail-closed tests exist; new Outcome-vs-Eligibility boundary is not fully tested. | Minimum Sample count / required evidence / gap criteria remain undefined; physical COMPLETE trace not run. |
| CC-CR03 Ordering | Suspected order/duplicate/gap anomalies are quarantined with Raw Evidence preserved. Equal elapsed_ms alone is not proof of duplication. No automatic deduplication. Arrival-order vs elapsed-order conflict is UNKNOWN / Quarantine, not repaired by sorting. No gap or duplicate threshold without evidence. | YES | YES | NO/PARTIAL: current analysis sorts by elapsed time; no complete anomaly detector or quarantine gate. | NO for the new policy; existing sorting/analysis tests do not prove anomaly quarantine. | Sequence absent; duplicate identity and gap threshold undefined; no physical cadence evidence. |
| CC-CR04 RawLog | Raw Serial Byte Stream is canonical evidence and receives SHA-256 over original received bytes. Decoded Text / Parsed Records are derived representations, optionally with separate hashes. Preserve DATA and control/diagnostic frames within the Capture boundary, including ACK/INFO/DEBUG/ERROR; do not alter LF/CRLF or undecodable bytes. | YES | YES | NO: current receive path decodes UTF-8 with replacement; RawLog stores decoded text; frame coverage is partial; raw-byte hash and complete identity linkage are not implemented. | NO for byte-exact preservation/hash/linkage; existing text-line tests cover only decoded text behavior. | Physical source-byte equivalence and capture boundary/correlation proof. |
| CC-CR05 Time | Device elapsed_ms is authoritative within a Capture. Host wall-clock is separate offset-aware metadata only; no conversion or synchronization claim. Do not synthesize Sequence. No millis rollover reconstruction or STARTALL skew inference without platform/device evidence. | YES | YES | PARTIAL: elapsed_ms parsing exists; host start timestamp is currently local naive time in the reviewed path; no approved dual-clock metadata contract. | PARTIAL: parser conversion tested; UTC-offset metadata, rollover and skew behavior not tested. | Target MCU rollover details, physical skew and clock accuracy. |
| CC-CR06 Partial/Retry | Capture-wide exactly-once / idempotency is not authorized: no Capture Key, alias, or Capture-level retry may be designed or implemented by Battery under the current decision. Existing A7 and specifically accepted DB/Anonymous retry behavior remain separate and unchanged. Uncertain partial RawLog state follows DB Main §8 / §14.3 and remains PENDING_RECOVERY / QUARANTINED. | YES | YES | NO for Capture-wide persistence; existing separate retry protections remain as previously accepted. | Existing A7/V1 tests remain accepted; Capture-wide tests are BLOCKED / NOT RUN. | Reopen only through a future common identity change proposal backed by new evidence and explicit Central Command direction; no current Battery action. |
| CC-CR07 Outcome/Aggregate | Map observed event source to Outcome table below. Session Lifecycle is independent. Aggregate requires Outcome=COMPLETE AND independent Quality/Eligibility=PASS. UNKNOWN, INCOMPLETE, STOP, ERROR, CANCEL, Quarantine are excluded. Legacy Session result is not a formal Outcome Envelope. | YES | YES | PARTIAL: legacy completed/result fields exist; formal independent Outcome envelope, event mapping and Aggregate gate are not implemented end-to-end. | PARTIAL: local COMPLETE and validity tests exist; full event-to-Outcome and Aggregate rejection matrix is not tested. | Real E2E / Aggregate acceptance remains NOT RUN. |

## 4. Normative event-to-Outcome table (CC-CR07)

| Observed event | Origin | Measurement Outcome |
|---|---|---|
| DATA state = COMPLETE | Firmware | COMPLETE |
| DATA state = STOP | Firmware | STOP |
| DATA state = TIMEOUT | Firmware | INCOMPLETE |
| ERROR frame observed within the Capture boundary and proven correlated to that Capture | Firmware | ERROR |
| ERROR frame outside a proven Capture boundary, or with unproven Capture correlation | Firmware diagnostic event | UNKNOWN (retain diagnostic Raw Evidence; do not attach it to a Measurement Outcome) |
| User-requested cancellation | Host | CANCEL |
| Disconnect | Host-observed transport event | INCOMPLETE |
| Process interruption | Host | INCOMPLETE |
| Unknown event, unprovable correlation, or insufficient evidence | Explicitly retain origin/unknown status | UNKNOWN |

Rules:

1. Record the observed event and its origin; do not relabel a Host event as Firmware-origin.
2. START request, ACK receipt, first DATA, STOP request, and terminal DATA are distinct observations.
3. ACK receipt alone is not successful Capture completion. If ACK cannot be tied to a Capture with evidence, its Capture correlation is UNKNOWN.
4. A Firmware ERROR frame maps to Measurement Outcome=ERROR only when it is observed within the proven Capture boundary AND evidence proves its association with that specific Capture. Temporal proximity, a preceding START request, or arrival order alone is not sufficient correlation evidence.
5. A Firmware ERROR that is outside the Capture boundary or cannot be proven to belong to a specific Capture is retained as a Firmware-origin diagnostic Raw Evidence event. Its Measurement Outcome correlation remains UNKNOWN; it must not be attached to a Measurement as ERROR.
6. Host process interruption is a Host event type `INTERRUPTED`; the resulting Measurement Outcome is `INCOMPLETE`. These are different layers: event identity/source versus Measurement Outcome. Do not store or report `INTERRUPTED` as a Firmware event or as an Outcome value.
7. Session CLOSED never implies Measurement Outcome COMPLETE.
8. Aggregate admission requires both Outcome=COMPLETE and Quality/Eligibility=PASS. All other outcomes and Quarantine are excluded.

## 5. Quality / Eligibility rules (CC-CR02 / CC-CR03)

The following already accepted checks remain mandatory and are not reopened:

- Selected-channel rows are validated; missing, nonnumeric, non-finite values fail closed.
- Selected-channel Voltage or Current 0.0 remains Validity UNKNOWN and blocks derived Benchmark/Aggregate acceptance.
- Non-selected-channel 0.0 does not affect selected-channel validity.
- Raw Measurement and RawLog evidence is never silently corrected, filtered, or overwritten.

Additional approved contract behavior:

- Device Outcome=COMPLETE is necessary but not sufficient for Benchmark/Aggregate admission.
- Minimum Sample count, mandatory event/record set, and gap tolerance have no evidence-backed values today. Any Eligibility decision dependent on those undefined conditions is UNKNOWN / NOT ELIGIBLE.
- Preserve all Samples; do not silently omit invalid rows to manufacture a complete result.
- Arrival order must not be replaced by sorted elapsed order as if that proved source order. If observed arrival order conflicts with elapsed order, mark ordering quality UNKNOWN and Quarantine the Capture.
- Equal elapsed_ms by itself is not a duplicate proof. Do not deduplicate based on elapsed_ms equality.
- Where a duplicate/gap suspicion cannot be resolved because Sequence/cadence evidence is absent, preserve the raw records and keep quality UNKNOWN / Quarantine rather than inventing a threshold.
- Quarantine prevents Benchmark and Aggregate admission; it does not delete or rewrite source evidence.

## 6. RawLog / timestamp / retry contract details

### 6.1 RawLog canonical representation

- Canonical input: exact serial bytes received by the host.
- Canonical digest: SHA-256 over those exact bytes, before decoding, newline normalization, replacement, or parsing.
- Derived forms: decoded text and parsed records are downstream representations. They may carry their own digest, but neither replaces the raw-byte digest.
- Preserve LF, CRLF, invalid UTF-8 bytes, and all observed frame types in the Capture boundary. No frame is silently filtered.
- Current implementation remains classified as decoded-text / partial-frame coverage until byte-level implementation and tests are separately accepted.
- Where Capture boundaries or ACK correlation cannot be proven, retain the byte stream at the strongest proven scope and label per-Capture association UNKNOWN; do not manufacture a Capture link.

### 6.2 Time and sequence

- Device elapsed_ms is the authoritative within-Capture elapsed axis.
- Host wall-clock is metadata only and must include an explicit UTC offset when stored.
- Host time is not the exact UTC occurrence time of a Device Sample unless a synchronization model is separately evidenced and approved.
- Do not synthesize sequence numbers.
- Do not infer millis rollover reconstruction or STARTALL channel start skew. If a decreasing elapsed value creates an order conflict under currently available evidence, keep the source record and classify ordering quality UNKNOWN / Quarantine; do not silently unwrap or reorder.

### 6.3 Capture-wide retry / persistence — current stop condition

- Central Command decision #7172052263 rejects Capture=Measurement 1:1, rejects `MeasurementID` as a Capture Key, and prohibits substituting `PhysicalRunID`, `ScopeKey`, `OperationID`, or `ReceiptID`, or creating a new Capture ID/issuer.
- Therefore Battery must not design or implement a Capture/Idempotency Key, Capture-wide exactly-once semantics, or Capture-keyed retry under the current authority. This work is **BLOCKED**; the former target wording is superseded.
- The existing A7 Benchmark-result idempotency decision and specifically accepted DB/Anonymous retry protections remain separate and unchanged; they do not establish Capture-wide idempotency.
- For uncertain partial RawLog persistence, follow DB Main §8 / §14.3: preserve evidence and classify PENDING_RECOVERY / QUARANTINED. Do not delete, overwrite, regenerate IDs, or perform a mutating retry on uncertain state. Battery must not invent a reconciliation algorithm.
- Reconsider Capture-wide identity only through a future common identity change proposal backed by new evidence and explicit Central Command direction. See §14.2 and §14.4.

## 7. Current implementation delta and fail-closed behavior

| Contract area | Existing accepted behavior / gap | Required behavior before formal acceptance | Fail-closed behavior while not implemented |
|---|---|---|---|
| Event journal | Host parser reads DATA and selected status paths; ACK/INFO/DEBUG/ERROR are not durably journaled end-to-end. | Preserve observed events with source, event type, receive time, raw-byte reference and proven Capture correlation. | Missing/unprovable event or ACK correlation = UNKNOWN; no completion inferred from ACK or silence. |
| Outcome | Legacy completed/result fields exist; no complete independent Outcome Envelope. | Implement CC-CR07 mapping, keeping Session Lifecycle separate. | Outcome UNKNOWN / non-COMPLETE; exclude from Aggregate. |
| Quality | Existing selected-channel validation exists; no complete sample-count/gap/order Eligibility gate. | Separate Quality/Eligibility result from Device Outcome. | Undefined minimum evidence / gap policy = UNKNOWN / NOT ELIGIBLE. |
| Ordering | Current analysis sorts elapsed values; no full arrival-order / duplicate / gap quarantine. | Retain arrival order and detect only evidence-supported anomalies; quarantine. | Do not sort into a claim of normal source order; no dedup; uncertain quality excluded. |
| RawLog | Current serial path decodes with replacement; RawLog Library stores decoded text; control frames may be omitted. | Byte-oriented receive, immutable raw-byte object, SHA-256, derived text/parsed forms, frame coverage and references. | Existing objects remain decoded-text/partial coverage; never claim byte-exact or full-frame evidence. |
| Timestamp | Device elapsed_ms parsed; host timestamp path is not offset-aware. | Preserve elapsed_ms as authoritative; store host time separately with UTC offset. | No clock conversion, rollover reconstruction, or precise inter-channel skew claim. |
| Retry | Current selected retry paths and A7 idempotency exist; multi-file RawLog is not atomic and no capture-wide key. | Stable key + identical no-op / different Conflict + partial-write quarantine + fault injection. | Uncertain write state = Quarantine; no exactly-once claim. |
| Aggregate | Legacy COMPLETE registration path exists; no complete Outcome AND Quality gate. | Require Outcome=COMPLETE and Quality/Eligibility=PASS, with raw evidence linkage. | Exclude every unknown, partial, invalid, or quarantined capture. |

## 8. Proposed implementation plan — historical proposal only

> **Not current instructions.** This section and §§9–§11 predate the final Central Command stop conditions. They are retained for traceability, not as an execution backlog. Any candidate, phase, test, or file inventory below is superseded where inconsistent with §14.1–§14.5. No item in §§8–§11 is authorized merely by appearing here. Capture Key / Capture-wide retry work in old Phase P5 is BLOCKED and must not be pursued by Battery.

This is a planning proposal only. It does not authorize code changes. The sequence avoids firmware and DB schema changes and keeps the accepted PR #218 code baseline intact.

### Phase P0 — design closure (Central Command decision #7172052263)

P0-1 through P0-4 are now **DECIDED**. Do not reopen them as questions or infer additional semantics:
1. Capture start/end: no normative boundary is assigned to START request, ACK, first DATA, STOP request, silence, disconnect, application exit, or last Sample. Keep observations distinct. If correlation/boundary cannot be proven, retain only the strongest supported evidence as UNKNOWN/opaque, do not assert Capture completeness or Aggregate eligibility. Firmware build/hash confirmation is conditional only if a future device-specific equivalence claim is made.
2. Capture Key: Capture is not approved as 1:1 with Measurement; MeasurementID is not approved as Capture Key. Do not substitute PhysicalRunID, ScopeKey, OperationID, or ReceiptID. Do not create a new Capture ID or issuer. Capture-level exactly-once/idempotency remains NOT IMPLEMENTED / NOT GUARANTEED; any function requiring a Capture Key is blocked.
3. DB representation: Outcome and Quality/Eligibility remain separate. Without an explicit Owner Envelope representation, preserve opaque/UNKNOWN/excluded; reject formal Benchmark registration and exclude from Current Aggregate. Do not infer from Session Lifecycle, legacy Session result/status, Measurement Status, or add/change DB fields. Issue #207 #7101200440 mapping remains closed.
4. Partial RawLog reconciliation: DB Main §8 / §14.3 is the governing common storage contract. Apply its temp-write, fsync, SHA-256 read-back, collision, atomic rename, directory fsync, final read-back, and Journal commit evidence sequence. Any missing/mismatched/uncertain Body/Metadata/Index/Reference/Journal state is PENDING_RECOVERY / QUARANTINED; no delete, overwrite, ID regeneration, or retry that mutates uncertain evidence. Legacy logs without proof remain legacy evidence only.
5. These decisions close the logical stop conditions, not implementation authorization. Obtain a separate explicit Central Command approval before any source changes.

### Phase P1 — host event capture and source-aware lifecycle

Candidate files:
- `battery_system/serial.py`
- `ui/battery_tab_ui.py`
- new focused event/capture contract module only if approved
- `tests/test_battery_tab_safety.py`
- `tests/test_anonymous_mode.py`
- new `tests/test_battery_capture_contract.py` if approved

Planned work:
- Preserve received bytes before text decoding.
- Record START request, observed ACK, first DATA, STOP request, terminal DATA, Host CANCEL, Host INTERRUPTED and disconnect as distinct events.
- Preserve origin labels and UTC-offset-aware host event timestamps.
- Keep ACK-to-Capture correlation UNKNOWN unless a stable correlation is evidenced.
- Do not change Firmware protocol or claim unsupported Firmware events.

### Phase P2 — immutable Raw Serial Bytes and hash

Candidate files:
- `battery_system/serial.py`
- `raw_log_library/manager.py`
- `measurement/battery_measurement_parser.py`
- `tests/test_battery_measurement_parser.py`
- `tests/test_anonymous_mode.py`
- new `tests/test_raw_log_byte_integrity.py` if approved

Planned work:
- Introduce byte-preserving storage without converting the canonical source to text.
- Compute SHA-256 over original received bytes.
- Derive decoded text / parsed records separately.
- Preserve LF, CRLF, invalid UTF-8, and control/diagnostic frames.
- Add stable identity and partial-write quarantine only after Capture Key design is approved.
- Do not claim per-Capture completeness where the Capture boundary is not proven.

### Phase P3 — ordering and Quality / Eligibility

Candidate files:
- `measurement/battery_measurement_parser.py`
- `analysis/battery_benchmark.py`
- `analysis/battery_benchmark_session.py`
- `analysis/battery_benchmark_service.py`
- `ui/battery_tab_ui.py`
- `tests/test_battery_benchmark.py`
- `tests/test_battery_benchmark_session.py`
- new `tests/test_battery_capture_quality.py` if approved

Planned work:
- Preserve source arrival order alongside elapsed_ms.
- Detect arrival/elapsed order contradictions without sorting them away.
- Do not deduplicate equal elapsed_ms.
- Keep gap/duplicate rules UNKNOWN until cadence / identity evidence supports a deterministic rule.
- Add independent Quality/Eligibility state; unknown required criteria remain NOT ELIGIBLE.
- Preserve existing selected-CH validity and 0.0 fail-closed behavior unchanged.

### Phase P4 — Outcome and Aggregate admission

Candidate files:
- `ui/battery_tab_ui.py`
- `analysis/battery_benchmark.py`
- `analysis/battery_benchmark_session.py`
- `analysis/battery_benchmark_service.py`
- `database/repository/battery_repository.py` only if the already-approved existing persistence contract supports the change without schema modification
- `tests/test_battery_tab_safety.py`
- `tests/test_battery_benchmark_session.py`
- new `tests/test_battery_outcome_aggregate_gate.py` if approved

Planned work:
- Implement the exact CC-CR07 event-to-Outcome table.
- Keep Outcome separate from Session Lifecycle and legacy Session result fields.
- Require Outcome=COMPLETE AND Quality/Eligibility=PASS for Aggregate admission.
- If formal Outcome / Quality representation cannot be persisted using the approved existing contract, leave the capture opaque/excluded and request a separate DB design/implementation authorization. Do not alter schema.

### Phase P5 — historical proposal; BLOCKED by current decision (not an active task)

Candidate files:
- `raw_log_library/manager.py`
- approved Capture/Operation/Receipt integration point (must be identified before implementation)
- `tests/test_anonymous_mode.py`
- new `tests/test_raw_log_retry_atomicity.py` if approved

Planned work:
- Align the stable Capture Key with existing Physical Run / Operation / Receipt identity and idempotency rules.
- Identical content retry = no-op; different content = Conflict.
- Inject failures after each body/metadata/index persistence boundary.
- Quarantine partial writes with uncertain state; reconcile before marking successful.
- Preserve the existing A7 no-op/Conflict behavior; do not replace it with a new revision policy.

## 9. Proposed regression test plan

The tests below are proposed and **NOT RUN**. They are not evidence of current implementation.

| Test group | Required cases | Expected result |
|---|---|---|
| Lifecycle event provenance | Firmware ACK/DATA/ERROR; Host CANCEL/INTERRUPTED; disconnect; ACK with no proven Capture correlation; ERROR before/outside boundary; ERROR inside boundary but uncorrelated; correlated in-boundary ERROR | Source and event preserved; ACK correlation unknown unless proven; only proven in-boundary ERROR maps to Outcome ERROR; uncorrelated ERROR remains diagnostic Raw Evidence with Outcome correlation UNKNOWN; Host INTERRUPTED event maps separately to Outcome INCOMPLETE. |
| Outcome mapping | COMPLETE, STOP, TIMEOUT, Firmware ERROR, Host CANCEL, disconnect, process interruption, unknown event | Exact CC-CR07 mapping; Session CLOSED does not alter Outcome. |
| COMPLETE vs Quality | COMPLETE with unknown minimum count / missing required event / selected 0.0 / non-finite row | Device Outcome remains COMPLETE where observed; Quality UNKNOWN/FAIL; no Benchmark/Aggregate admission. |
| Order | Monotonic arrival; arrival order conflicts with elapsed order; duplicate suspicion; equal elapsed only | Contradiction quarantined; equal elapsed alone is not deduplicated; all raw rows preserved. |
| Gap | Known gap evidence and unknown cadence | No guessed numeric tolerance; unresolved gap quality UNKNOWN / Quarantine. |
| Raw byte fidelity | LF, CRLF, mixed endings, invalid UTF-8, NUL/arbitrary bytes, DATA + ACK/INFO/DEBUG/ERROR | Stored raw bytes exactly equal input; SHA-256 matches original byte array; derived text cannot mutate raw bytes. |
| RawLog identity | Raw byte object, decoded derivative, parsed derivative, Measurement / Sample references | Linkage follows Issue #207 mapping; no link invented where correlation is unknown. |
| Time | elapsed_ms conversion; host timestamp with offset; no synchronization; rollover boundary without platform evidence | Device elapsed remains canonical; host time remains metadata; no fabricated sequence or wrap reconstruction. |
| Retry | same key/same content; same key/different content; failure after each file write; retry after uncertain partial write | No-op; Conflict without overwrite; partial state quarantined; no exactly-once claim until reconciliation. |
| Aggregate gate | All Outcome values × Quality PASS/UNKNOWN/FAIL × Quarantine | Only Outcome COMPLETE + Quality PASS enters Aggregate. |
| Regression protection | CH1/CH2 independent; selected CH 0.0 UNKNOWN; non-selected CH zero unaffected; A1-A7; V1/V2; Scope checks | Existing accepted tests remain passing; no re-review or behavioral regression. |

## 10. Change-file inventory (proposed, not modified)

| File / path | Planned responsibility | Approval / dependency |
|---|---|---|
| `battery_system/serial.py` | Byte-preserving serial receive; decoded parsing as derivative; source frame observations. | Host-only implementation approval. No Firmware change. |
| `ui/battery_tab_ui.py` | Capture event lifecycle, host events, offset-aware host metadata, Outcome/Quality gating. | Host-only implementation approval. |
| `raw_log_library/manager.py` | Immutable raw-byte object, SHA-256, derived representations, partial-write quarantine and retry identity. | Capture Key / persistence design approval. |
| `measurement/battery_measurement_parser.py` | Parse from raw bytes while retaining source representation and ordering evidence. | Host-only implementation approval. |
| `analysis/battery_benchmark.py` | Independent Quality/Eligibility and Aggregate admission gate. | Logical contract approved; implementation still needs separate approval. |
| `analysis/battery_benchmark_session.py` | Outcome/Quality-aware session extraction without equating Session Lifecycle and Outcome. | Host-only implementation approval. |
| `analysis/battery_benchmark_service.py` | Enforce Outcome/Quality and preserve existing Scope validation/transaction safety. | Host-only implementation approval; preserve accepted checks. |
| `database/repository/battery_repository.py` | Only if required and supported by already-approved persistence fields; no schema edits. | Conditional; stop and request separate DB authorization if schema change is required. |
| `tests/test_battery_capture_contract.py` (new) | Event provenance and lifecycle mapping. | Test-only addition after scope approval. |
| `tests/test_raw_log_byte_integrity.py` (new) | Byte fidelity and raw-byte SHA-256. | Test-only addition after scope approval. |
| `tests/test_battery_capture_quality.py` (new) | Ordering, gap/duplicate uncertainty, Eligibility and Quarantine. | Test-only addition after scope approval. |
| `tests/test_battery_outcome_aggregate_gate.py` (new) | Outcome mapping and Aggregate matrix. | Test-only addition after scope approval. |
| `tests/test_raw_log_retry_atomicity.py` (new) | Capture key, no-op/Conflict, partial-write fault injection. | Capture Key design approval first. |

No Firmware source path, DB schema/DDL, Migration, DB data, main branch, or physical test is in the proposed change list.

## 11. Additional approvals and dependencies

| Dependency | Why required | Current status |
|---|---|---|
| Central Command implementation authorization | Logical decisions are approved, but implementation is explicitly not authorized by comment #7161905985. | REQUIRED / NOT GRANTED |
| Capture Key design | Central Command rejected Capture=Measurement 1:1 and use of MeasurementID as Capture Key; no replacement key may be invented. | DECIDED STOP / NO KEY / Capture-key-dependent work BLOCKED |
| DB schema/persistence authorization | Only if formal Outcome/Quality/RawLog references cannot be represented in existing approved fields. | NOT REQUESTED; no schema change planned |
| Firmware Owner confirmation | Deployed firmware identity and platform-specific millis behavior; no firmware change requested. | CONDITIONALLY REQUIRED for device-specific claims |
| User / equipment authorization | Any physical serial capture, real 5A E2E or discharge. | NOT GRANTED; Issue #16 remains NOT RUN |

Do not re-query DB for the GL-04 mapping. If the existing mapping does not permit a required persistence behavior, stop and submit the exact gap to Central Command; do not add fields or infer substitutes.

## 12. Gate and completion state

- CC-CR01 through CC-CR07: **DECIDED** by Central Command comment #7161905985.
- This logical contract table and proposed plan: **DOCUMENTED** by this document.
- Implementation of the full Capture Contract: **NOT COMPLETE**.
- New tests described in Section 9: **NOT RUN**.
- Physical 5A RawLog → Measurement → Benchmark E2E / discharge: **NOT RUN** (Issue #16; explicit user authorization required).
- Firmware, DB schema/DDL/Migration, DB data, main, hardware: **UNCHANGED**.
- PR #218: must remain **OPEN / DRAFT / UNMERGED** at accepted code HEAD `91c635dd5c129633898566adf929a8dc2f7386ab`. This document does not update or reopen the accepted code PR.

**Current gate:** P0-1 through P0-4 are decided and documented. The host-side plan is now classified by feasibility under those decisions. No source implementation is authorized until a separate explicit Central Command approval is received.


## 13. P0 design-closure disposition — Central Command review #7164298834

- Review authority: PR #218 comment #7164298834.
- This section classifies the four P0 questions from existing source / approved logical contracts. It does not create a new Capture rule, identity, DB field, recovery algorithm, or implementation authorization.
- Evidence baseline: accepted Battery code HEAD `91c635dd5c129633898566adf929a8dc2f7386ab`; DB logical draft branch `db/v0.8.3-followup-remediation-20261121`, Main blob `e1cdac6f75225877034c70d6023de5f6c7558e30`; Issue #207 comment #7101200440; PR #218 accepted code and this document's v2 revision.

### P0-1 — Capture start / end boundary

**Classification**
- Existing observable markers: **RECOVERABLE**.
- Normative rule that declares which marker opens/closes a Capture: **NO_CURRENT_BASIS**.
- Equivalence between the cited external Firmware source and the deployed device: **CONDITIONALLY_RECOVERABLE** (Firmware Owner / device identity evidence required).

**Verified facts**
- At accepted Battery HEAD, `BatteryTab.start_channel()` records a Host local timestamp, clears the new in-memory buffer only after the prior-capture safety gate, and sends START. The timestamp is not an offset-aware Firmware start timestamp and is not evidence that the device accepted START.
- `BatterySerial.start()` sends `START1` / `START2` / `STARTALL`; `read_lines()` decodes incoming bytes to UTF-8 with replacement; `parse_data()` parses DATA rows only.
- `poll_serial()` appends parsed DATA rows. It does not persist a durable event journal for START request, ACK, first DATA, STOP request, and terminal DATA as separate linked events. The current terminal UI recognition does not establish a complete mapping for all Firmware states (notably literal STOP / TIMEOUT).
- Firmware command/state vocabulary and the distinctions START request, ACK, first DATA, STOP request, terminal DATA are documented in Issue #16 #7080826275 and Central Command decision #7161905985. CC-CR01 explicitly forbids treating ACK alone as completion and requires UNKNOWN when ACK-to-Capture correlation cannot be proven.
- DB Main §14.2 requires UNKNOWN when start/end existence or ordering cannot be established; elapsed silence, application exit, or last value must not be used to infer end.

**Disposition**
- We can retain each observed marker as a distinct fact, with its actual source and available timestamp.
- We cannot currently declare “Capture begins at START request”, “Capture begins at ACK”, or “Capture begins at first DATA”; likewise we cannot declare a universal end boundary from silence, STOP request, disconnect, or application exit.
- Until an approved boundary rule and correlation evidence exist, no per-Capture completeness assertion is made. Raw bytes/lines, if captured, remain opaque evidence; Measurement Outcome / eligibility remains UNKNOWN or INCOMPLETE as supported by explicit evidence, and Aggregate admission is blocked.
- No user confirmation is requested now. If a future implementation requires deployed-device equivalence, Firmware Owner must identify the deployed firmware build/hash and confirm its event behavior. This is evidence confirmation, not permission to modify Firmware or run hardware.

**Completion condition:** Central Command accepts a boundary rule based on an identified observable event and correlation mechanism, or explicitly accepts the UNKNOWN/opaque stop condition. No rule is inferred by Battery.

### P0-2 — Capture Key and identity alignment (final decision; closed)

**Classification**
- Current common identity registry / issuer assignments: **RECOVERABLE** and documented; see the existing DB Main references below.
- Capture=Measurement 1:1 and `MeasurementID` as Capture Key: **DECIDED NOT APPROVED**.
- Any replacement Capture Key, alias, or Battery-created identity/issuer: **DECIDED NOT ALLOWED** under the current authority. No further Battery-side design is pending.

**Verified facts retained from the evidence review**
- DB Main §5.1 assigns `MeasurementID`, `RawLogObjectID`, and `SampleReferenceID` to `CAPTURE_IDENTITY_AUTHORITY`; `RawLogReferenceID` to `EVIDENCE_STORAGE_AUTHORITY`; `PhysicalRunID` / `LogicalSessionID` / `DBRunID` to `RUN_MANAGER`; `OperationID` to `OPERATION_AUTHORITY`; and `ReceiptID` to `RECEIPT_AUTHORITY`.
- DB Main §5.3 defines RUN_SCOPE identity as `(PhysicalRunID, ScopeKey)`; it has no independent RunScopeID. Measurement Envelope `PhysicalRunID` + `ScopeKey` is the direct RUN_SCOPE reference (Issue #207 comment #7101200440 and Main §7.1).
- These existing identities do not establish a Capture identity or Capture↔Measurement cardinality.

**Final disposition — Central Command decision #7172052263**
- Do not treat one Battery Capture as normatively identical to one Measurement.
- Do not use `MeasurementID` as a Capture Key.
- Do not substitute `PhysicalRunID`, `ScopeKey`, `OperationID`, or `ReceiptID`; do not create a new Capture ID or issuer.
- Capture-wide exactly-once / idempotency / key-based retry is **BLOCKED** and remains NOT IMPLEMENTED / NOT GUARANTEED.
- Reconsideration is possible only through a future common identity change proposal supported by new evidence and explicit Central Command direction. This is not a current Battery task.

**Completion condition:** Met for the current stop condition: Central Command has explicitly rejected the proposed equivalence and prohibited replacement identities. No further decision request or Battery-side design is required now.

### P0-3 — Existing DB contract representation for Outcome / Quality / RawLog

**Classification**
- RUN_SCOPE, RawLog Object / Reference, Sample Reference, and Measurement Sample Link field mapping: **RECOVERABLE / DECIDED**.
- Logical Outcome vocabulary and Aggregate admission rule: **RECOVERABLE / DECIDED**.
- Field-level persistence mapping for Battery Outcome and independent Quality/Eligibility in the currently approved common Envelope / legacy SQLite implementation: **CONDITIONALLY_RECOVERABLE**; not proven implementable in the current legacy schema without a separately approved persistence representation.

**Verified facts**
- Issue #207 comment #7101200440 is the authoritative completed mapping; it must not be re-queried:
  - RUN_SCOPE = `(PhysicalRunID, ScopeKey)`; Measurement Envelope carries both fields.
  - RawLog Object = `RawLogObjectID + ContentHashSHA256`.
  - RawLog Reference = `RawLogReferenceID + RawLogObjectID + RawLogObjectContentHash`; reference hash must equal the Object hash.
  - Measurement Envelope references `RawLogReferenceID`; Sample Reference carries `SampleReferenceID + RawLogReferenceID + SampleLocator`; Measurement Sample Link is `(MeasurementID, SampleReferenceID, Role, Ordinal)`.
- DB Main §7.0 / §7.1 / §14.2 defines Measurement Envelope information, RawLog reference chain, Outcome values, and the rule that formal COMPLETE requires the Device/Capture Owner contract's terminal evidence and required Samples. Unknown / unreceived Owner Payload Schema is opaque only.
- DB Main §14.2 decides the Outcome vocabulary (COMPLETE / STOP / ERROR / CANCEL / INCOMPLETE / UNKNOWN) and Aggregate gate. However, the minimum Measurement Envelope field list in §7.0 names `Measurement Status` and `Termination Reason`; it does not by itself specify an unambiguous persisted field mapping for the separate Outcome value and the Battery Quality/Eligibility result.
- The accepted legacy SQLite `measurement_session` / `measurement` path has no complete Scope / RawLog Reference / Object Hash / Sample Link persistence chain. The Battery registration path fails closed if required explicit Scope Key columns are absent. No DB schema change is authorized.

**Disposition**
- Treat the Issue #207 RawLog / Sample reference mapping as closed and do not reopen it.
- Preserve Outcome and Quality as separate logical concepts. Do not equate either with Session Lifecycle, legacy Session result/status, or each other.
- Where the existing approved external Measurement Envelope / Owner Payload cannot unambiguously represent Outcome and Quality/Eligibility, retain the data as opaque / UNKNOWN, reject formal Benchmark registration, and exclude it from Current Aggregate. Do not add SQLite columns, reinterpret `Measurement Status`, or create an implicit mapping.
- The RawLog reference chain is a known logical contract; it is not implemented end-to-end by the accepted Battery code. The current Battery RawLog manager's local `log_id` must not be assumed to be a DB `RawLogObjectID` or `RawLogReferenceID`.

**Completion condition:** Met for the current fail-closed boundary: Central Command has decided that, absent an explicit Owner Envelope representation, Outcome/Quality remain opaque/UNKNOWN/excluded and formal Benchmark/Aggregate admission is rejected. If an authoritative Owner Envelope schema is supplied in the future, review that exact source; do not re-query the closed GL-04 mapping.

### P0-4 — Partial RawLog write reconciliation

**Classification**
- Generic common storage acceptance evidence / criteria: **RECOVERABLE**.
- Exact reconciliation of the current Battery RawLog Library's multi-file partial-write states: **CONDITIONALLY_RECOVERABLE**; no current implementation evidence proves it.
- Any claim that current Battery RawLog writes are atomic / exactly-once: **NO_CURRENT_BASIS**.

**Verified facts**
- DB Main §8 / §14.3 specifies the common storage evidence sequence for a received object: write a temporary file; fsync; read back and verify SHA-256; check final-path collision; atomic rename; fsync parent directory; reopen final path and re-verify hash; record completion in Journal. On failure or power loss, preserve the partial state as PENDING_RECOVERY / QUARANTINED; do not delete or overwrite. Retry uses the same RawLog ID and expected hash; a different hash for the same ID is prohibited.
- DB Main explicitly says these are common storage requirements, not Battery-specific Capture semantics, and that successful storage alone does not prove Capture completion / Measurement Outcome=COMPLETE.
- At accepted Battery HEAD, `RawLogLibrary.register()` writes the decoded text body, then updates a JSON metadata store, then appends a CSV index. The inspected path does not establish a temp-file/fsync/atomic-rename/read-back-hash/Journal commit chain. The current record uses a library-allocated local `log_id`; no proof maps it to the DB RawLog Object / Reference IDs.
- The current Battery RawLog library has no capture-wide manifest or transaction record that proves all three local artifacts (body, metadata, index) form one committed Capture object after a crash at each boundary.

**Disposition**
- Reuse the existing DB common storage acceptance criteria; do not invent a Battery-specific alternative.
- For future accepted-object persistence, “complete” can only be asserted after the canonical object bytes and expected hash are read back and match, final-path collision checks pass, the RawLog Reference points to the matching Object ID/hash, and the required Journal/Source Commit evidence is durable and verified.
- If a crash leaves body / metadata / index / reference / Journal state incomplete or ambiguous, preserve all surviving evidence and classify PENDING_RECOVERY / QUARANTINED. Do not delete, rewrite, overwrite, regenerate IDs, or mark successful based only on the presence of one file.
- For existing legacy local logs, where no canonical byte hash and no durable commit/reconciliation record exist, report the exact observed files as legacy evidence only; do not retroactively assert atomicity, exact-once, or complete Capture status.
- Applying the generic process to the current Battery multi-file layout requires a separately approved implementation design that identifies the canonical object, its manifest/commit record, and fault-injection coverage. This is a design dependency, not implementation permission.

**Completion condition:** The common storage rule is decided and documented by DB Main §8 / §14.3. Battery-specific canonical-object/manifest/commit mapping and reconciliation are not approved; do not design or implement them under this instruction. Uncertain partial state remains PENDING_RECOVERY / QUARANTINED. Any future proposal requires separate explicit Central Command direction and approval.

### P0 overall status — superseded by Central Command decision #7172052263

| P0 item | Central Command decision | DECISION / DOCUMENT | IMPLEMENTATION | VERIFICATION | Remaining dependency |
|---|---|---|---|---|---|
| P0-1 Capture boundary | No normative start/end boundary; UNKNOWN/opaque if correlation cannot be proven | DECIDED / reflected | NOT IMPLEMENTED | NOT RUN | None for stop condition; Firmware build/hash only for future device-specific equivalence claim |
| P0-2 Capture Key | No Capture=Measurement 1:1; MeasurementID not a Capture Key; no new key/issuer | DECIDED / reflected | NOT IMPLEMENTED; key-dependent work blocked | NOT RUN | Future common identity change proposal only if evidence creates a need |
| P0-3 Outcome / Quality | Without explicit Owner Envelope representation, opaque/UNKNOWN/excluded; no legacy inference/schema changes | DECIDED / reflected | NOT IMPLEMENTED | NOT RUN | Future Owner Envelope schema evidence; GL-04 mapping remains closed |
| P0-4 Partial RawLog | DB Main §8 / §14.3 governs; uncertain states PENDING_RECOVERY / QUARANTINED | DECIDED / reflected | NOT IMPLEMENTED | NOT RUN | Separately approved canonical object/manifest/commit design and fault-injection tests |

**P0 status:** all four logical stop conditions are **DECIDED** by Central Command comment #7172052263. They are not open questions. This does not authorize implementation.

No source code, tests, Firmware, DB schema/DDL/Migration, DB data, main, or hardware were changed by this P0 assessment. PR #218 remains OPEN / DRAFT / UNMERGED at accepted code HEAD `91c635dd5c129633898566adf929a8dc2f7386ab`. Physical 5A E2E remains NOT RUN (Issue #16).


## 14. Final implementation feasibility plan — Central Command decision #7172052263

This section supersedes any earlier wording that requests a new P0 decision. P0-1 through P0-4 are closed as logical decisions. The classifications below describe only whether work is logically possible under those decisions; **none of these classifications grants implementation permission**.

### 14.1 Work that can be implemented within the decided boundaries (after separate approval)

| Workstream | Allowed implementation scope | Mandatory limit / fail-closed behavior |
|---|---|---|
| P1 — Host event observation | Preserve each actually observed Host/Firmware event as a distinct observation with source, event type, receive timestamp and original evidence where available. Record Host START/STOP requests separately from received ACK/DATA/terminal/diagnostic frames. | Do not declare Capture start/end; do not create Capture association from temporal proximity, order, ACK, silence, disconnect or last Sample. Uncorrelated events remain standalone UNKNOWN/opaque evidence. |
| P2 — Raw byte acquisition | Add byte-preserving receive/test seams and prove byte fidelity for the bytes actually delivered by the serial layer; derive decoded text separately without mutating source bytes. | This alone does not authorize a Capture RawLog Object, RawLog Reference, Sample Reference, Capture Key, per-Capture hash claim or formal Measurement linkage. If canonical object ownership/boundary cannot be proven, retain only unassociated evidence or stop before persistence. |
| P3 — Ordering evidence | Preserve observed arrival order and Device elapsed_ms as separate values; detect and report contradictions only where directly observable. | No generated sequence, automatic deduplication, sorting to normalize source order, invented gap/duplicate threshold, rollover reconstruction or Quality PASS. Unknown cadence/identity means Quality UNKNOWN / NOT ELIGIBLE. |
| P4 — Pure Outcome mapping | Implement/test a pure mapping for explicit, source-attributed events exactly as CC-CR07 specifies, including Host INTERRUPTED event vs Outcome INCOMPLETE and correlated in-boundary Firmware ERROR only. | No formal Outcome persistence, Benchmark registration or Aggregate admission unless an explicit Owner Envelope representation exists. Unknown correlation remains UNKNOWN. Outcome COMPLETE does not imply Quality PASS or prove Capture boundary. |
| Regression-only work | Add tests for the above fail-closed rules and preserve accepted CH1/CH2, selected-CH 0.0, A1-A7, V1/V2 and Scope Key behavior. | Tests must not require real hardware, alter DB schema/data, or weaken accepted behavior. New tests remain NOT RUN until separately authorized/executed. |

### 14.2 Work blocked by the P0 decisions (do not implement)

| Workstream | Why blocked | Stop condition |
|---|---|---|
| Capture-wide ID / exactly-once / idempotent retry | P0-2 explicitly rejects Capture=Measurement 1:1 and use of MeasurementID as Capture Key; no new ID or issuer is allowed. | Do not create Capture ID, alias an existing ID, or claim Capture-level exactly-once. |
| Capture start/end lifecycle and complete Capture assembly | P0-1 deliberately assigns no normative boundary. | Do not declare Capture started/ended/complete or bind uncorrelated frames/Samples into one Capture. |
| Formal RawLog Object / Reference / Sample Reference linkage to a Capture/Measurement | Requires proven ownership and Capture boundary; P0-1/P0-2 do not supply it. Existing GL-04 mapping defines the shape but does not prove a Battery Capture identity/link. | Do not invent links, IDs, SampleLocator, or ownership. Preserve only separately proven evidence. |
| Formal Outcome + Quality persistence, Benchmark registration and Aggregate admission | P0-3 requires an explicit Owner Envelope representation; it is not currently available in the approved path. | Opaque/UNKNOWN/excluded; reject formal Benchmark registration and Current Aggregate inclusion. No legacy-field inference or schema changes. |
| Battery RawLog multi-file atomic commit/reconciliation and retry | P0-4 provides the common storage criteria but the Battery canonical Object/Manifest/Commit mapping and Capture identity are not yet approved/implemented. | Do not retrofit a guessed recovery algorithm. Uncertain legacy states stay PENDING_RECOVERY / QUARANTINED; no overwrite, deletion, ID regeneration or mutating retry. |
| Hardware/device-specific boundary, millis rollover or STARTALL skew claims | No deployed-build equivalence evidence or physical test authorization. | No Firmware modification, hardware access or device-specific assertion. |

### 14.3 P1-P5 phase disposition

| Phase | Can proceed after separate implementation approval | Blocked portion |
|---|---|---|
| P1 Host event lifecycle | Observation-only event provenance and preservation, without Capture association | Normative Capture lifecycle, ACK-to-Capture correlation, Capture completeness |
| P2 Raw byte fidelity | Byte-preserving receive and isolated fidelity tests | Canonical per-Capture RawLog Object/Reference/Sample linkage and Capture-keyed retry |
| P3 Ordering / Quality | Preserve order/elapsed evidence; detect direct contradictions; default unknown quality to NOT ELIGIBLE | Numeric gap/duplicate policy, sequence synthesis, Quality PASS where required contract absent |
| P4 Outcome / Aggregate | Pure CC-CR07 mapping and unit tests for explicitly evidenced events | Persisted formal Outcome/Quality, Benchmark/Aggregate admission without Owner Envelope mapping |
| P5 Retry / recovery | No active Battery work; no Capture Key design or Capture-keyed retry. Existing DB Main storage rules remain the governing reference only. | Capture identity/idempotency, Battery canonical-object commit/reconciliation, and any retry that mutates uncertain state |

### 14.4 Required approvals and gates

1. **Implementation authorization:** separate explicit Central Command approval is mandatory before any source-code change, including the implementable observation/test-only portions above.
2. **P0-2 identity:** no further Battery-side design work or ID proposal is authorized/needed now. Reopen only through a future common identity change proposal backed by new evidence and Central Command direction.
3. **P0-3 Owner Envelope:** if a formal field mapping later becomes available, review that exact authoritative schema. Do not ask DB to repeat Issue #207 GL-04 mapping.
4. **P0-4 storage:** any future canonical-object/manifest/commit design must map each DB Main §8 / §14.3 durability step and fault boundary before implementation authorization.
5. **Physical / Firmware:** remains separately gated; Issue #16 5A E2E and physical discharge remain NOT RUN.
6. **PR #218:** remain OPEN / DRAFT / UNMERGED. Preserve accepted code HEAD `91c635dd5c129633898566adf929a8dc2f7386ab`; do not modify main or the accepted code scope.

### 14.5 Current status

- P0-1..P0-4 decision: **DECIDED** by #7172052263; documented here.
- P1/P2/P3/P4 observation-only or pure-logic scope: **IMPLEMENTABLE IN PRINCIPLE, NOT AUTHORIZED, NOT STARTED**.
- Capture identity, formal linkage, formal persistence/eligibility, Capture-keyed retry/reconciliation: **BLOCKED BY DECIDED STOP CONDITIONS**.
- Source code changes for this update: **NONE**.
- New tests: **NOT RUN**.
- Firmware / DB schema / DDL / Migration / DB data / main / hardware: **UNCHANGED**.
- PR #218: **OPEN / DRAFT / UNMERGED**, accepted code HEAD unchanged.
- Physical 5A E2E / discharge: **NOT RUN**.
