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


## 17. 旧DB ID-001〜176の証拠来歴と未回収時の処理決定（2026-11-21）

Evidence Ledger §12に、前チャットで確認済みの来歴と未回収項目の処理方針を反映した。

### 17.1 来歴の確定範囲

- DB-001〜056: 2026-11-18「DB部門 設計レビュー v0.2」の従来56項目。短縮定義は会話記録から回収済みだが、原本・正式承認・テスト実装は未回収。
- DB-057〜078: 2026-11-19「新DB設計書 v0.2」で追加された範囲として前チャットで確認。個別本文・原本ファイル・承認・テスト実物は未回収。
- DB-079〜109: 統括の維持・保全指示範囲。維持指示は確認済みだが、各試験の実物が存在することとは区別する。
- DB-110〜124: 統括の追加指示範囲。追加指示は確認済みだが、各要件・テストの完成とは区別する。
- DB-125〜154: 正式番号の根拠が確認できず、前チャットで既存試験扱いを撤回。正式体系の対象外とし、既存IDとして登録しない。
- DB-155〜176: 提案番号を撤回済み。番号は復活・再利用せず、元の内容が残る場合に限りIDなしの候補メモとして扱う。

### 17.2 未回収時の確定処理

DB-001〜124はEvidence Ledgerに履歴を残す。個別原文・正式承認・テスト実物を回収できない場合、削除・不存在断定・推測補完は行わず、参照専用・実行不可として凍結する。

- Content Status = NOT_RECOVERED
- Approval Status = NOT_VERIFIED
- Test Artifact Status = NOT_VERIFIED
- Operational Disposition = REFERENCE_ONLY_NOT_EXECUTABLE

この状態のIDは現行受入試験のPASS/FAIL対象にしない。原文等が後日回収された場合だけ再審査する。未作成を直接示す証拠がある場合はNOT_CREATED_CONFIRMED / RETIRED_NOT_CREATEDへ更新できるが、検索0件だけでは更新しない。

現行システムのテスト不足を補う場合、承認済み仕様から独立した新Test IDを提案し、統括承認後に採番する。旧IDを推測再現したり、新IDへ転用したりしない。旧IDとの対応は直接証拠がある場合のみTraceabilityとして記録する。

### 17.3 完了・再開条件

同じ保存先を無期限に検索することを完了条件にしない。既知の保存先・会話記録・Issue/PR・Libraryを探索しても個別証拠が回収できなければ、参照専用・実行不可として凍結し、証拠調査を終了する。新しい保存先情報・具体的な出典・一次資料が提示された場合のみ再開する。

本処理は証拠管理と暫定運用であり、旧IDの正式承認・廃止や新規受入試験の承認を意味しない。v0.8.2 ORANGE / v0.8.3未承認、物理設計・DDL・DB生成・Migration・Restore・実装禁止の境界は維持する。


## 18. Receipt Recovery未解決事項の論理 / 物理責任境界（2026-11-21）

Receipt Recovery Contract §13で、未解決事項を論理設計段階で閉じる事項と、物理設計・実装・耐久試験まで保留する事項に分離した。

### 18.1 論理段階で閉じる事項
- Main §2.1と補助契約間のIntent Plan / Envelope属性同期。
- Receipt ID決定的導出の入力・versioning・再発行規則（UUIDv5 Namespaceは未承認のまま）。
- Event Ordinal発行主体・消費点・gap / partial appendの状態規則。
- 同一Operation / Receiptの二重writer防止と競合時の判定。
- Manifest Head predecessor競合時の拒否規則。
- DB Marker不存在を確定できない場合の保留規則。
- Envelope / Event Hashの自己参照除外、相互依存、version、Golden Vector。
- Journal / Receipt / Marker / RecoveryのEntity境界・Authority・Cardinality整合。

### 18.2 物理設計・実装段階まで保留
- fsync / Directory fsync / atomic renameのOS・filesystem別保証。
- Partial Tailの具体的修復・保全方式。
- SQLite Isolation / synchronous / WAL / read-after-commit実証。
- Lock lease / stale lock / fencing tokenの具体的実装方式。
- 電源断・プロセスkill・I/O error・DB unavailableを使ったcrash injection試験。

論理的な受入条件を定めず物理方式を仮定することも、物理実証なしに耐久性を合格扱いすることもしない。DB-RV-03は未解決を維持する。

### 18.3 次の閉鎖順序
1. Main §2.1とReceipt補助契約の項目単位同期。
2. Intent→Envelope再構成、Receipt ID、Hash範囲の論理契約確定。
3. Event Ordinal / partial append / writer競合 / Manifest Head競合の抽象条件確定。
4. DB read-after-commit不確実時の保留規則。
5. Entity InventoryとのJournal / Receipt / Marker / Recovery境界照合。
6. 統括審査へ提出。承認後に限り物理設計へ進む。

### 18.4 承認境界
今回の分類は未解決事項の責任境界と作業順序を明確にしたもので、DB-RV-03解消、v0.8.3承認、物理設計・DDL・DB生成・Migration・Restore実行・実装許可を意味しない。


## 19. Main §2.1 / Receipt Contract 項目単位同期監査（2026-11-21）

Receipt Recovery Contract §14に、Main draft §2.1と補助契約 §§2〜4 / 6 / 7の項目単位Traceability Matrixを追加した。

### 19.1 確認結果

- Main §2.1の13工程を個別に照合した。
- 方向性が一致するのは、Intent先行永続化、PREPAREDのSource/DB Commit前配置、Source Commit後のABORTED禁止・同一Operation再開、MarkerとMirrorの同一Transaction、終端Receiptの不変性。
- 13工程の多くは部分一致であり、論理契約として完全同期済みとは判定しない。
- Main §2.1に明示されない補助契約項目として、Envelope / Eventの詳細Schema、Envelope/Event Hash、Event Ordinal / Previous Event Hash、Event Payload / Actor、ABORTEDの積極的不存在証明がある。
- Mainと補助案のHash項目（DB Commit Payload Hash / Expected DB Marker Payload Hash等）は、同一範囲・同一意味と確認できない。
- Receipt ID決定方式、Operation Plan完全性、Hash自己参照除外、Event Ordinal発行/消費/部分書込み、Manifest predecessor競合、DB Marker不存在の確定条件は未解決。

### 19.2 変更判断

Main §2.1本文は変更していない。補助契約の追加項目をそのままMainへ転記すると、authority・Hash範囲・Ordinal・競合規則が未決定のまま規範化されるためである。

次の論理作業は、Receipt Contract §14.3に列挙した未決定事項を個別に閉じ、Main §2.1 / §2.2 / §2.3と補助契約を同期改訂するための変更表を作成すること。未承認アルゴリズム・Namespace・Hash規則・物理保証を先行採用しない。

**監査結論:** 項目照合は完了したが、同期完了ではない。DB-RV-03はOPENのまま。v0.8.3承認、Main反映、物理設計、DDL、DB生成、Migration、Restore、実装、PR、main反映を許可しない。


## 20. Receipt Recovery / Main §2.1〜§2.3 同期決定台帳の追加（2026-11-21）

Receipt Recovery Contract §15に、Main §2.1（正規順序）/ §2.2（Receipt State）/ §2.3（Crash Recovery）を同時改訂するための同期変更表と論理決定台帳を追加した。

### 追加した整理
- Operation / Event Ordinal Authority、単一Writer、部分Tailの扱い
- Intent Plan完全性とReceipt Envelope再構成条件
- PREPARED Event欠落・部分書込み時の補完境界
- Manifest predecessor / Head競合の拒否・隔離条件
- DB MarkerとMirrorのPayload Hash同一性、Commit結果不明時の保留
- VERIFIED判定における依存参照閉包
- Intent / Plan / Envelope / Event / Marker Hashの自己参照除外範囲
- Receipt ID決定的導出とUUIDv5 Namespace未承認の境界
- 論理決定と物理方式・耐久試験の責任分離

### 判定
- Main §2.1〜§2.3本文は変更していない。
- 現行資料から導ける安全側規則を候補として記録したが、未承認事項を規範化していない。
- Receipt ID、Hash範囲、Ordinal Authority、Manifest競合、DB Marker不存在の確定条件は未決定。
- DB-RV-03はOPEN。文書上の変更表作成は進捗であり、Blocker解消ではない。
- fsync / atomic rename / SQLite durability / crash injectionは物理・実装段階へ保留し、未実施をPASS扱いしない。

### 承認境界
v0.8.2 ORANGE / v0.8.3未承認、UUIDv5 Namespace未承認・未採用を維持。DDL / DB生成 / Migration / Restore実行 / 実装 / PR / main反映 / mergeなし。


## 21. Receipt Hash / ID依存関係監査（2026-11-21）

Receipt Recovery Contract §16で、Intent Plan / Receipt Envelope / Receipt Event / DB MarkerのHash・ID依存関係を項目単位で監査した。

### 新たに確認した問題
- Receipt再構成手順はIntentにExpected Receipt Hashを固定するとするが、Intent Plan最低Field一覧にExpected Receipt Hashがない。
- Operation Plan Hash / Intent Hashの包含関係・生成順が定義されていない。
- Envelope Hash / Event Hashの自己参照Field除外とCanonical serializationが未定義。
- Expected DB Marker Hash / Expected DB Marker Payload Hash / DB Commit Payload Hashの同一性・包含関係が未定義。
- Marker Payloadが自身のExpected Hashを含む場合、自己参照となる可能性がある。
- Source Manifest Head / Source Commit HashとReceipt Hashの相互包含範囲が未定義。

### 判定
Hash依存グラフが循環しないことを現行資料から証明できない。ただし循環が実装上発生していると断定するものではなく、Hash入力・除外・生成順の仕様不足として扱う。Expected Receipt HashのField欠落も確認事項として残す。

### 次の作業
- 各HashのCanonical Payload Field一覧を抽出。
- Hash生成順を依存グラフ化し、自己参照・後段値参照・相互依存を分類。
- Hash依存関係を閉じるために必要な統括判断と、文書内で根拠を持って定義可能な事項を分離。
- Main §2.1〜§2.3および補助契約への同期差分を更新する。

### 承認境界
Hash algorithm、Canonicalization、UUIDv5 Namespace、Receipt ID方式は未承認・未採用。DB-RV-03 OPEN。Main本文は未変更。DDL / DB生成 / Migration / Restore実行 / 実装 / PR / main反映なし。


## 22. Operation Ordinal / Receipt Event Ordinalの規則分離（2026-11-21）

§15.2のOrdinal候補規則を、既存Main / Receipt Schemaの明示記述に合わせて修正した。

- Operation Ordinal: Main §2.3の現行規則どおり欠番を許容し、再利用しない。発行Authority・消費点は未確定。
- Receipt Event Ordinal: Receipt Event Schemaの「Event Ordinal gapは検証失敗」を維持し、連続Chainとする。発行Authority・部分書込み後の復旧条件は未確定。
- 両者を一律に「欠番許容」または「欠番禁止」と扱わない。
- 部分Tailを黙って切り捨てたり、その後ろへ追記したりせず、証拠を保全して隔離する候補方針は維持する。

これは既存記述の整合化であり、Ordinal Authorityや物理的な追記・耐久方式の確定ではない。DB-RV-03 OPENを維持する。


## 23. Hash DAG候補・生成順・統括判断事項（2026-11-21）

Receipt Recovery Contract §17に、現行Hash Fieldの生成時点・参照関係の一覧と、非循環化候補を追加した。

### 追加した発見
- Expected Receipt HashをEnvelope Hashと解釈する場合、Intent Hash → Envelope Hash → Intent Hashの循環候補が生じる。
- Expected Receipt Hashが別Hashなら、その意味・対象Payloadが未定義。
- DB MarkerはSource Commit Hashを含む一方、Expected DB Marker HashはPREPARED時点で固定する案となっており、Source Commit Hashを事前確定できる証拠が不足。
- Expected DB Marker Payload HashをMarker自身のCanonical Payloadに含める場合、自己参照となる。
- Plan / Intent / Envelope / Source Commit / Event / MarkerのHash生成順・対象Field・自己Hash除外を別々に定義する必要がある。

### 非循環化候補
Plan Payload → Plan Hash → Intent Payload / Intent Hash → Receipt Envelope / Envelope Hash → Source Commit / Source Commit Hash → Receipt Event / Event Hash・DB Marker / Marker Payload Hash → DB_COMMITTED Event、という候補順を記録。後段Hashを前段入力へ逆流させない案である。ただしExpected DB Marker Hashの要件との整合は未解決。

### 統括判断が必要な事項
- Expected Receipt Hashを削除するか、別の非循環Hashとして定義するか。
- Expected DB Marker HashをPREPARED時点で固定するか、Source Commit後に計算するか、別概念へ分けるか。
- Marker Payload HashのCanonical対象と自己Hash Fieldの格納場所。
- Receipt IDの決定的導出方式・Namespace・version。

### 判定
これは非循環化の候補であり、規範仕様・承認済みの設計ではない。Hash algorithm / Canonicalization / Namespaceを採用していない。DB-RV-03 OPEN。Main本文未変更。DDL / DB生成 / Migration / Restore / 実装 / PR / main反映なし。


## 24. Intent後・Receipt作成前のABORTED経路不整合（2026-11-21）

### 24.1 照合した記述
- Main §2.3「Intent後、Receipt PREPARED前」: 「同一Operation ID / OrdinalでReceipt PREPAREDを作成、またはABORTEDを記録」と記載。
- Receipt Contract §4 Event遷移表: 未作成 → PREPARED と PREPARED → ABORTED のみ定義。未作成からABORTEDへの直接遷移は定義されていない。
- Receipt Contract §6 Crash Matrix: Intent後はEnvelopeを再構成しPREPARED、Envelope後・PREPARED Event前はPREPARED Eventを補完する。
- State Transition Matrix §4: 旧行は「Envelope作成後にABORTED Event」としており、PREPARED Eventを先に追記する必要が明示されていなかった。

### 24.2 不整合判定
Main §2.3は、Receipt Event遷移表に存在しない「Intent後・PREPARED前からABORTED」への直接遷移を許すように読める。またState Transition Matrix旧行はEnvelope作成後にABORTED Eventを追記するとだけ記載し、PREPARED Eventの先行を欠いていた。これは単なる説明不足ではなく、Event Chain上の許可遷移・Ordinal順序・復旧処理を曖昧にする。

### 24.3 安全側の同期修正案
State Transition Matrix Draftは次の2行へ修正した。
1. Intent永続化後・Envelope作成前: 同一OperationからEnvelopeを再構成・永続化し、PREPARED Eventを追記する。
2. PREPARED成立後・Source Commit前の中止: Source Commit不存在の完全検証と明示中止Intentを確認した場合のみ、同一ReceiptへABORTED Eventを追記する。不成立なら保留またはQUARANTINED。

この修正はReceipt Contract §4 / §6と整合する。Main §2.3本文は未変更であり、統括承認前に規範反映していない。

### 24.4 残る統括判断・同期作業
- Main §2.3の該当行を、Envelope / PREPARED Event / ABORTED Eventの順序が分かるように改訂するか承認が必要。
- ABORTED Event Payloadに必須のOperator Intent / Actor / Timestamp / Source Commit不存在証拠参照の完全Field定義は引き続き必要。
- PREPARED EventのOrdinal消費・部分書込み復旧はReceipt Event Chainの規則と同期する必要がある。

### 24.5 状態
State Transition Matrix Draftは修正済み。Main §2.3は未変更。Receipt Contract §4の許可遷移と整合した候補修正であり、DB-RV-03全体の解決・承認を意味しない。DB-RV-03 OPEN、v0.8.3未承認を維持する。


## 25. Operation Ordinalの部分Intent時における消費境界（2026-11-21）

### 25.1 照合結果
Main §2.1はOrdinal消費点をIntent永続化完了時とする一方、Receipt Contract §2 / §6は部分Intent・不正JournalでもOrdinalを再利用せずQUARANTINEDとする。Intent append中にクラッシュし、完全永続化か部分Tailかを確定できない場合のOrdinal状態は、現行Mainの「未消費 / 消費済み」だけでは表現されない。

### 25.2 安全側の修正案
- Intentが一切存在しないことを検証できる場合のみ未消費。
- 完全IntentがHash一致で検証できる場合は消費済み。
- append結果不明・部分Tail・Hash不一致・競合の場合は消費状態を推測せず、Ordinal再利用禁止・Physical Run QUARANTINED。
- 隔離中Physical Runで次Ordinalを推測発行しない。Recovery Operationの発行条件・Authorityは別途確定する。

State Transition Matrix Draftへ「Intent書込み中・結果不明」の隔離行を追加した。Receipt Contract §18に状態区分候補とAuthority未決定事項を記録した。

### 25.3 判定
Operation Ordinalは欠番許容・再利用禁止、Receipt Event Ordinalは連続必須。両規則を混同しない。Ordinal Authority / Recovery発行条件は未決定。Main §2.1〜§2.3は未変更。DB-RV-03 OPEN。


## 26. Main §2.2 Receipt Stateの証拠境界照合（2026-11-21）

### 26.1 現行MainのState定義
- PREPARED: Intentが永続化され、DB Commit前の証拠が存在する。
- SOURCE_COMMITTED: 対象Source Revision / Manifest Headが永続化され、Hash照合済み。
- DB_COMMITTED: DB Mirror Markerが同一TransactionでCommitされ、読戻し照合済み。
- VERIFIED: 関連Hash・外部正本・Markerの整合性が確認済み。
- ABORTED: Source Commit前の中止が確定。
- QUARANTINED: 証拠不整合・競合・検証不能で隔離。

### 26.2 Receipt Contract / State Matrixとの照合
| State | Main §2.2の明示範囲 | Receipt Contract / State Matrixの証拠境界 | 差分 |
|---|---|---|---|
| PREPARED | Intent永続化 + DB Commit前の証拠 | Intent + immutable Envelope + 検証済みPREPARED Event | MainがEnvelope / PREPARED Eventを明示していない |
| SOURCE_COMMITTED | Source Revision / Manifest Head永続化 + Hash照合 | Expected predecessor / 現Head / Source Payload Hash検証 + SOURCE_COMMITTED Event | MainがEvent Chain・predecessor照合の必須性を明示していない |
| DB_COMMITTED | 同一Transaction Marker + 読戻し照合 | Marker Payload / Source Commit / Intent / Receipt IDの整合 + DB_COMMITTED Event | MainがMarker Hash対象・Event証拠境界を明示していない |
| VERIFIED | 関連Hash・外部正本・Marker整合 | Intent Planの依存閉包・Journal / Receipt / Event Chain / Source / Markerを検証後、VERIFIED Event | 「全依存」の閉包とVERIFIED Event自体の検証範囲が未定義 |
| ABORTED | Source Commit前の中止が確定 | PREPARED成立後、明示中止Intent / Actor / Source Commit不存在の完全証拠を確認してABORTED Event | Mainは明示中止Intent・不存在証拠・Envelope/Event順序を明記していない |
| QUARANTINED | 証拠不整合・競合・検証不能 | 元Receiptを不変保持し、新Recovery Operationでのみ解決 | MainはRecovery Operationとの関係・元Receipt不変の証拠境界が簡略 |

### 26.3 同期修正候補
1. PREPAREDは、完全なIntent、immutable Receipt Envelope、検証済みPREPARED Eventが揃った状態とする。
2. SOURCE_COMMITTEDは、Intentに固定したExpected predecessor / Source Payload Hashと現Manifest Headを検証し、SOURCE_COMMITTED Eventが検証済みの状態とする。
3. DB_COMMITTEDは、MarkerとMirrorが同一TransactionでCommitされ、Marker Payload Hash / Source Commit Hash / Receipt / Intentとの整合を検証し、DB_COMMITTED Eventが検証済みの状態とする。
4. VERIFIEDはIntent Planで固定した依存閉包の全証拠を再検証し、VERIFIED Eventが検証済みの状態とする。
5. ABORTEDはPREPARED成立後に限り、明示中止IntentとSource Commit不存在証拠を確認したEventとする。
6. QUARANTINEDは元Receiptの終端・不変状態とし、Recovery Operationは別ID / Ordinal / Receiptで記録する。

上記はReceipt Contract / State Matrixとの整合を目的とした候補文であり、Main §2.2は未変更。各Hash / EventのCanonical Payloadと依存閉包が未決定のため、現時点で規範確定できない。

### 26.4 判定
Main §2.2のState名・大枠はReceipt Contractと一致するが、各Stateを成立させる証拠境界の明示度が異なる。Main本文へ状態名だけを転記しても受入条件は閉じない。§2.1 Hash / Event定義、§2.2 State定義、§2.3 Crash Recoveryを一括同期する必要がある。DB-RV-03 OPENを維持する。


## 27. Receipt Event初回表現・Ordinal・partial tailの追加照合（2026-11-21）

### 27.1 確認事項
Receipt Contract §3.2は初回Event以外にPrevious Event Hashを要求するが、初回Eventの表現（Field省略 / NULL / 空値 / Genesis Hash）とEvent Ordinal開始値を定義していない。またEvent Ordinal gapを検証失敗とする一方、Event append中のクラッシュ・部分Tail・append結果不明時のOrdinal消費点が規定されていない。

### 27.2 重要な区別
- Operation Ordinal: 欠番許容・再利用禁止。
- Receipt Event Ordinal: gapは検証失敗、連続必須。
- Operation OrdinalのUNUSED / CONSUMED / INDETERMINATE_QUARANTINED案をEvent Ordinalへそのまま転用しない。Event Chainでは部分Tailがある時点で後続Eventの連続性を検証できないため、同一Chainの追記を停止する必要がある。

### 27.3 補助契約・Matrixへの追加候補
- 初回Previous Event Hashの符号化、初回Ordinal、初回Event Typeを明示定義する。
- Event append未開始を証明できる場合のみ次Ordinalのappendを開始する。
- 完全Eventが読み戻せHash Chainを検証できる場合は既存Eventとして受理し、重複追記しない。
- append結果不明・部分Tail・Hash不一致・Writer競合はReceipt Event Chainを隔離し、後続Event・Ordinal飛越し・黙示Tail切捨てを禁止する。
- Event Chainの単一有効Writer、Event Type別発行Authority、Recovery Operationの追記権限を定義する。

### 27.4 判定
これはSchema / Authorityの欠落であり、特定実装で部分Eventが必ず発生するという不具合断定ではない。fsync / atomic append / Tail修復は物理設計で別途検証する。Main §2.1〜§2.3未変更、DB-RV-03 OPEN、v0.8.3未承認を維持する。


## 28. Manifest Head競合と後続Commit後のRecovery判定監査（2026-11-21）

### 28.1 発見した不足
前回までの§15.2「Headを再読込し、当該OperationのExpected Head / Commit Hashと一致する場合のみSource Commit済みと認定」という記述は、Recovery前に別Operationが後続Commitを完了しHeadが進んでいる場合を扱えていない。現在Headが先行OperationのCommit Hashと一致しないことは、そのOperationがCommitされなかった証拠にはならない。

### 28.2 競合条件の分離
1. **Stale predecessor:** Expected predecessorが現Headと一致しない状態で新規Commitしようとする。Commit拒否が必要。
2. **Commit済み・後続Headあり:** 当該Operationの不変Commit証拠がManifest履歴に存在し、後続Headの祖先である可能性がある。履歴検証なしに不成立と判定できない。
3. **Commit結果不明・履歴なし:** 当該Commitの存在も不存在も完全に証明できない。未Commitと推測せず保留・隔離。
4. **Operation ID重複Commit:** 同一Operation IDに異なるpredecessor / payload / commit identityが存在する場合は証拠矛盾。

### 28.3 補助契約・Matrixへの同期候補
- Operation単位の不変Commit証拠とManifest履歴上の祖先関係を、Source Commit成立判定に使えるよう論理契約を定義する。
- Expected predecessor不一致時はstale Commitを拒否し、旧Headで上書きしない。
- 現在Headが後続Commitへ進んでいても、当該Operation Commitが履歴上の祖先として検証できる場合はCommit成立を認定できる候補とする。
- Commit証拠の欠落・履歴不完全・部分Tail・Operation ID重複は、Source Commitを推測で確定せず保留または隔離。
- CAS / append-only log / Merkle DAG等の物理構造は選択しない。

### 28.4 訂正・状態
本監査により、§15.2のHead一致条件は単独では不十分と判明。§20で履歴上のCommit存在・祖先関係を含む候補に限定した。Main §2.1 / §2.3は未変更。DB-RV-03 OPEN。v0.8.3未承認。


## 29. Writer Authority / stale owner / Recovery Authorityの境界監査（2026-11-21）

### 29.1 Writer競合の追加不足
Main §2.1はPhysical Run単位の排他ロックを要求するが、Lock Owner identity、authority issuer、stale lock判定、Writer交代後の旧Writer拒否条件を定義していない。Receipt Contract §15.2の単一Writer案だけではsplit-brain防止の受入条件が閉じない。

### 29.2 Authority scopeを分離
- Physical Run外部正本のWriter Authority
- Operation Ordinal発行Authority
- Receipt Event Ordinal発行Authority
- Recovery Operation発行Authority
- Receipt Event Type（ABORTED / VERIFIED / QUARANTINED等）発行Authority
- Shared DB transactionの競合制御

これらは関連するが同一権限ではない。特にPhysical Run単位のlockを保持するだけで、Ordinal発行やRecovery / 終端Eventの権限が自動的に与えられるとは扱わない。

### 29.3 論理受入候補
同一Physical Runの外部正本に同時に有効なWriterは一つのみとし、Authorityの取得・更新・失効・交代は検証可能な証拠を残す。Writer交代後の旧Ownerが古い権限だけで更新できないことを証明する。Authority不明・複数Writer・世代矛盾は更新停止・隔離候補とする。lease / fencing token / OS lock / CAS等の具体方式は選択しない。

### 29.4 Recovery Authorityの未定義
現行資料はQUARANTINED元Receiptを編集せず新Recovery Operationで解決するとするが、誰がRecoveryを開始できるか、何を検証・変更できるか、元ReceiptのEvent Chain / Manifest Headを継続できるか、結果をどのArtifactに記録するかが閉じていない。Recovery権限が定義されるまで、Recovery Operationが元Receiptや元Manifestを修復・上書きできると推測しない。

### 29.5 判定
Writer / Ordinal / Recovery / Event Type / Shared DBのAuthorityを分離して定義する必要がある。単一WriterとRecovery Operationの存在だけではAuthority設計は完了しない。DB-RV-03 OPENを維持する。


## 30. DB-RV-01 / 02 / 04 / 05 / 06 / 07 / 08 横断整合監査（2026-11-21）

本節はMain v0.8.3、Entity Inventory、State Transition Matrix、Canonical Binary Name Audit、DB Evidence Ledger、V082 Crosswalkを照合した差分記録である。Main本文の修正・統括判断・実装許可ではない。

### 30.1 DB-RV-01 / 02 / 08 — Run / Scope / Session / Assignment / Measurement

**一致を確認した骨格**
- Physical Run IDとDB Run IDを分離し、DB RunはPhysical Runにつき最大1件。
- RUN_SCOPEはPhysical Run初期化時にScope単位で存在する。
- SessionはScopeの初回確定ASSIGNEDで一度だけ生成し、以後Assignment変更で削除・再採番しない。
- Assignment-at-MeasurementはMeasurement開始時のSnapshotを保持し、Current Assignmentで過去測定の帰属を変更しない。
- ANONYMOUS期間のMeasurement / RawLogは後日DB取込・Mirror化・Instance再紐付けを禁止。NONEは既存DB管理Measurementに限る明示Association候補。

**未解決・同期不足**
1. NONEの既存DB管理Measurementを明示Associationする場合、既存Session membershipをどう扱うか未定義。Session生成前のNONE Measurementと、既存Session生成後のNONE Measurementを分ける必要がある。
2. Main §1.2(6)のSession membership定義は「Session生成後にDB登録されたMeasurement集合」と記述する一方、NONE Associationは測定時Assignment=NONEを維持して許容される。membershipへ追加するのか、監査関連だけを持たせるのか決まっていない。
3. SessionのCanonical SchemaはPhysicalRunID + ScopeKeyであり、Session独立IDを持つか、別途決定的IDを発行するか未確定。
4. Assignment SnapshotのIdentity（独立UUID / Scope + Revision / Content Hash）とRevision開始値・欠番・前Revision Hash・Actor / Time / Reasonが未確定。
5. Measurement Envelopeの全属性・型・NULL・Capture終端・StatusとIntegrityの分離、Profile Snapshotの完全属性が未確定。
6. PHYSICAL_RUN_CLOSEDのClose Actor / UI / Operation / Capture終端・取消不可条件、全ScopeのClose順序は正式機器契約と照合が必要。

**判定:** 基本ライフサイクルは一貫するが、NONE AssociationとSession membership、Snapshot / Measurement完全Schemaが閉じていない。DB-RV-01 / 02 / 08は全体PASSにできない。

### 30.2 DB-RV-04 — Aggregate Request / Attempt / Result / Pointer

Main §3.2 / §3.3とState Matrix §5を照合した。

| 論点 | Main | State Matrix / 補助案 | 差分 |
|---|---|---|---|
| Current Valid | Latest Requested RequestのInput Set Hash一致 | Request Fingerprint全体一致を要求 | MainはAssignment Snapshot Set Hash / Algorithm / Configuration / Policy等の一致条件を明示していない |
| 遅延旧Request成功 | 最新要求・入力とのInput Set Hash一致時のみPointer更新 | Latest Requested Request IDとFingerprint一致が必要 | 同一Input Hashで異なるRequest / Algorithm / Assignmentの誤昇格を防ぐ境界がMainに不足 |
| Latest Successful順序 | 「最も新しい成功Result Revision」 | Request Ordinal優先、Attempt Ordinal等の明示順序 | 完了時刻・Request順・Attempt順の優先関係をMainで確定していない |
| FAILED | 全Attempt失敗・再試行終了 | Retryable / Retry Closedの明示状態/Eventが必要 | 「再試行終了」を誰がどの証拠で閉じるかMainで未定義 |
| Pointer再構築 | DB Mirrorの派生Pointer | Request / Attempt / Result履歴から再構築 | stale pointer・同時更新・遅延成功の復旧境界が未完了 |

**判定:** Request / Attempt / Resultの分離は一致するが、Current Validの判定基準とRetry終端・Pointer順序は同期が必要。State Matrixの候補をMainの規範とみなさない。

### 30.3 DB-RV-05 — Artifact Input DAG

Main §4の不変性・循環禁止・Input Set Hash順序は示されている。一方、Entity Inventory §6 / §8では次が未定義。
- Analysis Artifact / Simulation Artifactが共通Entityか別Entityか。
- Artifact IDとResult Payload Content Hashの区別・発行Authority。
- Artifact InputのInputType許容集合、全Polymorphic Reference対象Entity、Role / Ordinal domain、NULL / uniqueness。
- Source Revision / Input Hash / Requiredの完全Field schemaとCanonicalization。
- ArtifactのStatusとIntegrity、失敗・隔離・SupersededのLifecycle。
- Input Entityの削除禁止とRetention / Restore境界。

**判定:** DAG非循環・入力Hash一致・再解析時新Artifactという骨格はあるが、Entity完全Schemaと多態参照が未完成。DB-RV-05は全体PASSにできない。

### 30.4 DB-RV-06 — Canonical Binary Name v2

現行資料で確認できる範囲:
- Main §5.3: 11 Schema rows。
- Entity Inventory: 23 Logical Entity。直接対応Schema 10種、未定義13種。OPERATION_EVENTはInventoryへの対応自体が未確定。TEST_VALUEは汎用vector用でInventory外。
- Canonical Audit: §5.3の11 Entity正常Name byte vectorを用意。独立計算の初期7 vector一致、Expected Hex 29件の構造解析29/29通過。
- ただし全Field境界 / NULL / empty / domain / overflow / invalid-input vector、Unicode data version、Version更新規則、Entity uniqueness、Namespace全履歴調査、UUIDv5 RFC vector、独立2実装照合は未完了。

**判定:** byte grammarの一部・既存vectorの構造は確認済みだが、Entity全体のIdentity分類・完全Schema・実装相互検証・Namespace承認は未完了。DB-RV-06は未承認。

### 30.5 DB-RV-07 — External Source / DB Mirror / Restore

Main §6 / §9とEntity Inventory / Restore補助案の間で、外部正本からMirror再生成可能という基本方針は一致する。ただし、以下はEntityごとの完全性証拠が不足。
- RawLog ObjectとRawLog Referenceのidentity・Hash対象・所有権・Retention。
- Manifest / Snapshot / Assignment History / Receipt / Event / Artifact / Aggregate各外部正本の完全な列挙・依存閉包。
- Restore Phase A / Bの各検査結果とReceipt state確定のauthority。
- DB Mirrorの欠落・破損時に再生成可能なEntity / 再生成禁止Entity / 参照のみEntityの完全分類。
- RawLog durabilityはIssue #35の欠損許容契約と種別ごとに照合が必要。全RawLogへ同じfsync保証を適用する前提は未承認。

**判定:** External Source優先・DB Mirror再生成の方向は一貫するが、全Entity単位のAuthority / Restore条件・RawLog耐久性は未完成。

### 30.6 DB-001〜124 / V082 Crosswalk

Evidence Ledger / Crosswalkの現行状態:
- DB-001〜056: 会話記録由来の短縮定義を回収。原本文書・正式承認・番号付きテスト実物は未照合。
- DB-057〜078: 追加範囲の履歴のみ確認。個別本文未回収。
- DB-079〜109: 維持・保全指示の範囲履歴のみ。個別試験実物未確認。
- DB-110〜124: 追加指示の範囲履歴のみ。個別本文・試験実物未回収。
- DB-125〜154: 正式体系対象外として撤回。DB-155〜176: 提案番号撤回、再利用禁止。
- V082-001〜053: 53件すべてDB-001〜124との確定対応 / 部分対応 / 重複は0件。未対応付け53件。未カバー確定も0件（証拠不足で判定不能）。
- DB-032のANONYMOUS後日関連付け期待はCC-02と競合する旧記録として現行範囲から隔離。
- DB-007「NONE Session」は初期NONEのSession新規生成を意味するか、既存SessionのNONE状態を指すか未確定。V082-023と統合しない。

**運用処理:** 原文未回収IDは削除・推測補完せず、参照専用・実行不可として凍結する。これは不存在・未作成の断定ではない。新しい一次資料が得られた場合のみ再評価する。

### 30.7 横断判定
- DB-RV-01 / 02 / 08: Session membership・完全属性・Close証拠が未完了。
- DB-RV-03: Manifest履歴・Writer / Ordinal / Recovery Authority・Hash / ID依存が未完了。
- DB-RV-04: Current Valid / Latest Successful / Retry終端がMainと補助案で未同期。
- DB-RV-05: Artifact Type / Input polymorphism / identity・lifecycleが未完了。
- DB-RV-06: 23 Entity全体のCanonical identity coverage未完了。
- DB-RV-07: 全EntityのSource / Mirror / Restore / durability境界が未完了。
- DB-RV-08: Measurement Envelope / Assignment Snapshot / Capture終端完全Schemaが未完了。

本監査は現行文書間の差分を示す。Issue #209の正式な再審査・統括判断を代替せず、v0.8.3承認や実装移行を意味しない。


## 31. Motor / Battery / Anonymous正式契約の一次Issue照合（2026-11-21）

### 31.1 Motor — Issue #35（現行仕様唯一の正本）
Issue #35本文は、担当側が過去Issue・過去コメント・旧仕様・旧Commitから未記載仕様を復元せず、未記載事項を未確定として司令塔へ戻す権限境界を明示する。またRawLog v1 / v2を別形式とし、v1の自動変換・推測変換を禁止、v2を新規測定の正規形式とする。A0 / A1の独立性、A2 / A3の参考値限定、受信RawLog原文保持も明記する。

DB側の適用:
- RawLog v1の列・意味を新DB schemaへ推測転記しない。
- RawLog v2の完全Field Schema・保存表現・必須/任意属性はIssue #35 / Issue #170の正式決定を受領するまで補完しない。
- 受信原文とDerived / 推定値を分離し、DB側でraw dataを補正・再構成しない。
- Issue #35に明記されないRawLog durability / retention / loss toleranceを、DB部門の一般的な設計慣行で確定しない。
- Motorの制御・センサー・Capture終端条件をDB部門で変更しない。

### 31.2 Battery — Issue #16（E2E検証タスク）
Issue #16が明示するのは、Battery 5A DATAの取り込み、CH1 / CH2独立Session、Measurement保存、Feature Extraction、Benchmark Result保存、mAh / Wh / 電圧降下の妥当性、Measurement不変性のE2E検証である。境界としてArduino FW変更なし、内部抵抗算出なし、評価スコア基準確定なし、STARTALLのCH1 / CH2合算なしを定める。

Issue #16は完全なBattery DB / RawLog Data Contractではない。したがって以下は未受領として扱う。
- Battery Model / Instance / Profileの完全属性とIdentity。
- CH1 / CH2 Scope / Measurement / Session / Benchmarkの完全CardinalityとLifecycle。
- RawLog v2 / Sample Locator / Channel metadata / Capture終端Schema。
- Benchmark Feature / Resultの完全Schema・Algorithm / Configuration provenance。
- Battery独自のdurability / retention / loss tolerance。

CH1 / CH2独立性は現行要件として保持し、平均化・合算を導入しない。ただしDB部門はBattery実装を変更せず、未受領仕様を推測で補わない。

### 31.3 Anonymous — Issue #201とIssue #210 CC-02
Issue #201はDB不存在時のMainUI起動と匿名運用の境界を定め、DB file / schema / empty DB / migration / initialization / test data / legacy data migrationを禁止する。Issue #210 CC-02はANONYMOUS期間のMeasurement / RawLogを現行設計範囲で後日DB取込・Mirror化・Instance再紐付けしないことを明示した。NONEは既存DB管理Measurementに限る明示Associationを設計対象として許容する。

よってDB設計上、Anonymous RawLogの後日取込経路を追加しない。NONE AssociationのSession membershipはIssue #210が決定していないため、統括判断待ちのまま残す。

### 31.4 判定
Motor / Batteryの不足契約はDB部門の裁量で補完しない。Issue #35 / #16 / #201 / #210の範囲を維持し、正式契約の受領・統括判断後にのみ関連DB条項を同期する。


## 32. Entity 23種の根拠・Authority照合と未回収契約境界（2026-11-21）

Entity Inventory §10に、Main §§1–10、Issue #210 CC-01/02、Motor Issue #35 / #170、Battery Issue #16の根拠をEntity単位で対応付けた。

### 32.1 新たに明確化した点

- Main §6の正本 / Mirror表はAuthority分類の論理案であり、全Entityの完全Schema・Retention・Restore実証ではない。
- Main §7はMeasurement Envelopeの最低属性を示すが、Motor/Battery別のCapture終端・RawLog全属性は確定しない。
- Main §8はRawLog保存完了の論理要求を記載する一方、OS/filesystem別のfsync保証・電源断耐久性は物理実証が必要。Issue #35 / #170のMotor RawLog契約、およびBattery Issue #16のE2E検証範囲から、機器別の完全なdurability / retention契約を推測してはならない。
- Main §9はRestore / Bootstrapの二段階手順案である。各Entityの完全な証拠集合、復元可否、Loss toleranceがすべて定義・実証済みという意味ではない。
- OPERATION_EVENTをAssignment HistoryまたはOperation Journal Eventへ自動的に割り当てない。Intent / Event / SnapshotのEntity境界は未決定。
- Analysis ArtifactとSimulation Artifact、Recovery OperationとIntegrity Report、RawLog ObjectとRawLog Referenceはそれぞれ概念上区別するが、全Entityの独立ID・物理表分割までは決めていない。
- Aggregate Pointerは派生値として扱う候補であり、独立IDや保存表を追加する根拠はない。
- NONE Session membershipはIssue #210で未決定。Inventory §10.2もA/B/Cのいずれかを採用したとは扱わない。

### 32.2 監査結論

23 Entityの根拠所在を一覧化できたが、完全なField Schemaを提供する一次契約は不足している。特にMotor RawLog v2 / Battery Measurement・RawLog / Run管理Close / Profile Snapshot / Artifact / Recovery authorityは、各契約所有者または統括から正式な根拠が必要である。DB部門はそれらを推測補完しない。

本監査は文書調査のみ。Main本文、DDL、DB、Migration、Restore実行、機器実装、PR、main反映は変更していない。


## 33. DB-RV-04の選択肢・証拠要件を分離（2026-11-21）

Main §3とState Matrix §5の差分について、未決定事項を選択肢として分解し、Entity Inventory §11へ記録した。

### 33.1 確認された差分
- Main §3.2 Current ValidはInput Set Hash一致を中心に記述するが、State Matrix §5.1はAssignment Snapshot Set / Algorithm / Configuration / Measurement・Profile・Policy Revision / Aggregate Definition Versionを含むRequest Fingerprint全体一致を要求する。
- Main §3.2のLatest Successfulは「最も新しい成功Result Revision」とだけ記載し、Request Ordinal / Attempt Ordinal / Result Revision順序の優先関係がない。
- Main §3.3のFAILEDは「全Attempt失敗かつ再試行終了」とするが、State Matrix §5.3が要求するRetryable / Retry Closedの明示Event・状態と、閉鎖権限・Actor / Time / ReasonがMainに定義されていない。
- Pointerの同時更新・古いWorkerの遅延成功・再構築時の順序と整合性保証が未完了。

### 33.2 未決定選択肢
- FingerprintにRequest IDを含める案 / 計算条件だけを含める案 / Input Set Hashのみの案を比較。Input Set Hash単独では要求条件全体を表さない。
- Fingerprint Hashのみ保存する案と、全構成Field + Hashを保存する案を比較。再現・監査のためのpreimage保持が必要か未決定。
- Latest SuccessfulをRequest Ordinal + Attempt Ordinalで順序付ける案と、Result Revision独立Ordinalを使う案を比較。
- Retry Closedを追記Eventとする案、別状態記録とする案、現状失敗から推定する案を比較。明示終端なしのFAILED推定はMatrix案と整合しない。
- Pointerの条件付き更新と履歴再構築の案を比較。物理Concurrency保証は未承認。

### 33.3 判定
分離・不変性・遅延旧RequestのCurrent Valid昇格禁止・Input Set Hash単独判定禁止・Retry終端の明示証拠要求は、現行資料から最低限維持できる。完全Fingerprint schema、順序キー、Retry Closed authority、Pointer concurrencyは決定待ち。Main §3は変更していない。


## 34. RawLog durability条件の適用範囲・証拠不足（2026-11-21）

Main §8のRawLog durability条件を、Motor Issue #35 / #170およびBattery Issue #16と照合した。

### 34.1 確認できたこと
- Main §8はfile fsync相当、read-back SHA-256、Path衝突検査、Atomic Rename、directory fsync相当、final read-back hash、Journal completion Event、PENDING_RECOVERY、同一ID/Hash冪等再試行を論理受入条件として列挙する。
- Motor Issue #35はRawLog v1保全・非変換、v2独立Schema、保存形式等をIssue #170で定義する責務境界を明示する。Issue #170本文は通信・Python入力・RawLog v2 schema/validationを定義する作業を記載するが、Main §8の全Filesystem durability要件が確定済みであることは確認できない。
- Battery Issue #16は5A E2E検証であり、Battery固有のRawLog durability / retention / loss toleranceを定義していない。

### 34.2 未閉鎖条件
RawLog ID発行Authority、Expected Hash対象byte範囲、Path grammar、Temp file ownership / orphan recovery、completion Event schema、PENDING_RECOVERY判定・Recovery authority、duplicate ID/pathの意味、Retention / loss toleranceが未定義。これらがないまま物理方式・実装・Restore完了を合格扱いしない。

### 34.3 受入ゲートを分離
- 論理契約: ID / Hash / Path / Event / retry / quarantine semantics。
- 物理Filesystem: fsync / directory fsync / rename / read-back / crash durability。
- 機器別契約: Motor v2 / Battery RawLog schemaとCapture終端。
- Restore: partial / missing / duplicate / hash mismatchを証拠別に判定。

Main §8の要求はDB論理案として残すが、各OS/filesystemで実証済みとは扱わない。Batteryへ同じ方式を適用するとも決めない。実装変更なし。

## 35. v0.8.3 Decision Baseline — 全未決定事項の処置確定（2026-11-21）

Main §14をDecision Authorityとして、従来のOPEN / TBD / candidateを以下へ整理した。

- **採用:** UUIDv4 identity、M4W-JCS-1 / SHA-256、Request Fingerprintの完全Field保存、明示Retry Closed、単一Manifest Commit Chain、単一Writer + Epoch、外部正本優先、二段階Restore。
- **不採用:** UUIDv5 / Canonical Binary Name v2、OperationIDからのReceipt ID導出、Expected Receipt Hash、PREPARED時点のExpected DB Marker Hash、Current Head単独のCommit証明、last-write-wins、Aggregate Pointerを正本とする方式。
- **適用対象外:** DB契約のないMotor/Battery Field、未知Profile / Artifact Payloadの意味解析、Anonymous後日DB取込、旧ID推測復元、未契約SampleLocator解釈。
- **fail-closed:** Unknown Schema / Field / EventType / InputType、partial tail、hash mismatch、fork、stale writer、unknown Capture End、未実証Filesystem / SQLite環境は拒否・OPEN維持・PENDING_RECOVERY・QUARANTINEDのいずれか。
- **Recovery Authority:** Bootstrap登録済みPROJECT_RECOVERY_ADMINのみ。v0.8.3では元証拠不変・QUARANTINED解除禁止。
- **Entity境界:** OPERATION_EVENT独立Entityは不採用、Aggregate PointerはDerived View、Analysis / Simulationは共通Envelope + ArtifactKind、Recovery OperationとIntegrity Reportは別Entity。
- **Session / NONE / ANONYMOUS:** Issue #210 CC-01 / CC-02を維持し、Main §14.1–14.2で具体的なSession membership / Association / Outcome動作を固定。

したがって論理設計の選択肢は残さない。残件は実装・試験・他部門正式契約・統括最終審査という証拠Gateであり、設計未決定とは区別する。

### 35.1 DB unavailable / ANONYMOUS / NONEの取扱い差分
- DB unavailable中はDB Run / Session / Measurement Mirrorを作成しない。復旧後は明示Bootstrapで外部ASSIGNED履歴を検証し、ASSIGNED時に取得された完全なMeasurementだけをMirror化できる。UUIDv4 IDはManifestへ先行記録する。
- DB unavailable中のNONE MeasurementはDB管理下に存在しないため、後日取込・Association禁止。
- ANONYMOUS期間のMeasurement / RawLogは、DB unavailableとは別のCC-02禁止境界であり、後日取込・Mirror化・再紐付け禁止。
- DB利用可能かつ当該Scope Session存在中に取得されたNONE Measurementのみ、既存DB管理Measurementとして明示Association対象になり得る。
- PHYSICAL_RUN_CLOSEDのActorIDは認証済みOperator principal。UI画面・ボタン名はAuthorityではなく、Client/UI versionは任意監査Metadata。

### 35.2 Battery Issue #16の限定的な保存許可
Battery Issue #16に列挙された5A DATAの取込み、共通Measurement Envelope、CH1 / CH2独立Session / Measurementの保存は対象に含める。RawLog Schemaが未回収のPayloadは原本byteとHashを保全するopaque保存に限定する。Feature Extraction / Benchmark Resultの再計算、mAh / Wh / voltage dropの数値妥当性判定、スコア、内部抵抗、CH1 / CH2合算は、単位・式・Capture End・RawLog Schemaの正式契約が揃うまで実施しない。
### 35.3 Aggregate Request / Attempt終端の追加決定
Request StateをOPEN / SUCCEEDED / FAILED / CANCELLED / INDETERMINATEに固定。Retry ClosedはFAILED Attemptが1件以上、RUNNING Attemptがない場合のみ許可。Attempt CANCELLEDだけではFAILEDにせず、明示Request CancelledまたはRetry Closedを要する。Attempt結果不明のcrashではWorker停止 / fencing proof前にAggregate OwnerをQUARANTINEDとして全更新停止し、proof後にのみINDETERMINATEへ終端。

## 36. Supersession Register — 旧OPEN / TBD記述の最終処置（2026-11-21）

**規範優先順位:** COMMON_DB_LOGICAL_DESIGN_v0.8.3_REMEDIATION_DRAFT.md §14（DB-RV-04は§3、DB-RV-05は§4、DB-RV-06は§5、RawLog durabilityの論理条件は§8）が現行Decision Authority。本書の§1〜§34にあるOPEN / TBD / candidate / decision pendingは調査時点の履歴であり、現行設計判断としては適用しない。矛盾時はMainの該当条項を優先する。

| 論点 / DB-RV | 最終状態 | 決定根拠 | 残るもの（設計未決定ではない） |
|---|---|---|---|
| DB-RV-01 Entity / identity | 決定済み | Main §§5.1, 5.3, 14.3 | 23概念の完全SQL列定義は本論理版対象外。契約未受領Payloadはopaque |
| DB-RV-02 Run / Session / Assignment / NONE | 決定済み | Main §14.1–14.3 | Run Manager / Session Managerの実装・権限試験 |
| DB-RV-03 Journal / Receipt / Recovery | 決定済み | Main §14.4、Receipt Contract §22 | filesystem append/fsync、Epoch fencing、SQLite crash/recoveryの実証 |
| DB-RV-04 Aggregate | 決定済み | Main §§3.1–3.3, 14.5 | Aggregate Manager/Worker実装と競合・crash受入試験 |
| DB-RV-05 Artifact DAG | 決定済み | Main §§4, 14.3, 14.5 | Kind別Payload契約受領と検証器試験。未知Kindはopaque / reject |
| DB-RV-06 ID / Hash / Canonicalization | 決定済み | Main §§5.1–5.3, 14.3 | UUIDv4 / JCS conformance試験。UUIDv5 / CBN v2は不採用 |
| DB-RV-07 RawLog / Restore | 論理境界決定済み | Main §§8, 14.6–14.8 | 機器別RawLog契約、OS/filesystem durability、Restore実証 |
| DB-RV-08 Cross-evidence / durability | fail-closed決定済み | Main §§8–9, 14.4, 14.7–14.8 | 対象環境でのSQLite / filesystem / crash試験 |

### 36.1 過去の未決定記述の置換規則
1. NONE Session membershipのA/B/C案は不採用。Main §14.1(4)–(7)のScope単位・Session存在条件・DB availability・ANONYMOUS禁止境界を採用。
2. UUIDv5 / Canonical Binary Name v2 / Namespace案は不採用。UUIDv4とM4W-JCS-1を採用。
3. Receipt ID deterministic derivation / Expected Receipt Hash / Expected DB Marker Hashは不採用。Main §14.4およびReceipt Contract §22の順序を採用。
4. Writer / Recovery / Event Type AuthorityはMain §14.4のAuthority Registry / EventType別発行権限に固定。物理fencing方式は指定せず、証明不能な実装を受入不可とする。
5. Aggregate Fingerprint / Retry / Result / PointerはMain §§3.1–3.3および§14.5に固定。旧選択肢は採用しない。
6. Artifact InputType / Link Role / Ordinal / RequiredはMain §14.5に固定。発行元ContractにないRoleや未知InputTypeは拒否。
7. RawLog完全Field Schema、機器固有Capture終端、Retention / loss toleranceはDB部門が創作しない。v0.8.3ではopaque保存とfail-closedのみを許可し、正式契約受領後の改訂事項とする。
8. 未回収DB-001〜124 / V082番号はREFERENCE_ONLY_NOT_EXECUTABLE。推測MappingはNO_MAPPING。存在しないと断定せず、根拠が届いた場合だけ再審査。

### 36.2 完了判定の分離
- **設計選択:** 本表によりOPEN / TBDを閉じた。
- **契約証拠:** Motor / Battery / Run Managerからの正式Schema・Lifecycle・Capture終端・Close authorityは未受領のものがある。未受領項目は本版の適用対象外またはopaque/fail-closedであり、他部門仕様を推測しない。
- **実証:** UUID/JCS、filesystem、SQLite、crash recovery、Restore、Concurrencyの受入試験は未実施。
- **承認:** v0.8.3はDraft。統括最終承認・実装許可・DDL/DB生成/Migration/Restore実行/PR/main反映を意味しない。


## 37. CC-02 / DB unavailable / Session membershipの最終整合処置（2026-11-21）

**この節は本書の旧OPEN / candidate記述（特に§30.7、§31、§35.1）を更新する現行DB部門Decision Baselineである。** Issue #210 CC-01 / CC-02およびIssue #201を上位根拠とし、Main v0.8.3 §1 / §14.1、Session Lifecycle §§1 / 4 / 5 / 7、State Transition Matrix §§1–3を同期対象とする。

### 37.1 DB unavailableはAnonymous Mode
- Issue #201はDB unavailable動作を既存Anonymous Modeへ統合し、障害期間中のRawLog / Captureをローカル外部正本へ保全する一方、後日DB取込・Instance再紐付けは将来の別設計範囲としている。
- よってDB unavailable期間はAssignment-at-MeasurementがASSIGNEDであってもAnonymous Modeとして扱う。新規DB Run / Session / Measurement Mirrorを作成せず、障害期間中のCapture / Measurement / RawLogを復旧後にBootstrap・取込・Mirror化・Associationしない。
- 障害前にDB Run / Sessionが存在した場合、そのIdentityと履歴は保持する。障害期間のCaptureは既存Session membershipへ追加しない。
- 同一Physical Run内で障害期間に初回ASSIGNEDとなった場合、復旧後に同一RunをDB管理へ遡及変換しない。同一Run内のDB管理再開契約は本版対象外とし、新しいPhysical RunからDB管理を開始する。

### 37.2 NONE AssociationとSession membershipの分離
- Session membershipはMeasurement Mirror初回登録時点で同一Physical Run / ScopeのSessionが存在する場合に限り固定する。membershipは後日変更・遡及追加しない。
- Session生成前に登録されたNONE Measurementは、後に初回ASSIGNEDでSessionが生成されてもSessionへ遡及所属しない。
- Session生成後、DB正常利用可能時に取得・登録されたNONE Measurementは、登録時点で同一Scope Sessionへ所属する。後日のNONE AssociationはInstanceへの関連付け履歴のみを追加し、Session membershipを変更しない。
- NONE Associationは明示操作のみ。Association History Recordの論理Identityは(MeasurementID, AssociationOrdinal)、AssociationOrdinalはMeasurementごとに1から連続増加。Event Identityは(OperationID, EventOrdinal)。NONE_ASSOCIATION_CREATED / NONE_ASSOCIATION_CLOSEDをEvent Registryへ登録し、CreatedはTargetInstanceID / AssignmentSnapshotID・Revision / Actor / UTC / Reason、ClosedはPreviousCreatedEventRef / Actor / ClosedAtUTC / CloseReasonを保持する。ActiveはCreate後未Close、Closedは対応Close Eventありとし、MeasurementごとActive最大1件。Reassignmentは同一Operation内でClose→次Ordinal Createの順に記録し、必要Event集合をSource Commitで一括確定、DB MirrorとMarkerは同一Transactionで更新する。部分Tail・欠落・順序違反・Hash不一致・Commit不明はQUARANTINED、元Eventを修復しない。Assignment-at-Measurement=NONE / Session membership不変、Current Aggregate対象外。
- ANONYMOUS / DB unavailable期間のデータはAssociation対象外。

### 37.3 旧記述の処置
- §30.7、§31、§35.1にある「DB unavailable中のASSIGNED Measurementを復旧後BootstrapでMirror化できる」という記述は、Issue #201と不整合な旧候補として廃止する。
- NONE MeasurementのSession membershipを統括判断待ちとした旧記述は、本節37.2で閉鎖する。
- 本節は論理設計文書の同期であり、DB作成・Bootstrap実行・Restore実行・Migration・実装許可を意味しない。

### 37.4 同一Physical Run内のモード再開境界
- outage中に当該Runの初回ASSIGNEDが発生した場合、DB復旧後に同一Physical Runを遡及DB化しない。
- outage前からDB Run / Sessionが存在する場合はIdentityを保持するが、outage中Captureの後日取込は禁止する。
- outage中の初回ASSIGNED後に同一Run内でDB管理へ移行する手順は現行契約に存在しないため、本版では許可せず、新しいPhysical Runを要求する。

### 37.5 External Evidence StorageとDevice Captureの責務境界
- Main §8.1は、DB側External Evidence StorageがProducerから引き渡された確定byte objectを永続化する段階に限る共通受入条件として位置付ける。
- Device / Capture Owner（Motor / Battery担当）はCapture開始・終端、RawLog framing / Schema / Version、Sample境界、Outcome、Channel分離、機器固有Retention / Loss契約を所有する。DB部門は補完しない。
- External Evidence Storage Authorityは引渡し済みbyteの不変保存、Object ID / Hash / Path / durability検証を担当し、保存成功からCapture正常完了・Measurement COMPLETEを推定しない。
- Run ManagerはStorage証拠を検証してManifest / Journal Source Commitを記録する。
- Capture境界が未契約の場合、受領byteはopaque fragmentとしてのみ保全し、完全RawLog / COMPLETE / Feature Extraction / Aggregate入力を主張しない。

### 37.6 受入ケース（未実行）
| ID | 条件 | 期待結果 |
|---|---|---|
| XDC-001 | DB outage中にASSIGNED Measurementを取得 | 外部正本のみ。DB Mirrorなし |
| XDC-002 | XDC-001後にDB復旧 | 障害期間データのBootstrap / 取込 / Mirror化を拒否 |
| XDC-003 | outage前にDB Run / Sessionあり、outage中にCapture | 既存Identity保持。outage CaptureはSession membershipに追加しない |
| XDC-004 | outage中に同一Physical Runで初回ASSIGNED、後にDB復旧 | 同一Runの遡及DB化を拒否。新Physical RunからDB管理 |
| XDC-005 | Session生成前にNONE MeasurementをDB登録し、後にSession生成 | Session membershipへ遡及追加しない |
| XDC-006 | Session生成後にNONE MeasurementをDB登録 | 登録時点で同一Scope Session membershipを固定 |
| XDC-007 | XDC-006対象を後日Association | Instance関連付け履歴のみ。Session membership / Assignment-at-Measurement不変 |

全ケースは論理受入案であり、実行・PASS未確認。