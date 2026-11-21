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
- Main draft §1.4.1
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
- Main §1.4.1とSession Lifecycle §§1 / 2 / 8の語彙・条件が完全一致すること。
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
