# Battery Capture Contract — Logical Contract & Implementation Plan

- Date: 2026-11-25
- Authority: Central Command decision, PR #218 comment #7161905985
- Evidence baseline: `docs/battery_capture_contract_evidence_recovery_report.md`, commit `db7961832aabafa84eff7b6b3f97b377e3041394`
- Accepted Battery code baseline: PR #218 exact HEAD `91c635dd5c129633898566adf929a8dc2f7386ab`
- Document branch: `docs/battery-capture-contract-logical-plan-20261125`
- Purpose: record the seven logical decisions, current implementation/test status, fail-closed behavior, and a proposed implementation/test plan for separate approval.
- Revision: v2 clarification responding to Central Command review comment #7162994812; no implementation authorization is implied.
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
| CC-CR06 Partial/Retry | Target exactly-once logical persistence using a stable Capture/Idempotency Key. Same key + same content = no-op; same key + different content = Conflict. Uncertain partial multi-file persistence = Quarantine until reconciled. This is a target contract, not a claim about current RawLog atomicity. | YES | YES | NO/PARTIAL: selected DB/Anonymous retry protections and A7 idempotency exist; RawLog multi-file write is not atomic and no stable Capture key covers the whole capture evidence set. | PARTIAL: A7 and V1 retry tests pass; RawLog partial-write fault-injection / capture-key exactly-once tests absent. | Key generation and atomicity design; crash/fault injection not run. |
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

### 6.3 Exactly-once logical persistence target

- A stable Capture/Idempotency Key must be designed in alignment with existing Physical Run / Operation / Receipt concepts before implementation.
- Same key and identical complete persistence payload: no-op success; no UPDATE/REPLACE.
- Same key and different payload: Conflict; preserve existing evidence.
- Any multi-file partial write with uncertain final state: Quarantine; reconcile before treating as saved.
- The existing A7 Benchmark result idempotency decision remains separate and unchanged.
- No claim of exactly-once until failure injection covers each persistence boundary and read-back proves the same logical object is not duplicated or replaced.

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

## 8. Proposed implementation plan — approval required before work

This is a planning proposal only. It does not authorize code changes. The sequence avoids firmware and DB schema changes and keeps the accepted PR #218 code baseline intact.

### Phase P0 — design closure and implementation authorization

1. Review this contract table and approve the proposed host-only scope.
2. Define the Capture start boundary from an observable event and the Capture end boundary from an observable terminal condition. Distinguish a Host request from a Firmware acknowledgement/terminal observation; where either boundary cannot be proven, retain evidence without asserting a per-Capture association.
3. Specify the Capture Key using the existing Physical Run / Operation / Receipt identities and their relationships. Identify the exact authoritative identifier, uniqueness scope, and derivation/reference rule; do not invent a parallel ID scheme.
4. Confirm the existing DB field mapping in Issue #207 comment #7101200440 is used as-is. If Outcome / Quality / RawLog references cannot be represented by that approved contract, keep the data opaque and excluded from Aggregate; submit the exact persistence gap for separate authorization. Do not ask DB to repeat the mapping.
5. Define a reconciliation procedure for partial RawLog writes: which persisted objects/manifests/hashes/read-back evidence prove complete, incomplete, or conflicting state. Until such evidence can prove reconciliation, retain Quarantine and prohibit retry from overwriting uncertain evidence.
6. Obtain separate authorization before any source implementation begins.

**Exit:** Central Command explicitly approves the implementation scope and test plan, and the four design closure items above have evidence-backed answers or explicit UNKNOWN/opaque stop conditions. Any DB schema, Firmware, or physical action remains separately gated.

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

### Phase P5 — stable Capture key and retry/fault recovery

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
| Capture Key design alignment | Must align with existing Physical Run / Operation / Receipt model. | DESIGN TASK / NOT APPROVED |
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

**Requested next decision:** approve or revise the proposed host-only implementation scope and test plan. Until explicit approval is received, Battery will make no implementation changes.
