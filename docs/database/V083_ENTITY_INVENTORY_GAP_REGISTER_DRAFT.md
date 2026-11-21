# v0.8.3 Entity Inventory / Constraint Gap Register

- 基準日: 2026-11-21
- 状態: 論理Entity棚卸し・未承認
- 対象: COMMON_DB_LOGICAL_DESIGN_v0.8.3_REMEDIATION_DRAFT.md §§1–10
- 目的: 現行草案に登場する論理Entityを漏れなく棚卸しし、確定済みの最低契約と未定義属性・制約を分離する。
- 本書は物理DDL、DB生成、Migration、実装を許可しない。列名・型・NULL・FKの未確定箇所を推測で確定しない。

## 1. 分類

- **外部正本**: DBの有無にかかわらず証拠として保持する不変ファイル / Event。
- **DB Mirror**: 外部正本から再生成できる検索・集計用表現。
- **派生Pointer**: 不変Entity群から再構築可能な最新参照。正本の代替ではない。
- **補助状態**: Integrity / Quarantine / Recoveryなどの検証状態。通常の測定結果やAssignmentと混同しない。

## 2. Entity Inventory

| Logical Entity | Authority | 現行草案で明示された識別・属性 | 既知の最低制約 | 未確定 / 要定義 |
|---|---|---|---|---|
| Physical Run / Run Manifest | 外部正本 | PhysicalRunID(UUIDv4)、Run Manifest、Scope一覧、Run履歴 | ID不変、DB Runと別ID | Run開始/終了Event、Status、作成Actor、時刻精度、Manifest revision/hash、Run Close根拠 |
| DB Run | DB Mirror | DBRunID(UUIDv5)、PhysicalRunID | Physical Runにつき最大1件、PhysicalRunIDとの分離、削除/再採番禁止 | 属性全体、生成Operation参照、UNIQUE/FK、Canonical Nameの確定 |
| RUN_SCOPE | 外部正本 + DB Mirror | PhysicalRunID、ScopeKey | Physical Run内ScopeKey一意 | ScopeKey語彙/長さ/正規化、初期Snapshot参照、Scope lifecycle |
| Assignment Snapshot | 外部正本 + DB Mirror | Revision、State、InstanceID、Scope参照 | ASSIGNEDならInstanceID必須、NONE/ANONYMOUSならNULL。Snapshot不変 | Snapshot ID、Operation ID、時刻、Actor、前Revision Hash、理由、複合一意制約 |
| Assignment History / Event | 外部正本 + DB Mirror | Assignment遷移履歴、Operationとの関係 | 追記のみ、Current Assignmentは最新Snapshotから導出 | Event/Historyを別Entityにするか、Snapshot内に統合するか、Event ordinal/hash schema |
| Session | DB Mirror（外部正本のScope/Run履歴に基づく） | SessionID(UUID候補・Namespace未承認)、PhysicalRunID、ScopeKey、Lifecycle | Scopeにつき最大1件。初回確定ASSIGNEDで生成し以後保持。LifecycleはNOT_CREATED（未生成状態）/ OPEN / CLOSED / QUARANTINED。Measurement Outcomeから導出しない | 明示Close Operation / 外部正本Close記録・依存参照検証、Close受入条件、作成/閉鎖Operation参照、NONE既存DB管理MeasurementのSession membership規則 |
| Measurement Envelope | 外部正本 + DB Mirror | MeasurementID、PhysicalRunID、ScopeKey、MeasurementType、BenchmarkType、Purpose、StartedAt、EndedAt、Status、TerminationReason、Assignment Snapshot Ref/Revision/State/InstanceID、Profile Snapshot refs、RawLog/Sample refs、Canonicalization Version、Envelope Hash | 測定時Assignment必須・不変。ASSIGNEDならInstanceID必須、他状態ならNULL | 正式Outcome語彙、開始/終了Event、時刻精度/clock source、StatusとIntegrity分離、必須/任意属性全体 |
| Measurement Profile Snapshot | 外部正本 + DB Mirror | Measurementが参照する不変Profile Snapshot、Snapshot Hash | Hash検証後にMirror再生成 | Snapshot種別、ID、Profile schema/version、値/単位/校正、FKと保持規則 |
| RawLog Object / RawLog Reference | RawLog本文は外部正本、ReferenceはDB Mirror | PhysicalRunID、ScopeKey、LogID、RawLog本体/Reference Manifest | 本文Hash一致後に参照Mirror生成。原本変更禁止 | RawLog種別ごとの必須耐久性、schema/version、path/URI、capture state、欠損/retention/owner |
| Sample Reference | 外部正本の参照情報 + DB Mirror | RawLogReferenceID、SampleLocator | RawLog参照とHash整合 | SampleLocator grammar、時刻/offset semantics、複数RawLog跨ぎ、欠損時扱い |
| Measurement Sample Link | DB Mirror | MeasurementID、SampleReferenceID、Role、Ordinal | MeasurementとSampleの型付き参照、Ordinal順 | 複合PK/UK、Role語彙、Required、重複リンク許可、ON DELETE/UPDATE |
| Operation Journal / Intent | 外部正本 + DB Marker Mirror | OperationID、Ordinal、Intent Payload/Hash、Operation Plan | Operation Ordinal単調増加・再利用禁止。Intent追記後不変 | 完全Operation Plan属性、Actor/Intent、source plan、expected marker、Hash canonical schema、部分追記回復 |
| Receipt Envelope | 外部正本 + DB Mirror | ReceiptID、OperationID、Ordinal、Intent Hash、Expected Source Payload Hashes、Expected DB Marker Hash、Canonicalization Version | Operationにつき最大1 Receipt。作成後不変 | Full schema、Expected Receipt Hash、Manifest predecessor/head、Schema Version、Actor/CreatedAt |
| Receipt Event | 外部正本 + DB Mirror | ReceiptID、EventOrdinal、EventType、PreviousEventHash、Payload、EventAt、Actor/RecoveryOperationID、EventHash | Receipt内Ordinal一意・単調増加、Hash Chain、状態遷移制約 | 各Event Payload Schema、NULL条件、Unknown Event拒否、Event retention |
| DB Operation Marker | DB Mirror | OperationID、Ordinal、Intent Hash、ReceiptID、Source Commit Hash、DB Commit Payload Hash | Mirror更新と同一transaction、Operation ID/Ordinal/Hash整合 | Marker PK/UK、Payload Hash self-reference回避、schema version、retention/restore |
| Analysis Artifact | 外部正本 + DB Mirror | Artifact ID、Algorithm/Configuration、Input Set Hash、Result Hash/Payload Ref、Artifact Input DAG | 不変、再解析は新ID、自己参照/循環/未解決入力拒否 | Artifact Envelope完全属性、statusとIntegrity、作成時刻/Actor、入力型/出力型 |
| Simulation Artifact | 外部正本 + DB Mirror | Analysis Artifactと同様のArtifact契約 | 不変、DAG循環禁止 | Analysisとの共通/固有属性、Simulation schema/version、result payload形式 |
| Artifact Input | 外部正本 + DB Mirror | ArtifactID、InputType、InputReferenceID、Role、Ordinal、Required、SourceRevision、InputHash | InputTypeと参照Entity Type一致、DAG非循環 | Polymorphic FK保証方式、Role語彙、NULL条件、重複・順序・複合UK |
| Aggregate Request | 外部正本 + DB Mirror | RequestID、RequestOrdinal、Scope/DBRun、InputSetHash、AssignmentSnapshotSetHash、RequestedAt、Reason、Algorithm/Configuration Version | Request不変、Ordinal単調増加 | Request Fingerprint完全項目、Scope/DBRun cardinality、request reason語彙、受理/取消/Retry Close |
| Aggregate Attempt | 外部正本 + DB Mirror | AttemptID、RequestID、StartedAt、FinishedAt、Status、FailureCode/Detail、Worker、AlgorithmVersion | 試行ごとに新ID、失敗AttemptはResult Revisionを作らない | AttemptOrdinal、再試行可能性、終端判定、時刻/Actor、失敗詳細のNULL規則 |
| Aggregate Result Revision | 外部正本 + DB Mirror | RevisionID、RequestID、AttemptID、InputSetHash、ResultHash、PayloadRef、CompletedAt | 成功Attemptのみ生成、不変 | Revision番号/ordinal開始値、Request Fingerprint参照、Algorithm/Config snapshot、FK/UK |
| Aggregate Pointer | DB Mirror / 派生 | Latest Requested Request、Latest Successful Revision、Current Valid Revision、Recalculation State | 外部正本から再構築可能。Current Validは最新Request完全一致のみ | PointerのScope、更新/再構築順、同時更新競合、古いRequest成功の扱い |
| Recovery Operation / Integrity Report | 外部正本候補（現行草案の記載は限定的） | 元Receipt参照、検証結果、Recovery Operation | 元Receipt不変。解決は新Operation | 独立Entityが必要か、報告Schema、Actor承認、解決参照、retention |

## 3. 既知の論理制約（現行案にあるもの）

1. Physical Run IDとDB Run IDは別UUID。
2. DB RunはPhysical Runにつき最大1件。
3. SessionはRUN_SCOPEにつき最大1件。初回確定ASSIGNEDで生成し、NONE / ANONYMOUS遷移で削除しない。LifecycleはNOT_CREATED（未生成状態）/ OPEN / CLOSED / QUARANTINED。Measurement Outcomeから導出しない。CLOSEDはRun管理側の明示Close Operationと外部正本・依存参照の検証が必要。
4. Assignment Snapshotは不変。ASSIGNED / NONE / ANONYMOUSとInstanceIDのNULL条件を相互排他にする。
5. Measurement EnvelopeはAssignment-at-Measurementを必須保持する。
6. Current Aggregateは現在ASSIGNED、測定時ASSIGNED、測定時Instanceと現在Instanceの一致を要求する。
7. CH1 / CH2を独立Scope / Measurement / Benchmarkとして保持し、平均化しない。Pair Analysisは別Artifact。
8. Operation Ordinal / Event Ordinal / Request Ordinalは単調増加し、再利用しない。
9. ReceiptはOperationにつき最大1件。Receipt EventはReceipt内Ordinal一意。
10. Artifactは不変。再解析は新Artifact ID。Artifact Input DAGの自己参照・循環を禁止。
11. Aggregate Request / Attempt / Resultを分離し、失敗Attemptは成功Result Revisionを作らない。
12. 外部正本からDB Mirrorを再生成できる。DB Mirrorで外部正本の欠落を補完しない。
13. 通常運用のDELETE / UPDATEによる証拠変更を禁止。訂正は新Operation / 新Revisionで表現する。

## 4. まだ確定できない制約

以下は現行草案から確定できないため、実装・DDLへ持ち込まない。
- 各Entityの完全なPK / UK / FK / Composite FK / CHECK。
- NULL / NOT NULLの全属性。
- EntityごとのRevision / Ordinal開始値（0 / 1）と最大値。
- ON DELETE / ON UPDATEの物理設定、および論理的削除禁止の例外。
- 多態参照（Artifact Input等）の全参照型・存在検証方法。
- RawLog ObjectとRawLog Referenceの所有・複数Measurement共有・保持期間。
- Run管理側の明示Close OperationのActor / UI / 取消・受入条件と外部正本契約。
- NONEの後日明示Association対象Measurementが既存Sessionへ所属する条件・監査参照（新規Mirror生成なし）。
- Measurement固有Capture終端契約とOutcome確定根拠。PHYSICAL_RUN_CLOSEDは既存機器EventではなくRun管理側の論理Event。
- Aggregate Pointerの並行更新と再構築順序。
- EntityごとのCanonical Name Field Schema完全版とgolden vectors。
- Namespace候補の既存利用有無・統括承認。
- DB-001〜124個別要求との一対一対応・V082テストとの対応。

## 5. Canonical Nameとの整合ギャップ

現行v0.8.3 §5.3でCanonical fieldsが明記されるEntityは一部に限られる。少なくとも以下の候補EntityのField Schemaが未提示または不完全:
- Physical Run Manifest
- Assignment Snapshot / History
- Measurement Envelope
- Measurement Profile Snapshot
- RawLog Object / Reference Manifest
- Operation Journal / Intent
- DB Operation Marker
- Analysis / Simulation Artifact Envelope
- Aggregate Request / Attempt
- Aggregate Pointer
- Recovery Operation / Integrity Report

また、Canonical Nameで識別するEntityと、Content Hashで識別する不変ファイル / Payloadを区別する必要がある。同じ概念にEntity UUIDとContent Hashのどちらを正本識別子として使うか、混同しない。

## 6. 完成判定のゲート

このInventoryを完成扱いにするには、各Entityについて次を個別に埋める必要がある。
1. 正式名称 / 定義 / 責務。
2. Authority（外部正本 / DB Mirror / 派生Pointer）。
3. 全属性、型、NULL、単位、正規化、値域。
4. PK / UK / FK / Composite FK / CHECK。
5. 親子関係、Cardinality、Polymorphic Referenceの全許容型。
6. Revision / Ordinalの開始値・単調増加・欠番規則。
7. 作成・更新・削除・訂正・保持・Restore規則。
8. Canonical Name Field Schema / Content Hash対象 / Golden Vector。
9. DB-001〜124原文との対応、V082 test coverage、実装証拠。
10. Motor / Battery / RawLog正式契約との整合。

**結論:** 現行草案はEntityの存在と一部の最低制約を定義しているが、全Entityの属性・キー・参照・制約を完成させていない。本Inventoryは未確定箇所を可視化するもので、物理設計・DDL・実装へ移行できる完成設計ではない。
