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
