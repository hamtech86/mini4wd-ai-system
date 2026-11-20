# Mini 4WD AI System — 共通DB論理設計書 v0.8.2
## 統括再審査用ドラフト / GitHub共有版

- 基準日: 2026-11-20
- 対象: Motor / Battery / Machine 共通DB基盤
- 前版: v0.8.1
- 状態: **統括再審査前・未承認**
- この文書は論理設計レビュー用。物理設計・DDL・DB生成・Migration・DB実装・実装PRを許可しない。

> 重要: 本文はv0.8.1の基本構造を維持し、統括差戻し DB-REV-22〜28 を補完するドラフトである。未照合事項を完了扱いしない。GitHub上のIssue #77が担当間連絡・引継ぎ規則、Issue #35がMotorの現行FW/Python/UI/RawLog接続契約の正本であり、本書は共通DB論理設計の審査対象文書である。

---

# 0. 変更統制・承認境界

## 0.1 維持する基本原則

1. Physical RunとDB Runは常に別UUID。
2. Physical Run内のScopeをRUN_SCOPEとして独立管理。
3. SessionはRUN_SCOPEに対して0または1件。
4. MeasurementはRUN_SCOPEに直接所属し、Sessionに依存しない。
5. ANONYMOUS / NONE / ASSIGNEDを区別する。
6. Anonymous測定にSession / DB Runを強制しない。
7. 後日割当でMeasurementの実測内容・測定時点の帰属・Profile Snapshotを変更しない。
8. Battery CH1 / CH2は独立Measurement・独立Benchmark。
9. RawLog・Measurement Envelope・Analysis ArtifactはDB外正本。
10. Aggregateは不変Revisionで管理し、Motor / Battery / Machine固有の解析ロジックを共通DBに固定しない。

## 0.2 禁止範囲

統括最終承認および物理設計承認まで、DDL作成・変更、DB生成、Migration、DB実装コード変更、実装PR作成、旧DB復旧・移行を禁止する。旧DBは復旧対象としない。

---

# 1. 識別モデル

## 1.1 Physical Run

物理測定実行の同一性。測定開始前にUUIDv4を発行し、DBの有無に関係なく保持する。複数Scopeを包含できる。

## 1.2 DB Run

DB管理単位。Physical Runにつき0..1件。Physical Run IDとは異なるUUIDv5。最初のASSIGNED確定時に生成し、全ScopeがANONYMOUS / NONEなら存在しない。

## 1.3 RUN_SCOPE

Physical Run内のScope単位。Battery Scope Keyは `BATTERY:CH1` / `BATTERY:CH2`。ANONYMOUS / NONE / ASSIGNEDのいずれでも生成する。

## 1.4 Session

RUN_SCOPEに対して0..1件。初回ASSIGNED確定時に生成する。ANONYMOUS / NONEでは存在しない。再割当やNONE経由の再割当でもSession IDは変えない。

## 1.5 Measurement

RUN_SCOPEに直接所属する物理測定記録。Sessionの有無に依存しない。Measurement IDはUUIDv4で発行し、DB外Measurement Envelopeに保存する。後日割当でID・実測内容・測定時刻・測定時点Profileを変更しない。

## 1.6 Assignment State

| State | 意味 | Instance ID | Session |
|---|---|---|---|
| ANONYMOUS | 意図的な匿名運用 | NULL | なし |
| NONE | 未割当・未確定 | NULL | なし |
| ASSIGNED | Instanceに割当済み | 必須 | あり |

同一Physical Run内で同じInstanceを複数Scopeへ同時割当することは禁止する。

---

# 2. DB-REV-22 — Measurement StatusとSession Status

## 2.1 分離原則

Measurement Statusは個々の物理測定の状態。Session Statusは同一RUN_SCOPE / Session内のMeasurement集合を集約した管理状態。DB登録状態、Receipt状態、RawLog送信状態はどちらにも混入させない。

## 2.2 Measurement Status

- IN_PROGRESS
- COMPLETED
- CANCELLED
- FAILED
- INTERRUPTED
- UNKNOWN

Termination Reasonとの対応:

| Termination Reason | Measurement Status |
|---|---|
| NORMAL_END | COMPLETED |
| USER_STOP | CANCELLED |
| DEVICE_ERROR / PROTOCOL_ERROR / SAFETY_ABORT | FAILED |
| TIMEOUT / DISCONNECTED / POWER_LOSS / APP_CRASH | INTERRUPTED |
| UNKNOWN | UNKNOWN |

測定開始確定時にMeasurementを作成しIN_PROGRESSとする。開始前のMeasurementは作成しない。

## 2.3 Session Status

Session Statusは導出値。Measurement集合から次の優先規則で決定する。

1. Measurement 0件 → NOT_STARTED
2. IN_PROGRESSが1件以上 → IN_PROGRESS
3. 全件COMPLETED → COMPLETED
4. 全件CANCELLED → CANCELLED
5. 全件FAILED → FAILED
6. 全件INTERRUPTED → INTERRUPTED
7. 全件UNKNOWN → UNKNOWN
8. 上記以外の終端状態混在 → PARTIAL

例:

| Measurement状態 | Session Status |
|---|---|
| COMPLETED / COMPLETED | COMPLETED |
| FAILED / FAILED | FAILED |
| COMPLETED / FAILED | PARTIAL |
| FAILED / INTERRUPTED | PARTIAL |
| CANCELLED / UNKNOWN | PARTIAL |
| COMPLETED / FAILED / IN_PROGRESS | IN_PROGRESS |
| 0件 | NOT_STARTED |

Measurement個別状態と件数内訳は必ず保持する。Session StatusをMeasurementへ書き戻さない。

ANONYMOUS / NONEのScopeではSession Statusを作らずMeasurement Statusだけを保持する。後日ASSIGNEDでSessionを作成した場合、既存MeasurementからSession Statusを導出する。

DB内にSession Statusをキャッシュする場合は、Derivation Version、Input Measurement Set Hash、Derived Atを保持し、入力集合変更時に無効化する。

---

# 3. DB-REV-23 — Operation Ordinal / Journal / Receipt

## 3.1 Operation対象

Assignment変更、Session生成、DB Run生成、Measurement登録、RawLog Reference登録、Artifact登録、Aggregate Revision確定、Seal / Reopen等、Physical Run内の永続状態変更をOperationとして記録する。RawLog個々のサンプル取得はOperationではなくSample Sequence / Timestampで管理する。

## 3.2 採番・排他

- 採番主体はPhysical Run単位のOperation Coordinator。
- Physical Run単位のSingle Writer / 排他ロックで全Scope要求を直列化。
- Operation IDはUUIDv4。
- Operation OrdinalはPhysical Run内で1から単調増加。
- Journal Intentの永続化時点でOrdinalを消費済みとする。
- 消費済みOrdinalの再利用は禁止。
- Journal Intent前に停止した場合は未確定として扱う。
- Intent永続化後に中止した場合もOrdinalは消費済みのまま中止Eventを記録する。
- 欠番は許容するが、再利用しない。

## 3.3 正規処理順

1. Physical Run単位の排他ロック取得。
2. Journal整合性確認。
3. Operation ID発行・次Ordinal決定。
4. Operation Intent作成。
5. Journal追記・永続化。
6. Snapshot / History / Envelope等の変更内容を準備。
7. DB transaction開始。
8. DB変更とOperation Markerを同一transactionでCommit。
9. DB MarkerとJournal Hashを照合。
10. Receipt Eventを記録・永続化。
11. VERIFIEDを記録。
12. 排他ロック解放。

JournalとSQLiteは単一トランザクションではない。Journal先行記録を復旧可能な操作Intentとして扱う。

## 3.4 障害復旧

| 停止位置 | 復旧 |
|---|---|
| Intent永続化前 | Operation未確定 |
| Intent永続化後、DB Commit前 | 同じOperation ID / Ordinalで再実行または明示中止 |
| DB Commit中 | DB MarkerでCommit有無を判定 |
| DB Commit後、Receipt前 | Marker / Hash照合後にReceipt再生成 |
| Receipt後、VERIFIED前 | ReceiptとMarkerを検証して確定 |
| Hash / Marker不一致 | QUARANTINED。推測修復禁止 |

再実行は同じOperation IDで冪等に行う。異なるHashを持つ同一Operation IDは隔離する。

## 3.5 CH1 / CH2重複割当防止

Assignment変更時はPhysical Run全Scopeの現状態を読み、変更後の仮想状態を構成して同一Instance重複がないことを検証する。検証・Journal・DB CommitはPhysical Run単位の直列Operationで行う。Scope単位の並行Commitは禁止。

## 3.6 Event Ordinal / Hash Chain

Operation Event OrdinalはOperation内で1から単調増加し、Operation間では共有しない。Event IDはOperation ID + Event OrdinalからUUIDv5で生成する。

Assignment History Hash ChainはScope単位。Operation Journal Hash ChainはPhysical Run単位。History EventにはPhysical Run Operation Ordinalを含める。

`EventHash[n] = SHA256(CanonicalEvent[n] || PreviousHash[n-1])`

Revision 0 Snapshot HashをScope Historyの初期Hashとする。Canonicalization Versionを各Eventに含める。

---

# 4. DB-REV-24 — Analysis Artifact複数入力

## 4.1 原則

Analysis Artifact本体に単一Input Measurement IDを固定せず、複数入力を独立したArtifact Input Referenceとして保持する。

Artifact本体の属性:

- Artifact ID
- Artifact Type
- Physical Run / Scope参照（該当する場合）
- Algorithm ID / Version
- Configuration Hash
- Input Set Hash
- Result Hash
- Status
- Created At
- Envelope Reference

## 4.2 Artifact Input Reference

各入力に次を保持する。

- Input ID
- Artifact ID
- Input Type
- Input Reference ID
- Input Hash
- Role
- Ordinal
- Required
- Source Revision
- Canonicalization Version

Input TypeはMEASUREMENT / ANALYSIS_ARTIFACT / SIMULATION_ARTIFACT / PROFILE / CONFIGURATION等。入力元参照の型整合性はInput Typeに基づき検証する。多態参照の物理FK方式は物理設計で定義する。

## 4.3 Battery Pair Analysis

CH1 / CH2の独立Benchmark Artifactを入力とするPair Analysis Artifactを許可する。Pair Analysisは個別Benchmarkを置き換えない。CH1 / CH2の値を平均して単一Battery Benchmarkを作ることは禁止。片側の変更で他側の個別Benchmarkが変化してはならない。

複数Measurementを用いる内部抵抗推定、複数Motor Measurementによる性能評価、Machine Simulationも同じ複数入力構造を利用できる。

入力Hash・Algorithm Version・Configuration Hashを固定し、後日入力が変化しても既存Artifactの入力を変更しない。

---

# 5. DB-REV-25 — Aggregate Status / Pointer

## 5.1 対象

Current AssignmentがASSIGNEDでSessionが存在するScopeを対象Sessionとする。対象外ScopeもAssignment State / Revision / Hash / 除外理由とともにAggregate Revisionへ固定する。

## 5.2 Aggregate Status

1. 対象Session 0件 → EMPTY
2. IN_PROGRESSが1件以上 → IN_PROGRESS
3. 全件COMPLETED → COMPLETED
4. 全件CANCELLED → CANCELLED
5. 全件FAILED → FAILED
6. 全件INTERRUPTED → INTERRUPTED
7. 全件UNKNOWN → UNKNOWN
8. その他の終端状態混在 → PARTIAL

FAILED + INTERRUPTED、CANCELLED + UNKNOWN等はPARTIAL。Statusだけで内訳を失わず、各状態件数を保持する。

## 5.3 Revision / Pointer分離

次の4つを独立管理する。

- Latest Requested Revision
- Latest Successful Revision
- Current Valid Revision
- Recalculation State（CLEAN / DIRTY / RUNNING / FAILED）

再計算開始時はLatest Requested Revisionを更新しRUNNING。成功時はLatest Successful / Current Validを新Revisionへ更新しCLEAN。失敗時はLatest Successfulを履歴として維持するが、Current Valid RevisionをNULLにしFAILEDまたはDIRTYとする。古い成功Revisionを最新有効結果として表示・利用してはならない。

入力に影響するAssignment / Session / Measurement / RawLog / Artifactが変わった場合はDIRTYとし、Current ValidをNULLにする。

---

# 6. DB-REV-26 — Assignment Snapshot Revision 0

## 6.1 正本

Assignment Snapshot本体はScope単位の不変ファイルを正本とする。ManifestはPath / Scope Key / Revision / Hash / Format Version等の参照情報だけを持つ。DB内SnapshotはMirror。Assignment Historyは遷移履歴の正本であり、Snapshotと競合する状態正本ではない。

## 6.2 Revision 0

RUN_SCOPE生成時にPhysical Run初期化処理がRevision 0 Snapshotを作成する。初期StateはANONYMOUS / NONE / ASSIGNEDのいずれも許可する。ASSIGNEDの場合Instance ID必須。

Snapshot HashはCanonical Content（Format Version、Physical Run ID、Scope Key、Revision、State、Instance ID、Created At、Canonicalization Version）に対するSHA-256。

## 6.3 History

Revision 1以降はAssignment変更ごとに生成する。Revision nのBefore HashはRevision n-1 Snapshot Hashと一致しなければならない。Revision飛び・欠落・重複・Hash不一致はQUARANTINED。

`EventHash[n] = SHA256(CanonicalEvent[n] || PreviousHash[n-1])`

History EventにはBefore / After State、Instance ID、Revision、Hash、Operation ID、Operation Ordinal、Event ID、Timestamp、Canonicalization Versionを保持する。

---

# 7. DB-REV-27 — Profile Snapshot

## 7.1 測定時点固定

Profile SnapshotはMeasurement単位。測定開始時点のProfile Revision / Hashを固定し、後日割当やProfile更新によって変更しない。

## 7.2 Model Profile

Model Profileが存在する場合はModel ID / Profile Revision / Hash / Snapshot Timestampを記録。存在しない場合はRevision NULL、Snapshot Status=MISSINGとし、推測補完しない。欠落は物理Measurementの存在を否定しない。

## 7.3 Instance Profile

測定開始時Assignmentに従う。

| 開始時Assignment | Instance Profile |
|---|---|
| ANONYMOUS | NULL / NOT_APPLICABLE |
| NONE | NULL / NOT_APPLICABLE |
| ASSIGNED | 当該Instanceの開始時Profile Snapshot |

ASSIGNEDでProfileが存在しない場合はMISSING。NONEから後日ASSIGNEDとなっても過去MeasurementのInstance Profile SnapshotはNULLのまま。後日割当情報はAssignment Historyで管理する。

## 7.4 測定中のProfile変更

Measurement開始時点のProfileを採用。測定中にProfileが更新されてもSnapshotは変えない。終了時Profileが必要なら別観測として保持し、開始時Snapshotの代替にしない。

Snapshot StatusはCOMPLETE / MISSING / NOT_APPLICABLE / UNAVAILABLE / HASH_MISMATCHを区別する。Profile不完全性と物理Measurement Statusは分離し、品質判定はAnalysis側で行う。

---

# 8. DB-REV-28 — 全Anonymous / NONE再構築

## 8.1 正常状態

全ScopeがANONYMOUS / NONEのPhysical Runは正常。次の状態を認める。

- Physical Runあり
- RUN_SCOPEあり
- Snapshot Revision 0あり
- Measurement / Envelopeあり
- RawLogあり
- DB Runなし
- Sessionなし
- DB変更OperationがなければReceiptなし

Receiptがないことだけを理由に隔離しない。

## 8.2 受入条件

全Anonymous / NONE再構築では、Physical Run、Scope、Revision 0、Measurement ID / Envelope、RawLog本文 / Hashが存在し、DB Run / Sessionが存在しないことを確認する。再構築後も同じID・Hash・状態を再現する。

## 8.3 後日ASSIGNED

1. Assignment Operation開始。
2. Instance重複を検証。
3. DB Run未生成なら生成。
4. 対象ScopeのSession未生成なら生成。
5. Snapshot / Historyを更新。
6. 既存Measurement IDを維持してDBへ登録。
7. RawLog本文・測定時Profile Snapshotを変更しない。
8. Aggregateを再計算。

---

# 9. UUID / Canonical Input

## 9.1 ID種別

| Entity | ID |
|---|---|
| Physical Run | UUIDv4 |
| DB Run | UUIDv5 |
| RUN_SCOPE | UUIDv5 |
| Session | UUIDv5 |
| Operation | UUIDv4 |
| Operation Event | UUIDv5 |
| Receipt | UUIDv5 |
| Receipt Event | UUIDv5 |
| Measurement | UUIDv4 / Envelope正本 |
| RawLog Reference | UUIDv5 |
| Sample Reference | UUIDv5 |
| Measurement Sample Link | UUIDv5 |
| Analysis Artifact | UUIDv4 / Envelope正本 |
| Artifact Input | UUIDv5 |
| Aggregate Revision | UUIDv5 |
| Simulation Artifact | UUIDv4 / Envelope正本 |

## 9.2 Project Namespace

提案Namespace UUID:

`8f4c2d91-6a73-4e5b-9c20-31d7a8b5e642`

プロジェクト専用Namespace候補として固定提案する。実装前に既存Repo内で使用有無を検索し、統括承認を得る。承認後は変更禁止。RFCのDNS / URL / OID / X.500 Namespaceとは別の独自Namespace。

## 9.3 Canonical Name

UUIDv5のNameは次のVersioned形式とする。

`mini4wd-id:v1|ENTITY_TYPE|FIELD_1|FIELD_2|...`

- UTF-8
- Unicode NFC
- 固定フィールド順
- 値中の区切り文字は規定エスケープ
- NULLと空文字を区別
- UUIDは小文字ハイフン付き標準形式
- Scope Keyは大文字ASCII
- Revisionは10進整数・先頭ゼロなし
- TimestampはUTC ISO 8601固定形式
- Canonicalization Versionを保持

値エスケープ、パーセント文字の二重エスケープ、Timestamp精度等のバイト単位の完全仕様は実装前にテストベクトルで確定する。

## 9.4 Entity別Name

| ID | Name構成 |
|---|---|
| DB Run | DB_RUN / PhysicalRunID |
| RUN_SCOPE | RUN_SCOPE / PhysicalRunID / ScopeKey |
| Session | SESSION / PhysicalRunID / ScopeKey |
| Operation Event | OP_EVENT / OperationID / EventOrdinal |
| Receipt | RECEIPT / OperationID |
| Receipt Event | RECEIPT_EVENT / ReceiptID / EventOrdinal |
| RawLog Reference | RAWLOG_REF / PhysicalRunID / ScopeKey / LogID |
| Sample Reference | SAMPLE_REF / RawLogReferenceID / SampleLocator |
| Measurement Sample Link | MEAS_SAMPLE_LINK / MeasurementID / SampleReferenceID / Role / Ordinal |
| Artifact Input | ARTIFACT_INPUT / ArtifactID / InputType / InputReferenceID / Role / Ordinal |
| Aggregate Revision | AGGREGATE_REVISION / DBRunID / Revision |

UUIDv5は識別安定性、SHA-256は内容同一性・改ざん検知に使用する。

---

# 10. Measurement Envelope / RawLog / Sample Reference

## 10.1 Measurement Envelope

DB外正本。最低限、Measurement ID、Physical Run ID、Scope Key、Measurement Type、Benchmark Type、Purpose、開始/終了時刻、Measurement Status、Termination Reason、RawLog Reference、Sample Reference、Profile Snapshot Reference、Canonicalization Version、Envelope Hashを保持する。

同一Measurement IDで複数EnvelopeがありHash一致なら重複コピーとして扱える。内容Hashが異なる場合はQUARANTINED。DB再構築時にMeasurement IDを再発行しない。

## 10.2 RawLog保存完了

RawLog保存完了は以下のすべてを満たした時点。

1. 一時ファイル書込み完了。
2. Flush / 永続化要求。
3. Hash計算・再確認。
4. 最終PathへのAtomic Rename。
5. 最終ファイル存在確認。
6. 最終Hash一致。

完了前にDB登録・GitHub送信へ進まない。保存失敗時は一時ファイルを識別可能な状態で保全し、FAILED / PENDING_RECOVERY等で管理する。

## 10.3 Sample Reference

RawLog Reference ID、Record Locator、Sample Sequence、Timestamp、Record Hashを保持。CSVでは行番号だけに依存せずSequence / Timestampを併用。BinaryではByte Offset / Record Lengthを使用可能。RawLog本文不変ならSample Referenceも不変。再整形したデータは別RawLogとする。

---

# 11. Receipt

ReceiptはDB変更Operationの証拠。Anonymous測定やローカル保存だけでは不要。Receipt本体/EventはDB外正本、DB内はMirror。

State:

- PREPARED
- DB_COMMITTED
- VERIFIED
- QUARANTINED

通常遷移はPREPARED → DB_COMMITTED → VERIFIED。Marker / Journal / Receipt Hash不一致、Ordinal競合、Hash Chain不一致、Envelope競合、RawLog Hash不一致等はQUARANTINED。QUARANTINEDからの自動復帰は禁止。

復旧はOperation ID / Ordinal / Journal Intent / DB Marker / Envelope / Snapshot / Hash Chainを検証し、冪等性が証明できる場合のみ新しい復旧Operationで実施する。元証拠は変更しない。

---

# 12. DB Run / Session生成

最初のASSIGNED確定OperationでDB Runを生成。DB Run IDはPhysical Run IDを入力とするUUIDv5。

初回ASSIGNED確定時に対象RUN_SCOPEのSessionを生成。Session IDはPhysical Run ID + Scope KeyからUUIDv5。Instance IDを入力に含めない。ASSIGNED→ASSIGNED、ASSIGNED→NONE→ASSIGNEDでもSession IDを維持する。

---

# 13. 論理ER / Entity制約の骨子

主要Entity:

- PHYSICAL_RUN
- DB_RUN
- RUN_SCOPE
- SESSION
- ASSIGNMENT_SNAPSHOT
- ASSIGNMENT_HISTORY
- INSTANCE
- DEVICE_MODEL
- MODEL_PROFILE_REVISION
- INSTANCE_PROFILE_REVISION
- MEASUREMENT
- MEASUREMENT_PROFILE_SNAPSHOT
- RAWLOG_REFERENCE
- SAMPLE_REFERENCE
- MEASUREMENT_SAMPLE_LINK
- ANALYSIS_ARTIFACT
- ARTIFACT_INPUT
- SIMULATION_ARTIFACT
- OPERATION
- OPERATION_EVENT
- JOURNAL
- RECEIPT
- RECEIPT_EVENT
- AGGREGATE_REVISION
- AGGREGATE_POINTER

主要関係:

- PHYSICAL_RUN 1:N RUN_SCOPE
- PHYSICAL_RUN 0:1 DB_RUN
- RUN_SCOPE 0:1 SESSION
- RUN_SCOPE 0:N MEASUREMENT
- RUN_SCOPE 0:N RAWLOG_REFERENCE
- RAWLOG_REFERENCE 1:N SAMPLE_REFERENCE
- MEASUREMENT N:M SAMPLE_REFERENCE（MEASUREMENT_SAMPLE_LINK経由）
- RUN_SCOPE 0:N ANALYSIS_ARTIFACT
- ANALYSIS_ARTIFACT 1:N ARTIFACT_INPUT
- PHYSICAL_RUN 1:N OPERATION
- OPERATION 1:N OPERATION_EVENT
- OPERATION 0:1 RECEIPT
- RECEIPT 1:N RECEIPT_EVENT
- DB_RUN 1:N AGGREGATE_REVISION
- DB_RUN 0:1 AGGREGATE_POINTER

主要UNIQUE:

- DB_RUN(physical_run_id)
- RUN_SCOPE(physical_run_id, scope_key)
- SESSION(run_scope_id)
- ASSIGNMENT_SNAPSHOT(run_scope_id, revision)
- ASSIGNMENT_HISTORY(run_scope_id, revision)
- OPERATION(physical_run_id, ordinal)
- OPERATION_EVENT(operation_id, event_ordinal)
- RECEIPT(operation_id)
- RECEIPT_EVENT(receipt_id, event_ordinal)
- RAWLOG_REFERENCE(run_scope_id, log_id)
- SAMPLE_REFERENCE(rawlog_reference_id, sample_locator)
- ARTIFACT_INPUT(artifact_id, ordinal)
- AGGREGATE_REVISION(db_run_id, revision)

CHECK要件:

- Assignment StateはANONYMOUS / NONE / ASSIGNED。
- ASSIGNED時Instance ID必須、他状態はNULL。
- Revision >= 0、Ordinal >= 1。
- UUID / SHA-256 / Scope Keyは正規形式。
- Measurement / Session / Receipt / Aggregate Statusは定義済み列挙値のみ。
- Current Valid Revisionは成功済みRevisionのみ参照可能。
- 同一Physical Run内のInstance重複割当は禁止。

DELETEは通常運用で禁止。訂正・取消は新Operation / Historyで表現。複数Scopeにまたがる制約は行単位CHECKだけに依存せず、Physical Run単位Operationで検証する。

> 注意: 本章は論理関係と主要制約の骨子。全列の型・NULL可否・複合FK・多態Artifact Input参照方式・ON DELETE/UPDATE規則の完全な物理DDL契約は未確定であり、物理設計へ進む前に別途確定する。

---

# 14. Backup / Restore / Bootstrap / Path Resolver

## 14.1 再構築順

1. 外部ファイル一覧取得
2. Manifest検証
3. Physical Run / Scope検証
4. Snapshot Revision 0検証
5. Assignment History / Hash Chain検証
6. Operation Journal検証
7. Receipt / Receipt Event検証
8. RawLog本文 / Hash検証
9. Measurement Envelope検証
10. Sample Reference検証
11. Analysis Artifact Envelope検証
12. Profile Snapshot検証
13. DB Run / Session生成条件判定
14. DB初期化
15. 検証済み正本からDB Mirror再生成
16. 外部正本との整合性検証
17. Aggregate Revision / Pointer復元
18. Integrity Check
19. 通常接続許可

正本欠落・Hash不一致・History不整合は推測で修復せず隔離する。

## 14.2 Bootstrap

新規DB生成は明示Bootstrapのみ。通常接続でDB不存在なら暗黙生成せずfail-closed。Bootstrap完了後にschema_version・初期データ・整合性検証を実施してから通常接続を許可。

## 14.3 Path Resolver

明示的絶対Path、Read-only / Read-write分離、Git worktree共通解決、Bootstrapと通常接続の分離を要求する。DB Path不明・不一致時は接続停止。

---

# 15. 部門境界

## 15.1 Motor

Issue #35を現行接続・制御・RawLog契約の正本として尊重する。Scope Key、Measurement Type、Benchmark Type、Purpose、Profile Snapshot、RawLog Reference、Sample Reference、Artifact参照のDB契約照合は残る。Motor正式DB要件書は未受領。推定トルク・RPM・対応車重の計算式は共通DB論理承認条件に含めない。

## 15.2 Battery

CH1 / CH2独立、Anonymous Session非依存、RawLogローカル保全優先、5A非必須、内部抵抗はAnalysis Artifact、後日割当によるMeasurement変更禁止を維持。Pair Analysisは個別Benchmarkと別成果物。Battery最終測定・RawLog契約との正式照合は未完了。

## 15.3 Machine / Simulation

Machine要求性能、Motor実現性能、Battery供給能力を入力可能な拡張性を持たせる。Simulationの具体的入力・計算契約はMachine部門の別設計。

---

# 16. 受入試験

| Test ID | 試験 | 期待結果 |
|---|---|---|
| V082-001 | Measurement 0件のSession | NOT_STARTED |
| V082-002 | 全Measurement COMPLETED | COMPLETED |
| V082-003 | COMPLETED + FAILED | PARTIAL |
| V082-004 | COMPLETED + IN_PROGRESS | IN_PROGRESS |
| V082-005 | 全Measurement FAILED | FAILED |
| V082-006 | Anonymous Measurement COMPLETED | Sessionなしで状態保持 |
| V082-007 | 後日ASSIGNED | 既存MeasurementからSession Status導出 |
| V082-008 | Journal Intent前停止 | Operation未確定 |
| V082-009 | Intent後Commit前停止 | 同じOperationで復旧 |
| V082-010 | Commit後Receipt前停止 | Receipt再生成 |
| V082-011 | Ordinal欠番 | 欠番維持・再利用禁止 |
| V082-012 | CH1 / CH2同一Instance同時割当 | 拒否 |
| V082-013 | Artifact複数Measurement入力 | 全入力Hash保持 |
| V082-014 | CH1 / CH2 Pair Analysis | 個別Benchmark不変 |
| V082-015 | Aggregate FAILED + INTERRUPTED | PARTIAL |
| V082-016 | Aggregate再計算失敗 | Current Valid=NULL |
| V082-017 | Revision 0→1 | Hash Chain一致 |
| V082-018 | Snapshot Hash不一致 | QUARANTINED |
| V082-019 | Model Profile欠落 | MISSING |
| V082-020 | NONE→ASSIGNED | 過去Profile Snapshot不変 |
| V082-021 | 測定中Profile更新 | 開始時Profile維持 |
| V082-022 | 全Scope Anonymous | DB Run / Sessionなし |
| V082-023 | 全Scope NONE | DB Run / Sessionなし |
| V082-024 | Anonymous再構築 | 同一ID / Hash |
| V082-025 | Anonymous→ASSIGNED | DB Run / Session生成 |
| V082-026 | UUIDv5再生成 | 同一Nameで同一UUID |
| V082-027 | RawLog保存途中停止 | DB / GitHub送信なし |
| V082-028 | RawLog Hash不一致 | QUARANTINED |
| V082-029 | Receipt Hash不一致 | QUARANTINED |
| V082-030 | DB消失後再構築 | 外部正本から同一関係を復元 |

Battery固有条件: CH1 / CH2独立Measurement・Benchmark、STARTALLは同時開始のみ、CH間平均禁止、5A到達非必須、内部抵抗推定は複数入力可、Pair Analysisは別成果物、AnonymousはDB Runなしでも成立。

既存DB-001〜124は維持する。個別本文の未取得・未照合分を推測で補わない。V082試験は新規受入試験であり既存試験番号を置換しない。

---

# 17. 未照合・保留事項

| 項目 | 状態 |
|---|---|
| DB-001〜124個別本文 | 一部未取得・未照合 |
| Motor正式DB要件書 | 未受領 |
| Motor Scope Key正式契約 | 未確定 |
| Battery最終測定 / RawLog契約 | 最終照合未完了 |
| Machine Simulation契約 | 別設計待ち |
| UUIDv5 Namespace既存利用確認 | 未実施 |
| UUIDv5完全エスケープ規則・テストベクトル | 未確定 |
| 全Entity属性・型・NULL・CHECK・複合FK | 未完成 |
| Artifact Input多態参照の物理実装方式 | 未確定 |
| DDL・SQLite制約・トリガー | 物理設計段階 |
| Backup / Restore実装試験 | 未実施 |

---

# 18. 改訂履歴・審査依頼

- v0.8.1: RUN_SCOPE / Session / Measurement分離、Anonymous対応。
- v0.8.2: DB-REV-22〜28、Journal、複数入力Artifact、Aggregate Pointer、Snapshot Hash Chain、Profile Snapshot、Anonymous再構築を補完。

統括に以下を審査依頼する。

1. DB-REV-22〜28の定義。
2. Operation Journal先行永続化とOrdinal欠番方針。
3. Scope単位Assignment Hash ChainとPhysical Run単位Journalの併用。
4. Artifact複数入力構造。
5. Aggregate Status / Pointer分離。
6. Revision 0 SnapshotとHash Chain接続。
7. Profile Snapshot測定開始時固定。
8. Anonymous / NONEの再構築受入条件。
9. UUIDv5 Namespace / Canonical Input案。
10. V082-001〜030受入試験。
11. 未照合事項を残した共通論理設計承認の可否。

**提出状態: 統括再審査前。承認済みではない。**
**物理設計移行・DDL・DB生成・Migration・実装は禁止継続。**
