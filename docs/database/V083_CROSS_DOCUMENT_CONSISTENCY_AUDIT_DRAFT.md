# v0.8.3 Cross-Document Consistency Audit — Draft

- 基準日: 2026-11-21
- 対象ブランチ: `docs/db-logical-design-v0.8.3-remediation-20261120`
- 状態: **CC-01 / CC-02統括判断反映済み・旧資料の同期監査を継続・全体設計未承認**
- 目的: v0.8.3本文、補助論理設計、統括Issueおよび既存契約を相互照合する。
- 制約: Issue #210の決定範囲を超えて仕様を拡張しない。物理設計・DDL・DB生成・Migration・実装を許可しない。

## 1. 監査対象と一次根拠

| Source | Relevant section / decision |
|---|---|
| `COMMON_DB_LOGICAL_DESIGN_v0.8.3_REMEDIATION_DRAFT.md` | §§1.2, 1.4, 5.3–5.5, 6, 7 |
| `V083_SESSION_LIFECYCLE_OUTCOME_DRAFT.md` | §§1–8 |
| `V083_STATE_TRANSITION_MATRIX_DRAFT.md` | §§1–6 |
| `V083_ENTITY_INVENTORY_GAP_REGISTER_DRAFT.md` | §§2, 4–6 |
| Issue #201 | Anonymous Mode / DB unavailable acceptance scope |
| Issue #209 | DB-RV-01〜08差戻し条件 |
| Issue #210 | CC-01 / CC-02統括決定（2026-11-21） |

Issue #209のv0.8.2判定はORANGE — 条件付き差戻し・最終承認保留のまま。Issue #210はCC-01 / CC-02のみを決定し、v0.8.3全体を承認していない。

## 2. CC-01 — Session LifecycleとMeasurement Outcome

**Status: DECIDED — Issue #210を規範判断として反映する。**

### 決定内容
1. Session LifecycleとMeasurement Outcomeを完全に分離する。
2. Measurement Outcome（COMPLETE / STOP / ERROR / CANCEL / INCOMPLETE / UNKNOWN）はMeasurement単位で保持し、Session Lifecycleへ集約しない。
3. Session LifecycleはNOT_CREATED / OPEN / CLOSED / QUARANTINED。NOT_CREATEDはSessionレコードではなく未生成状態。
4. Scopeの初回ASSIGNED確定時にSessionを一度だけ生成する。以後NONE / ANONYMOUS / 別InstanceへのAssignment変更でもSession IDとLifecycleを保持する。
5. MeasurementのOutcomeやMeasurement終了ではSessionを閉じない。
6. CLOSEDはRun管理側の明示的Close Operationが外部正本に記録され、その記録と依存参照を検証できた場合に限る。
7. Close Operationは論理Run管理イベントであり、Motor/BatteryのSTOP ACK、機器制御プロトコル、最終Telemetry、アプリ終了、プロセス消失、無通信時間からRun終了を推定しない。
8. Close受入時は対象ScopeのCaptureが終端または明示的に放棄・保留され、未確定MeasurementをCOMPLETEへ読み替えない。終端不明・参照不整合はOPEN維持またはQUARANTINEDとし、推測でCLOSEDにしない。
9. DB unavailable / ANONYMOUS運用ではDB Sessionを生成せず、外部正本上のRun / Capture情報を保持する。

### 反映対象
- Main draft §1.4
- Session Lifecycle supplemental §§1 / 2 / 8
- State Transition MatrixのSession状態・受入ケース（SES-017〜024を含む）
- Self Review: SR-09をCC-01で解決・旧案廃止として明示。SR-01 / SR-02はCC-02後の残課題を再定義
- Entity Inventory: Session Lifecycle語彙・Close根拠を更新
- V082 Crosswalk: V082-007を旧案として隔離し、CC-01 / CC-02補助受入ケースを追加
- 本文の関連参照§1 / §6 / §7 / §12（同期確認を継続）

PHYSICAL_RUN_CLOSEDは既存機器Eventとして扱わない。Run管理側の明示Close Operationが外部正本へ記録する論理Eventとして定義する。Event名・Schema・永続化形式の論理案は許容されるが、機器プロトコル変更を意味しない。

## 3. CC-02 — NONEとANONYMOUSの後日関連付け

**Status: DECIDED — Issue #210を規範判断として反映する。**

### ANONYMOUS
1. 現行設計範囲では、Anonymous Mode中にローカルRawLog / 外部正本として取得したMeasurementを後日DBへ取込・Mirror化・Instance再紐付けしてはならない。
2. 自動取込は禁止。明示操作による例外も現行範囲には含めない。
3. Issue #201の承認済みAnonymous Mode受入範囲を拡張しない。
4. 将来拡張は永久禁止ではないが、プライバシー・明示同意・RawLog所有権・来歴・監査・Measurement/Session関係・受入条件を含む別設計と統括の明示承認を要する。

### NONE
1. DB利用可能時に取得され、外部正本およびDB管理下のMeasurement記録が既に存在するNONE期間のMeasurementに限り、後日の明示Association Operationを論理設計対象としてよい。
2. 自動関連付けは禁止。実行主体・時刻・変更前後・理由を監査履歴に記録する。
3. Assignment-at-MeasurementはNONEのまま不変。後日関連付けを測定時ASSIGNEDの証拠として扱わない。
4. 後日関連付けだけを理由にCurrent Aggregateへ自動算入しない。履歴分析への利用条件は別途定義する。
5. NONE方針はAnonymous RawLogのDB取込を許可しない。保存経路・来歴・プライバシー境界を混同しない。

### 反映対象
- Main draft §1.2 / §1.3 / §1.4
- State Transition Matrix §§1–3
- Issue #201との境界説明
- NONE明示関連付けとANONYMOUS後日取込禁止を別々に検証する受入ケース

## 4. CC-03 — Canonical Name coverage vs full Entity Inventory (MAJOR / OPEN)

Main v0.8.3 §5.3に列挙された11 Entityの正常値byte vectorは作成済み。Expected Hex 29件の構造検査は29/29通過したとの作業報告がある。ただし、これは全23論理EntityのCanonical Identity / Content Hash分類、全Field制約、UUIDv5実装合格を示さない。

Required:
1. Inventory全EntityをUUID/Canonical Name identity、content-hash identity、externally assigned identity、derived Pointerに分類する。
2. 決定的UUID identityを必要とする各Entityに完全な固定順Canonical Field Schemaとvectorを定義する。
3. Content Hash対象はEntity identityと分離したCanonical Payload Serializationを定義する。
4. Receipt、Journal、DB Marker、Artifact、Aggregate、RecoveryのID関係を非再帰かつ再現可能にする。

## 5. CC-04 — Main draft and supplemental docs synchronization (MAJOR / IN PROGRESS)

Issue #210の判断を受け、Main draft・Session Lifecycle supplemental・State Transition Matrixを更新した。これらの更新は専用ブランチ上の文書修正であり、全条項の整合完了を意味しない。

継続確認:
- Main §1.4とSession Lifecycle §§1 / 2 / 8の語彙・条件が完全一致すること。
- Main §1.2のNONE関連付け条件とMatrixのNONEケースが一致すること。
- ANONYMOUSの後日取込禁止が本文・補助案・Issue #201説明で一貫すること。
- §1 / §6 / §7 / §12およびV082受入表に旧記述が残っていないこと。
- PHYSICAL_RUN_CLOSEDを機器既存Eventとして誤記していないこと。

## 6. Decision register

| ID | Issue | Severity | Status | Owner |
|---|---|---|---|---|
| CC-01 | Session Lifecycle vs Measurement Outcome | BLOCKER | DECIDED; document synchronization in progress | DB department |
| CC-02 | NONE / ANONYMOUS late association | BLOCKER / POLICY | DECIDED; document synchronization in progress | DB department |
| CC-03 | 11 Canonical schemas vs 23 Inventory Entities | MAJOR | OPEN; coverage classification required | DB department |
| CC-04 | Main and supplemental proposal synchronization | MAJOR | IN PROGRESS; full cross-reference audit pending | DB department |

## 7. Current gate

- v0.8.2: ORANGE / not approved.
- v0.8.3: remediation draft only / not approved.
- Issue #210: CC-01 / CC-02 decision only; no overall approval.
- No physical design, DDL, DB generation, migration, restore execution, implementation, implementation PR, or main merge.
- UUIDv5 Namespace remains unapproved and unadopted.
- DB-001〜124, V082 crosswalk, Entity complete constraints, Canonicalization boundary vectors, Motor/Battery formal contract checks, and Restore acceptance remain open.
- No Battery implementation changes or direct Battery department instructions from DB department.

**Conclusion:** CC-01 / CC-02 are now decided and their primary text changes have been applied on the documentation branch. The full v0.8.3 design remains unapproved; continue cross-document synchronization and all outstanding DB-RV / evidence work before requesting overall re-review.


## 8. 2026-11-21 cross-document remediation batch

### Updated documents
- `V083_SELF_REVIEW_FINDINGS_DRAFT.md`: Issue #201の旧一括表現をNONE / ANONYMOUSに分離。SR-01 / SR-02の残課題を更新し、SR-09をCC-01により解決・旧案廃止と記録。
- `V083_ENTITY_INVENTORY_GAP_REGISTER_DRAFT.md`: Session Lifecycleの確定語彙、Outcome非導出、Close Operation条件をEntity最低契約に反映。
- `V082_DB_001_124_CROSSWALK_DRAFT.md`: V082-007のSession Status導出を旧仕様として隔離し、CC-01 / CC-02の未実行補助受入ケースを追加。

### Remaining checks
- Main draft §1 / §6 / §7 / §12と補助資料の語彙・条件を再走査する。
- NONE明示Association対象のSession membership条件を定義する（CC-02は許容範囲のみ決定し、membershipの詳細までは決めていない）。
- DB-001〜124個別原文・正式出典の回収は未完了。

### Verification boundary
- 変更対象はdocs/database配下の論理設計・監査資料のみ。
- DDL、DB生成、Migration、Restore実行、実装、main変更・mergeは行っていない。
- 追加受入ケースは提案であり、実装・実行・PASSを意味しない。


## 9. DB-001〜124 prior-record recovery (2026-11-21)

Prior conversation records were re-queried. DB-001〜056 individual short test descriptions and expected outcomes were recovered as conversation-record summaries and added to `DB_001_124_EVIDENCE_LEDGER_DRAFT.md`. This is not recovery of the original formal requirement document or proof of approval / implementation. In particular:
- DB-032 (ANONYMOUS→Instance later association) is a historical requirement and is superseded for current scope by Issue #210 CC-02.
- DB-020 / DB-036 (explicit Bootstrap success) are historical expectations and do not authorize DB creation / Bootstrap under current Issue #201 restrictions.
- DB-057〜078 individual definitions remain unrecovered despite the range history for additions in 新DB設計書 v0.2.
- DB-079〜109 have a user instruction to preserve the existing acceptance-test range, but individual definitions remain unrecovered.
- DB-110〜124 have range-level additional-instruction history only; individual definitions remain unrecovered.

A Library search for the named 新DB設計書 v0.2 and DB requirement ranges did not surface the source document. Do not infer nonexistence from that search. Continue retrieval from prior conversation records and GitHub historical artifacts; do not ask the user to resubmit known materials.


## 10. DB-001〜056 crosswalk candidate triage (2026-11-21)

The V082 crosswalk now includes a separate candidate-overlap table for DB-008 / 012 / 014 / 017 / 031 / 034 / 046 / 051 / 055. These are semantic similarities only, not confirmed mappings. In particular, a Session-not-created outcome is not automatically identical to rejecting an explicit Session-create request; RawLog mismatch detection is not automatically identical to quarantine; and Run PARTIAL is not automatically Aggregate PARTIAL.

Potential duplicates within DB-001〜056 are recorded for DB-019/035 (missing DB normal startup), DB-020/036 (explicit Bootstrap success), and DB-017/046 (analysis rerun preserves prior results). No duplicate is confirmed because exact preconditions, actions, and expected results are not yet available from original source documents.

**Current traceability result:** DB-001〜056 short definitions recovered from prior conversation records; 0 DB↔V082 one-to-one mappings confirmed; 0 partial mappings confirmed; duplicate candidates listed but 0 confirmed. DB-057〜124 individual definitions remain unrecovered. This is a conservative evidence status, not proof that no overlap exists.


## 11. Entity Inventory / Canonicalization coverage audit (2026-11-21)

### Entity inventory
- Counted 23 logical entities in `V083_ENTITY_INVENTORY_GAP_REGISTER_DRAFT.md` §2.
- Added §6 coverage matrix mapping each inventory entry to Main draft §5.3 Canonical Field Schema.
- Result: 10 direct Schema mappings; 13 Inventory entities have no defined Schema; `OPERATION_EVENT` is a Schema row without a confirmed Inventory mapping.
- The 13 missing schemas are not automatically UUIDv5 requirements. Identity UUID, Composite identity, Content Hash, Derived Pointer, and External event identity must be distinguished entity by entity.

### Canonical vectors
- Independently recalculated all 11 §5.3 Schema sample vectors from the documented fixed inputs and binary grammar: 11/11 exact byte match (DB_RUN/RUN_SCOPE 2/2; remaining nine rows 9/9).
- Existing structural parser check remains 29/29 expected hex strings parsed without structural errors.
- Neither result validates the missing 13 schemas, semantic uniqueness, per-field domain, UUIDv5 output, Namespace, or two-independent-implementation agreement.

### Motor / Battery contract boundary
- Motor: Issue #35 is the sole current specification source and explicitly prohibits a department from reconstructing missing specifications from other Issues/comments/old commits. It defines important raw-log and channel meaning boundaries but does not, in its current text, provide a complete DB entity mapping / Measurement Envelope field contract / UUID identity contract. DB must not infer those missing details from subordinate task Issues.
- Battery: Issue #16 is an E2E Benchmark verification task, not a complete formal Battery Measurement / RawLog / Session data contract. It names CH1/CH2 independent sessions and benchmark checks but does not define the full canonical field schema, Capture terminal outcomes, or persistence identity. DB must not invent them.
- Required next input is formal Motor and Battery data contracts from their responsible authority/central command. DB work may define adapter placeholders and explicit unresolved fields only; it may not change either device contract.

### Current gate
Canonicalization remains a proposal and unapproved. Namespace remains unapproved. Entity Inventory remains incomplete. Physical design / DDL / DB generation / Migration / Restore execution / implementation remain prohibited.


## 12. V082-001〜005 legacy Session Outcome aggregation conflict (2026-11-21)

A targeted read of the full V082 crosswalk found that the old Session aggregation expectations were not limited to V082-007:

- V082-001: zero Measurements → NOT_STARTED
- V082-002: all COMPLETE → COMPLETED
- V082-003: COMPLETE + FAILED → PARTIAL
- V082-004: COMPLETE + IN_PROGRESS → IN_PROGRESS
- V082-005: all FAILED → FAILED
- V082-007: later ASSIGNED → derive Session Status from existing Measurements

All six are historical Session-level Outcome aggregation expectations and are superseded as Lifecycle rules by Issue #210 CC-01. The crosswalk preserves the old test descriptions but labels their expected Session-state behavior as obsolete. Current acceptance overlays CC-01-T01 / T04 / T05 and SES-017〜020 assert that zero, homogeneous, and mixed Measurement Outcomes do not change Session Lifecycle.

V082-006 (Anonymous Measurement with no DB Session) is not in this obsolete set; it remains compatible with the no-Session behavior for a Scope that has never been ASSIGNED, subject to CC-01/CC-02 boundaries.


## 13. CC-02 NONE Association — Session membership boundary remains OPEN (2026-11-21)

Issue #210 permits design of explicit late association only when the NONE-period Measurement already has both an external authoritative record and a DB-managed Measurement record. It does not decide how that record relates to Session membership.

### Boundary scenarios requiring an explicit rule

| Scenario | Current facts | Unresolved question |
|---|---|---|
| A. Scope already has Session (earlier ASSIGNED → NONE) | Session exists and remains OPEN under CC-01. DB is available; a NONE Measurement is captured and already stored as DB-managed Measurement. | Is it immediately a member of the existing Session with Assignment-at-Measurement=NONE, and does later association only add an Instance link/history? |
| B. Scope has never been ASSIGNED (initial NONE) | No DB Run / Session exists under current v0.8.3 generation rules. | Can a DB-managed Measurement exist without a Session, or is this scenario ineligible for later association? |
| C. Measurement exists before first ASSIGNED | External and DB Measurement record may exist, but Session is not yet created. | After first ASSIGNED creates Session, may the existing NONE Measurement be linked to it, or must it remain outside Session membership? |

### Design alternatives — not selected

1. **Existing-Session-only**: NONE late association is eligible only where the Scope already had a Session at Measurement capture. The Measurement is immediately recorded under that existing Session with Assignment-at-Measurement=NONE; later association changes only a separate Instance association/audit relation. Initial-NONE-before-first-ASSIGNED has no DB Measurement Mirror and is ineligible.
2. **Detached-Measurement**: DB-managed NONE Measurement may exist without Session; later Session creation requires an explicit, audited membership-link rule. This would extend the current "Session membership is Measurements registered after Session creation" statement and requires explicit approval.
3. **Session-link-on-association**: Existing NONE Measurement may be linked to a later-created Session only by explicit association; this requires a rule for whether this is permitted when the Measurement's Physical Run / Scope has an existing Session, and must not change Assignment-at-Measurement.

**DB department recommendation for risk containment:** prefer Alternative 1 unless central command explicitly authorizes a detached or delayed Session-membership model. This is a recommendation only, not a selected rule.

No automatic Session creation, DB Run creation, RawLog import, Mirror generation, or Current Aggregate inclusion is inferred from NONE. ANONYMOUS remains prohibited from later DB import / Mirror / Instance re-association under CC-02.

**Status: OPEN — return to central command for a narrow boundary decision before finalizing Session membership and the CC-02 association contract.**


## 14. Canonicalization strict-input / version-freeze proposal (2026-11-21)

The Canonicalization audit now contains a draft-only proposal for:
- Freezing every byte-affecting rule under a Canonicalization Version and requiring a new version for schema / normalization / encoding changes.
- Strict UTF-8 and Unicode scalar handling, pinned NFC data version, no BOM stripping.
- Type-safe Integer encoding and canonical decimal rejection cases.
- Timezone-aware exact UTC nanosecond conversion, sub-nanosecond / overflow rejection.
- Strict Boolean, Byte String, NULL, u16/u32 length/count overflow handling.

This is a candidate remediation, not an adopted rule. Per-Field domain ranges, Unicode version pin, Timestamp leap-second policy, Entity Type registry, all Entity schemas, Namespace clearance and central approval remain open.

CBN-07 NUL notation ambiguity is resolved in Main draft §5.5 by replacing the ambiguous escape spelling with explicit Unicode scalar sequence and UTF-8 bytes. Expected Hex did not change.

**Gate:** CBN-01 coverage and sample vectors have improved, but CBN-02 / 03 / 04 / 05 / 06 / 08 remain open or partial. No UUIDv5 implementation or Namespace approval is claimed.


## 15. DB-001〜056 evidence ledger provenance correction (2026-11-21)

A read-back audit found that the ledger's range inventory still described DB-001〜056 as wholly unrecovered even though §4 already contained a conversation-derived short-definition table. The inventory rows and section-2 scope description have been corrected to distinguish three evidence levels:

1. Short definitions / expected outcomes recovered from prior conversation records (DB-001〜056).
2. Original requirement document, contemporaneous approval, and original test implementation not retrieved.
3. Current validity and V082 / implementation traceability not established.

A targeted retrieval also resolved an ID conflict in fragments for DB-015〜017. The retained mapping is DB-015 = Session reassociation with history append; DB-016 = RawLog reassociation with history append; DB-017 = Analysis rerun preserving prior results. Conflicting snippets that assigned RawLog metadata changes or RawLog Session/Instance association to these IDs are not used. This remains conversation-derived evidence, not recovery of the original v0.2 specification.

No V082 crosswalk match is promoted: similarity is insufficient without matching preconditions, action, and expected result. DB-057〜124 individual definitions remain unrecovered. This correction does not approve the legacy requirements or authorize DDL, DB generation, migration, Restore execution, implementation, PR, or main changes.


## 16. 追加監査 — Entity属性・存在証拠・Receipt Recovery（2026-11-21）

### 16.1 Entity 23種の属性・制約カバレッジ

Entity Inventory Gap Register §8に23 Entity個別のカバレッジ表を追加した。属性・型・NULL・一意性・参照/Cardinality・Identity分類・Lifecycle/保持・未確定事項を、Main draft等に明記された範囲に限定して記載した。

- 23/23 Entityについて明記済み / 部分 / 未定義の境界を整理。
- 23/23の完全属性・制約が完成したとは判定しない。
- Canonical Schemaのある10 Entityでも、SchemaはIdentity候補Fieldの一部にすぎず、全属性表を代替しない。
- 13 EntityはCanonical Schema未定義。OPERATION_EVENTはInventoryへの対応自体が未解決。
- 一般的なDB慣行から属性・FK・NULL・Retentionを補完しない。UUIDv5を未定義Entityへ自動追加しない。

### 16.2 DB-001〜124の存在確認レベル

Evidence Ledger §10に、EXISTS_CONFIRMED / EXISTENCE_EVIDENCED_CONTENT_MISSING / EXISTENCE_POSSIBLE_NOT_FOUND / EXISTENCE_UNCONFIRMED / LIKELY_NOT_CREATED / SEARCH_INCOMPLETEを定義した。

現時点の判定:
- DB-001〜056: 会話記録上の短縮定義は確認済み。原本仕様書・正式承認・番号付き実装テストの存在は未確認。
- DB-057〜078: 範囲履歴のみ。個別本文未回収、存在した可能性はあるが未発見。
- DB-079〜109: 維持指示の範囲履歴のみ。各試験実物の存在は未確認。
- DB-110〜124: 追加対象の範囲履歴のみ。個別成果物の存在未確認。
- 現時点でLIKELY_NOT_CREATEDと確定した範囲はない。これは存在を前提とする意味ではなく、未作成と高確度に判断する否定証拠も不足しているため。

2026-11-21にGitHub default-branch code search、Issue #207全コメント、Issue/PR searchを追加確認したが、DB-057〜124個別本文の実物は取得できなかった。Code Searchはdefault branch対象であり、非default / 削除済みbranch、全commit tree、過去会話全文、Library全体を網羅しない。検索0件を不存在証明としない。

### 16.3 Receipt Recoveryのクラッシュ点再監査

Receipt Recovery Contract §12に追加監査を記録した。

整合している候補:
- Intent → Envelope/PREPARED → Source Commit → DB Marker/Mirror Commit → VERIFIEDの順序。
- Source Commit後はABORTED禁止、同一Operation再開。
- DB MarkerとMirrorの同一Transaction、Commit結果不明時のMarker読戻し。
- VERIFIED / ABORTED不変、QUARANTINEDの解決は新Recovery Operation。

未解決:
- PREPARED / SOURCE_COMMITTED / DB_COMMITTED / VERIFIED / ABORTED Event自体の部分書込み。
- Event Ordinalの予約・消費と部分Tailの補完条件。
- 同一Receiptへの並行Recovery、stale lock / fencing。
- Manifest Head更新の競合・compare-and-swap相当の条件。
- DB Commit後の読戻し一貫性 / Isolation前提。
- Intent / Receiptの完全Canonical payloadと自己Hash除外規則。
- Receipt ID決定的導出の根拠とNamespace承認。
- Main draft §2.1との項目単位同期。

よってDB-RV-03を解消済みとは判定しない。物理耐久性・filesystem / DB durabilityは未実証であり、Issue #35のRawLog契約を一律拡張しない。

### 16.4 CC-02 Session membership

NONE late associationの対象MeasurementがSessionに属する条件は引き続き未決定。Existing-Session-only / Detached-Measurement / Session-link-on-associationの3案を維持し、DB部門のExisting-Session-only推奨は未採択。統括から追加判断がないため、Main draftの確定規則として閉じない。

### 16.5 作業境界

今回の変更は専用ブランチのdocs/database文書のみ。v0.8.2 ORANGE、v0.8.3未承認、UUIDv5 Namespace未承認を維持する。DDL / DB生成 / Migration / Restore実行 / 実装 / PR / main反映 / mergeは行わない。
