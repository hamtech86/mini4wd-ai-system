# v0.8.3 Cross-Document Consistency Audit — Draft

- 基準日: 2026-11-21
- 対象ブランチ: `docs/db-logical-design-v0.8.3-remediation-20261120`
- 状態: **矛盾検出・統括判断待ち**
- 目的: v0.8.3本文、補助論理設計、統括Issueおよび既存のAnonymous Mode契約を相互照合する。
- 制約: 本文の一方を独断で採用しない。物理設計・DDL・DB生成・Migration・実装を許可しない。

## 1. 監査対象と一次根拠

| Source | Relevant section / decision |
|---|---|
| `COMMON_DB_LOGICAL_DESIGN_v0.8.3_REMEDIATION_DRAFT.md` | §§1.2, 1.4, 5.3–5.5, 6, 7 |
| `V083_SESSION_LIFECYCLE_OUTCOME_DRAFT.md` | §§1, 2, 4, 5, 8 |
| `V083_ENTITY_INVENTORY_GAP_REGISTER_DRAFT.md` | §§2, 4–6 |
| Issue #201 | Anonymous Mode / DB unavailable acceptance scope and approved Phase 2 boundary |
| Issue #209 | DB-RV-01 and DB-RV-07 required re-review conditions |

Issue #209 remains OPEN with decision **ORANGE — conditional return / final approval withheld**. No new overall approval was present at this audit.

## 2. CC-01 — Session Status derivation contradiction (BLOCKER)

### Main v0.8.3 text

§1.4.1 currently states:

> Session StatusはHistorical SessionのMeasurement集合から導出する。

This defines Session Status as a derived value from the Session's Measurement collection.

### Session Lifecycle supplemental proposal

`V083_SESSION_LIFECYCLE_OUTCOME_DRAFT.md` §§1, 2 and 4 states:

- Session Lifecycle and per-Measurement Outcome are separate concepts.
- Measurement Outcome mixtures must not determine Session Lifecycle.
- Session closes only on a verified external-authority `PHYSICAL_RUN_CLOSED` Event.
- COMPLETE / STOP / ERROR / CANCEL / INCOMPLETE / UNKNOWN belong to Measurement Outcome, not Session Status.
- The formal existing source for `PHYSICAL_RUN_CLOSED` has not yet been established.

### Assessment

These statements are logically incompatible as currently worded. The supplemental proposal explicitly identifies §1.4.1 as inconsistent and rejects deriving Session Lifecycle from mixed Measurement outcomes. The main text still retains the older derivation rule.

This affects Session lifecycle, restore behavior, Aggregate readiness, and whether a run without a recognized close event can be marked closed.

### Required resolution

1. Decide whether Session has an independent Lifecycle (e.g. OPEN / CLOSED / QUARANTINED) or a derived status.
2. If independent Lifecycle is selected, replace §1.4.1 and reconcile all references in §§1, 6, 7, 12 and V082 acceptance cases.
3. Confirm whether a formal `PHYSICAL_RUN_CLOSED` external-authority Event exists. Until evidence is found, do not silently make the proposed Event normative.
4. Keep Measurement Outcome as a separate per-Measurement concept; do not map STOP/ERROR/CANCEL onto Session Lifecycle.

**DB department disposition:** BLOCKER; no unilateral selection. Supplemental proposal is not an approval to edit the normative main draft.

## 3. CC-02 — Anonymous Measurement late DB association conflict (BLOCKER / POLICY DECISION)

### Main v0.8.3 text

§1.2.6 permits a prior Measurement to be registered into DB Mirror by an explicit Association Operation after later assignment. It also states that Anonymous-period data is not automatically imported and requires an explicit user instruction.

§1.3 and §1.4 further define that NONE / ANONYMOUS measurements are not retroactively treated as ASSIGNED and do not enter Current Aggregate.

### Session Lifecycle supplemental proposal

`V083_SESSION_LIFECYCLE_OUTCOME_DRAFT.md` §§1, 4 and 5 states that anonymous data is not imported into DB later within this proposal; Issue #201 anonymous RawLog later import / Instance relinking is outside the proposal.

### Issue #201 accepted scope

Issue #201's approved Anonymous Mode scope says:
- Anonymous Battery capture preserves channel-specific RawLogs locally.
- The current recovery acceptance does not include later import of anonymous RawLogs into DB or Instance relinking.
- Anonymous RawLogs are not automatically reused as DB benchmark records.
- The possibility of later registration is a separate future DB redesign topic; it is not part of the current Anonymous Mode acceptance.

### Assessment

The main v0.8.3 draft currently permits an explicit user-directed later DB association for Anonymous-period Measurement data, while the supplemental proposal excludes that behavior and Issue #201 excludes it from the accepted Anonymous Mode scope.

The Issue #201 wording does not prove a permanent prohibition on every future DB design. It does establish that this behavior is not included in the currently approved Anonymous Mode acceptance. Therefore, the main draft must not silently treat the feature as already approved.

NONE-period late association and ANONYMOUS-period late association should not be conflated. The current text does not provide sufficient evidence to generalize one policy to both.

### Required resolution

1. Make a separate policy decision for NONE-period Measurement and ANONYMOUS-period Measurement.
2. For ANONYMOUS-period RawLog, either retain the Issue #201 exclusion or obtain explicit overall approval to extend the scope in the future DB design.
3. If late association is allowed in a future scope, define provenance, explicit user intent, privacy/consent semantics, original Assignment-at-Measurement preservation, Audit trail, RawLog ownership and whether a DB Measurement Mirror may be created.
4. Never auto-import Anonymous RawLogs, never rewrite the original Assignment-at-Measurement, and never treat a later association as proof that the Measurement was originally ASSIGNED.
5. Until the decision is made, mark Anonymous late association as NOT SPECIFIED / NOT APPROVED and do not make it an acceptance requirement.

**DB department disposition:** BLOCKER / policy decision required. Do not implement or present the main draft's manual association clause as already approved.

## 4. CC-03 — Canonical Name coverage vs full Entity Inventory (MAJOR)

The main v0.8.3 §5.3 lists 11 Canonical Name schemas. The Entity Inventory lists 23 logical Entity classes, including Physical Run Manifest, Assignment Snapshot/Event, Measurement Envelope, Profile Snapshot, Operation Journal/Intent, DB Operation Marker, Artifact envelopes, Aggregate Request/Attempt/Pointer and Recovery/Integrity entities.

The audit now contains normal-value byte vectors for all 11 entities explicitly listed in §5.3, and a structural parse check of 29 Expected Hex entries passed. This does **not** establish canonical identity coverage for all 23 Entity classes.

Required resolution:
1. Classify each Inventory Entity as UUID/Canonical Name identity, content-hash identity, externally assigned identity, or derived Pointer with no independent identity.
2. For every Entity requiring deterministic UUID identity, define its full fixed-order Canonical Field Schema and vectors.
3. For content-hash objects, define canonical payload serialization separately; do not substitute Content Hash for Entity identity without explicit design.
4. Ensure Receipt, Journal, DB Marker, Artifact, Aggregate and Recovery identity relationships are deterministic and non-recursive.

## 5. CC-04 — Main draft and supplemental docs version synchronization (MAJOR)

The supplemental documents contain proposals that have not yet been integrated into the normative v0.8.3 draft. This is intentional under the current approval boundary, but it means the branch must not be represented as a fully internally consistent specification.

At minimum:
- Main §1.4.1 conflicts with Session Lifecycle proposal §2.
- Main §1.2.6 conflicts with the Anonymous late-import exclusion in the Session Lifecycle proposal / Issue #201 current scope.
- Entity Inventory §5 records that many Entity canonical schemas remain undefined, even though the §5.3 subset has normal-value vectors.
- Canonical audit's initial finding/status text has been revised to distinguish the completed 11-Entity baseline from incomplete per-Field boundary coverage and incomplete full-inventory coverage.

## 6. Decision register

| ID | Issue | Severity | Status | Owner |
|---|---|---|---|---|
| CC-01 | Session Lifecycle vs Measurement-derived Session Status | BLOCKER | Awaiting overall decision / source evidence | Overall commander |
| CC-02 | Anonymous late DB association | BLOCKER / POLICY | Awaiting overall decision; Issue #201 current acceptance excludes it | Overall commander |
| CC-03 | 11 Canonical schemas vs 23 Inventory Entities | MAJOR | Coverage gap documented; identity classification required | DB department, overall review |
| CC-04 | Main and supplemental proposal synchronization | MAJOR | Not synchronized pending CC-01/02 decisions | DB department |

## 7. Current gate

- v0.8.2: not approved.
- v0.8.3: remediation draft only; not approved.
- Issue #209: ORANGE / final approval withheld.
- No DDL, DB generation, migration, restore, implementation, implementation PR, or main merge.
- No Battery department direct contact or Battery implementation changes from DB department.
- User action: none required at this point.

**Conclusion:** The current remediation branch has made useful progress on the DB-RV issues, but it is not yet a single internally consistent normative specification. CC-01 and CC-02 require explicit overall decisions before the main text can be reconciled.