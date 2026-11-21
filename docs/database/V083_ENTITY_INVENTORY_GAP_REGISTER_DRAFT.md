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

## 6. Canonical Identity Coverage Matrix（2026-11-21）

この表はEntity Inventory 23種とMain draft §5.3のCanonical Field Schemaを対応照合したもの。ここでいう「Schemaあり」はCanonical NameのUUIDv5採用承認を意味せず、Namespace・Field domain・UUIDv5出力も未承認である。

| # | Entity Inventory | §5.3 schema | 現在の判定 | 不足 / 注意 |
|---:|---|---|---|---|
| 1 | Physical Run / Run Manifest | — | 未定義・UUIDv4候補 | PhysicalRunIDはUUIDv4として記載。ManifestはContent Hashと別にIDを持つか未定義。UUIDv5を追加しない |
| 2 | DB Run | DB_RUN | Schemaあり・部分 | PhysicalRunIDのみ。DBRun ID生成規則はNamespace未承認 |
| 3 | RUN_SCOPE | RUN_SCOPE | Schemaあり・部分 | PhysicalRunID + ScopeKey。ScopeKey domain/正規化/長さが未確定 |
| 4 | Assignment Snapshot | — | 未定義 | Snapshot ID / Revision / Scope composite identityのどれを使うか未決定 |
| 5 | Assignment History / Event | — | 未定義 | Operation eventとの同一性、OperationID + Ordinalの適用範囲を未決定 |
| 6 | Session | SESSION | Schemaあり・部分 | PhysicalRunID + ScopeKey。Lifecycle・Run closeとの整合は別途必要 |
| 7 | Measurement Envelope | — | 未定義 | MeasurementIDの発行方式、Envelope Hashとの識別関係を未決定 |
| 8 | Measurement Profile Snapshot | — | 未定義 | Snapshot ID、Profile ID + revision、Content Hashのどれが識別子か未決定 |
| 9 | RawLog Object / RawLog Reference | RAWLOG_REFERENCE | Referenceのみ | Object本文はContent Hash / immutable object identityの区別が未定義。Reference schemaをObjectへ流用しない |
| 10 | Sample Reference | SAMPLE_REFERENCE | Schemaあり・部分 | RawLogReferenceID + SampleLocator。Locator grammarとdomain uniqueness未確定 |
| 11 | Measurement Sample Link | MEASUREMENT_SAMPLE_LINK | Schemaあり・部分 | MeasurementID + SampleReferenceID + Role + Ordinal。Role / Ordinal domain未確定 |
| 12 | Operation Journal / Intent | — | 未定義 | OPERATION_EVENTとの対応は未確定。Intent本体とEventを同一視しない |
| 13 | Receipt Envelope | RECEIPT | Schemaあり・部分 | OperationIDのみ。ReceiptIDの独立発行 / OperationIDからの決定的生成を確定していない |
| 14 | Receipt Event | RECEIPT_EVENT | Schemaあり・部分 | ReceiptID + EventOrdinal。EventType domain / ordinal規則未確定 |
| 15 | DB Operation Marker | — | 未定義 | OperationIDで一意に特定するMirrorか、独立Marker IDを持つか未決定 |
| 16 | Analysis Artifact | — | 未定義 | ArtifactIDの発行方式とPayload Content Hashの区別未定義 |
| 17 | Simulation Artifact | — | 未定義 | Analysis Artifactと共通ID Schemaか、別Entity Typeか未定義 |
| 18 | Artifact Input | ARTIFACT_INPUT | Schemaあり・部分 | ArtifactID + InputType + InputReferenceID + Role + Ordinal。InputType domainとpolymorphic identity未確定 |
| 19 | Aggregate Request | — | 未定義 | RequestIDの発行方式 / Request Fingerprintとの区別未定義 |
| 20 | Aggregate Attempt | — | 未定義 | AttemptID / RequestID + AttemptOrdinalのどちらで識別するか未定義 |
| 21 | Aggregate Result Revision | AGGREGATE_RESULT_REVISION | Schemaあり・部分 | DBRunID + Revision。Scope単位かRun単位か、revision domain未確定 |
| 22 | Aggregate Pointer | — | 派生・identity要否未決定 | 派生参照であり独立UUIDを持たない可能性。Pointer Scope / keyを定義する |
| 23 | Recovery Operation / Integrity Report | — | 未定義 | Recovery Operation IDとIntegrity Report ID / Content Hashの区別未定義 |

### 6.1 Canonical Schema側の孤立・未対応定義

- Main draft §5.3の `OPERATION_EVENT(OperationID, EventOrdinal)` は、Entity Inventory 23種のいずれかへ一意に対応付けられていない。
- Assignment History / EventまたはOperation Journal Eventの候補にはなるが、Intent本体、Assignment Snapshot、Operation Eventを同一Entityと断定しない。
- §5.3には11 schema row（うちTEST_VALUEは別の汎用vector用途）がある。Entity Inventory 23種のうち10種に直接対応するschemaがある。13種はschema未定義、OPERATION_EVENT 1種はinventoryへの対応が未確定。
- 「schema未定義」はUUIDv5を必ず追加すべきという意味ではない。既存UUIDv4、親ID+ordinal、Content Hash、自然キー、派生Pointerのいずれが適切かをAuthorityと更新・保持規則から決める。

### 6.2 次に確定すべき分類ルール

1. **Identity UUID**: Entityそのものの永続ID。UUIDv4かUUIDv5かをEntityごとに決める。
2. **Composite identity**: 親ID + Revision / Ordinal / Scope等で一意になる行。独立UUIDの必要性を証明してから採用する。
3. **Content Hash**: 不変ファイル・Payloadの内容同一性。Entity UUIDの代用と混同しない。
4. **Derived Pointer**: 最新参照・検索状態。正本IDを新規発行せず再構築できるか検討する。
5. **External event identity**: OperationID / EventOrdinal等のEvent ID。Journal IntentとEventの境界を定義する。

この分類を埋めるまでは、23 EntityすべてへのUUIDv5適用・Namespace採用・Canonicalization完成を宣言しない。

## 7. 完成判定のゲート

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


## 8. Entity 23種 属性・制約カバレッジ表（2026-11-21追加）

### 8.1 判定方法

本表は、現行v0.8.3草案と補助資料に**明記されている範囲**を転記・整理したカバレッジ表である。一般的なDB設計慣行から属性・制約を補完していない。

- **明記**: 現行草案に属性・制約・ライフサイクルの記述がある。
- **部分**: 一部の識別子や最低条件だけが記載されている。
- **未定義**: 属性・型・NULL・一意性・参照先等を確定できる記述がない。
- **候補**: Identity分類の検討候補であり、採用決定ではない。
- **不存在**: 今回の検索で見つからなかっただけでは判定しない。作成されなかった可能性も調べるが、根拠が不足する場合は「存在未確認」とする。

PK / FK欄は論理的な参照・一意性の記載状況であり、SQLite DDLや物理キーの確定を意味しない。保持・削除は「通常運用で証拠のUPDATE / DELETEを禁止し、訂正は新Operation / Revisionで追記」という本文の共通最低契約を前提にするが、各Entityへの適用範囲が明記されていない場合は個別未確定とした。

### 8.2 23 Entity 個別カバレッジ

| # | Entity | 草案に明記された属性 / 型 | NULL・UNIQUE・参照 / Cardinalityの根拠 | Identity分類（候補・未承認） | Lifecycle / 保持 | 未確定・不足 |
|---:|---|---|---|---|---|---|
| 1 | Physical Run / Run Manifest | PhysicalRunID: UUIDv4。Manifest内容・Hash | PhysicalRunIDはRun識別子。DB Runとは別ID。Manifest IDの有無は未定義 | Identity UUID候補。Manifest Content Hashは別概念 | 外部正本。Run事実・履歴を保持。削除・ID再発行禁止 | Manifest属性、Manifest ID、Hash対象・版、作成・終端・保持期間、Run単位UNIQUE |
| 2 | DB Run | DBRunID: UUIDv5候補、PhysicalRunID: UUID | Physical Runにつき最大1件。最初のASSIGNED確定時に生成。PhysicalRunIDと別ID | Identity UUID候補（Namespace未承認） | DB Mirror。生成後は全ScopeがNONE/ANONYMOUSでも保持。削除・再生成禁止 | Namespace、Field Domain、全属性、FK実装論理、NULL、DB Run status/close semantics |
| 3 | RUN_SCOPE | PhysicalRunID(UUID), ScopeKey(ASCII string) | PhysicalRunID + ScopeKeyの組を識別候補。Physical Run初期化時に全Scope分の外部正本を作成 | Composite identity候補 | Scope Manifestが外部正本。Run内Scopeの履歴を保持 | ScopeKey許容値・正規化・長さ、Scope一覧のAuthority、FK/Cardinality、Scope追加・廃止 |
| 4 | Assignment Snapshot | Assignment Revision / State / Instance ID / Snapshot Reference / Hashの記述あり | Scope単位の不変Snapshot。ASSIGNEDならInstance ID必須、NONE/ANONYMOUSならNULL。Revision一意性は値域未確定 | Composite identity / Identity UUID / Content Hashの選択未決 | 外部正本の不変Revision。訂正は新Operation / Revision | Snapshot ID、Revision開始・連番・欠番、全属性、Instance FK、Profile参照、Hash範囲 |
| 5 | Assignment History / Event | Operation ID / Ordinal / Actor / Timestamp / before-after / Reasonの一部記述 | Assignment Snapshot / HistoryはScope単位。EventとOperation Eventの同一性は未確定 | External event identity候補（OperationID + Ordinal） | 追記履歴。過去Assignmentを更新しない | Event ID、Ordinal適用範囲、Actor/Reason型、Event Type、Hash Chain、OPERATION_EVENTとの対応 |
| 6 | Session | PhysicalRunID(UUID), ScopeKey(ASCII string)。Lifecycle: NOT_CREATED/OPEN/CLOSED/QUARANTINED | RUN_SCOPEにつき最大1件。初回ASSIGNEDで生成。Outcome集合からLifecycleを導出しない | Identity UUID / Composite identity候補（Canonical SchemaはRunID + ScopeKey） | 一度生成したらAssignment変更後も保持。CLOSEDは検証済み明示Close Operationのみ | SessionIDの独立発行/決定規則、Close Actor/Time/Reason属性、Close参照、FK/Cardinality詳細 |
| 7 | Measurement Envelope | MeasurementID、PhysicalRunID、ScopeKey、Measurement Type、Benchmark Type、Purpose、Started/Ended At、Outcome、Termination Reason、Assignment Snapshot Ref/Revision/State/Instance ID、Profile Snapshot refs、RawLog/Sample refs、Canonicalization Version、Envelope Hash | Assignment Snapshot必須。ASSIGNEDならInstance ID必須、他状態はNULL。測定時帰属を不変保持 | Identity UUID候補。Envelope Hashは別のContent Hash | 外部正本。Measurement OutcomeはCOMPLETE/STOP/ERROR/CANCEL/INCOMPLETE/UNKNOWN。ANONYMOUS後日取込禁止。NONEの扱いはCC-02とSession membership未決に従う | MeasurementID発行、全Field型/NULL/domain、時間整合、Capture終端契約、Profile snapshot全属性、Hash範囲、Session membership |
| 8 | Measurement Profile Snapshot | Profile Snapshot Reference / Hash / Snapshot Status。Model Profile / Instance Profile参照 | Measurement Envelopeから参照。Hash検証後にMirror再生成 | Content Hash / Identity UUID / Composite identity候補 | 不変Snapshot。削除・更新規則は個別未定義 | Snapshot ID、Profile ID/revision、完全属性、欠損時Status、NULL条件、参照Cardinality |
| 9 | RawLog Object / RawLog Reference | Reference側: PhysicalRunID(UUID), ScopeKey(ASCII), LogID(UTF-8)。Object側: 本文とSHA-256の記述 | RAWLOG_REFERENCE SchemaはReferenceのみ。Object本文とReferenceを同一Entityとしない | ObjectはContent Hash / immutable object identity候補。ReferenceはIdentity UUIDまたはComposite候補 | Objectは不変ファイル。Reference Mirrorは本文Hash検証後に再生成。ANONYMOUS後日取込禁止 | Object IDとLogIDの関係、Path/format/size/time/channel、Hash algorithm scope、複数Reference共有、Retention/ownership |
| 10 | Sample Reference | RawLogReferenceID(UUID), SampleLocator(UTF-8 string) | RawLog Referenceに従属する候補。SampleLocatorのgrammar / domain uniqueness未定義 | Composite identity候補（RawLogReferenceID + Locator） | Reference Manifestから再生成候補。個別削除規則なし | Locator grammar、sample index/time/channel/field semantics、NULL/UNIQUE、RawLog typeとの対応 |
| 11 | Measurement Sample Link | MeasurementID(UUID), SampleReferenceID(UUID), Role(UTF-8), Ordinal(Integer) | MeasurementとSample Referenceの関連。Role / Ordinal domain未定義。Ordinal一意性は未確定 | Composite identity候補（Measurement + Sample + Role + Ordinal） | Linkは参照情報。訂正・削除の扱いは個別未定義 | PK/UK、同一Sample複数Role許否、Required/Optional、複合FK、順序規則、Retention |
| 12 | Operation Journal / Intent | OperationID、Ordinal、Intent Payload、Intent Hash、Expected Source Payload Hashes、Expected DB Marker Hash、Target Entity ID等 | Physical Run単位のJournal。Ordinalは消費後再利用禁止。OperationとReceiptは1:1候補 | External event identity候補（OperationID + Ordinal）。Intent HashはContent Hash | 外部正本。追記・不変。Recoveryは新Operation | OperationID発行規則、Journal/Intent/Operation EventのEntity境界、全属性・型、Actor/lock fields、Retention |
| 13 | Receipt Envelope | OperationID(UUID)。Receipt IDはOperationIDから決定的に導出する草案 | Operationにつき最大1 Receipt。Receipt ID/Operation IDの関係は1:1 | Identity UUIDまたはdeterministic identity候補（Namespace/algorithm未確定） | PREPARED→SOURCE_COMMITTED→DB_COMMITTED→VERIFIED等。VERIFIED不変。QUARANTINED解除は新Recovery Operation | ReceiptID導出規則、全Payload属性、Hash自己参照除外、NULL、Operation FK、保持期間 |
| 14 | Receipt Event | ReceiptID(UUID), EventOrdinal(Integer)。Event Type / Timestamp / Payloadの記述 | Receipt内Ordinal一意。Receiptへの従属。Event Type domain未確定 | Composite / External event identity候補（ReceiptID + EventOrdinal） | 追記のみ。State遷移単調。VERIFIED後の追記禁止 | Event ID、Actor、Timestamp、Payload schema、Hash Chain、Ordinal開始値/欠番、Unknown Typeの扱い |
| 15 | DB Operation Marker | OperationID / Ordinal / Intent Hash / Receipt ID / Source Commit Hash / DB Commit Payload Hash / Target Entity Type/ID / Schema Version等 | DB Mirror変更とMarkerは同一Transaction。OperationにつきMarker cardinality候補1 | Composite identity候補（OperationID + Ordinal） | DB内Mirror。Source Commit後にのみ作成。DB Mirror再生成可能 | Marker独立IDの有無、完全Payload、UNIQUE/FK、Hash算出範囲、Transaction durability / isolation |
| 16 | Analysis Artifact | ArtifactID、Algorithm Version、Configuration Version、Input Set Hash、Result Hash、Payload Reference等 | Artifact Inputを通じて入力参照。Artifactは作成後不変。ID/Hashを区別 | Identity UUID候補 + Content Hash | 再解析は新Artifact。旧Artifact保持。DAG循環禁止 | Artifact Envelope全属性、Algorithm/Configの完全識別、Measurement/Profile relation、Status、Retention |
| 17 | Simulation Artifact | ArtifactID候補、Algorithm/Configuration/Input/Resultの共通概念のみ | Analysis Artifactと共通Schemaか別Entityか未確定 | Identity UUID候補 + Content Hash候補 | 不変・再実行で新Artifactとする案はAnalysisと共通適用候補だが、正式適用範囲未確定 | 完全属性、Artifact Type境界、Simulation専用Input/Output、参照制約、Retention |
| 18 | Artifact Input | ArtifactID(UUID), InputType(UTF-8), InputReferenceID(UUID), Role(UTF-8), Ordinal(Integer) | 親Artifactに従属。InputTypeと参照Entity Type一致、参照先存在/Hash一致、DAG非循環。Ordinal uniqueness等未確定 | Composite identity候補（ArtifactID + Type + Ref + Role + Ordinal） | 追記・不変Artifactの構成要素。参照先削除禁止 | InputType許容集合、Reference polymorphism全型、Required、Source Revision、PK/UK、NULL |
| 19 | Aggregate Request | RequestID、RequestOrdinal、Input Set Hash、Assignment Snapshot Set Hash、Requested At、Reason、Algorithm/Configuration Version | DB Run/Scopeとの関係は一部記載。Request Ordinal一意性・開始値は未確定 | Identity UUID候補。Request Fingerprintは別のContent Hash相当 | Requestは不変。再計算ごとに新Request | 全属性、RequestID生成、Scope/Run cardinality、Reason domain、NULL、retry closure reference |
| 20 | Aggregate Attempt | AttemptID、Started/Finished At、Attempt Status、Failure Code/Detail、Worker/Algorithm Version | Requestに従属。再試行ごとに新Attempt ID | Identity UUIDまたはRequestID + AttemptOrdinal候補 | Attemptは不変履歴。失敗AttemptからResult Revisionを生成しない | Attempt Ordinal、Status domain、Failure Code/Detail型、Worker identity、Request/Attempt cardinality、Retry terminal event |
| 21 | Aggregate Result Revision | RevisionID、RequestID、AttemptID、Input Set Hash、Result Hash、Result Payload Reference、Completed At。Canonical fields: DBRunID + Revision | 成功Attemptのみ生成。DBRunID + Revision候補。Revision scope (Run/Scope)未確定 | Composite identity候補（DBRunID + Revision）+ Payload Content Hash | 不変成功結果。失敗要求/AttemptはRevision化しない | Revision domain/開始値、Scope/Run単位、Algorithm provenance、FK、Payload schema、保持期間 |
| 22 | Aggregate Pointer | Latest Requested Request / Latest Successful Revision / Current Valid Revision | 対象Request/Revisionへの参照。Current Validは最新要求とInput Set Hashが一致する成功Revisionのみ | Derived Pointer候補。独立UUID不要の可能性 | 派生・再構築可能とする案。履歴正本と混同しない | Pointer owner scope、NULL条件、並行更新/再構築、stale pointer判定、保存場所 |
| 23 | Recovery Operation / Integrity Report | Recovery Operation ID / Ordinal / Intent / Receipt / Plan / Evidence Hash / Result Artifact等の一部 | 元Receiptを変更せず新Operationで記録。Integrity Reportとの関係は未定義 | Recovery OperationはExternal event identity候補。ReportはContent Hash / Identity UUID候補 | Recovery失敗も証拠を保持。元QUARANTINED ReceiptをVERIFIEDへ変更しない | Report ID、Recovery/ReportのEntity分離、完全属性、親Receipt cardinality、成功/失敗状態、Retention |

### 8.3 カバレッジ結論

- 23/23 Entityについて、現行草案から明記済み属性・制約と未確定項目を区別した。
- **23/23の完全属性表が完成したという意味ではない。** 全属性・型・NULL・UNIQUE・CHECK・FK / 複合FK・Cardinality・Retentionが一式揃うEntityは現時点で確認できない。
- §5.3 Canonical Schemaが直接対応する10 Entityのうち、Canonical fieldsが示すのはIdentity候補の一部であり、全属性表ではない。残る13 EntityはCanonical Schema未定義である。OPERATION_EVENTはInventoryとの対応自体が未解決。
- したがって、Canonical Schemaを持たないEntityにUUIDv5を追加したり、空欄を一般的な設計慣行で埋めたりしない。
- 今後は「明記」「部分」「未定義」「Authority未確認」「個別原文未確認」を属性ごとに追跡し、論理的に必要な判断と物理設計へ持ち越す判断を分離する。

### 8.4 次の検証単位

次回はEntityを一括で完成扱いせず、次の列ごとに証拠を追加する。

1. 属性定義（名称 / 型 / NULL / domain / unit / normalization）
2. Identity / PK / UK（単一・複合・外部ID・Content Hash）
3. FK / Composite FK / Polymorphic ReferenceとCardinality
4. Lifecycle / Revision / Ordinal / State transition
5. Authority / DB Mirror生成条件 / Restore再構築条件
6. Update / Delete / Correction / Retention
7. DB-001〜124 / V082 / Motor / Battery正式契約の根拠

この表は文書調査・論理カバレッジ資料であり、仕様承認、物理設計、DDL、DB生成、Migration、Restore実行、実装を許可しない。


## 9. DB-RV横断の未解決属性・責務マップ（2026-11-21）

Entity Inventory 23種をDB-RVの審査項目へ対応付ける。これは責務の所在を整理するもので、Entityの正式Schemaや新しい要件を確定しない。

| DB-RV | 主なEntity | 未解決の中心項目 |
|---|---|---|
| RV-01 / 02 | Physical Run / Run Manifest / DB Run / RUN_SCOPE / Assignment Snapshot / Assignment History / Session | Run/Manifest identity、Scope domain、Assignment Snapshot identity/revision、Session ID、Close Operation、NONE Association membership |
| RV-03 | Operation Journal / Intent / Receipt Envelope / Receipt Event / DB Operation Marker / Recovery Operation | Plan / Hash DAG、Ordinal authority、Manifest ancestry、Writer / Recovery authority、Marker identity/hash |
| RV-04 | Aggregate Request / Attempt / Result Revision / Pointer | Request fingerprint、Attempt order/retry closure、Result revision scope、Pointer concurrency/rebuild |
| RV-05 | Analysis Artifact / Simulation Artifact / Artifact Input | Artifact identity、Analysis/Simulation boundary、InputType set、polymorphic references、DAG and retention |
| RV-06 | DB Run / RUN_SCOPE / Session / RawLog Reference / Sample Reference / Measurement Sample Link / Receipt / Event / Artifact Input / Aggregate Result Revision | Canonical identity vs composite identity vs Content Hash; 13 Entity schemas absent; OPERATION_EVENT orphan |
| RV-07 | All external-authority entities and DB Mirror entities | source-of-truth authority, mirror rebuild eligibility, Restore verification and retention |
| RV-08 | Measurement Envelope / Profile Snapshot / RawLog Object / Sample Reference / Measurement Sample Link | Measurement identity, assignment snapshot, profile snapshot, capture end, sample locator, RawLog linkage |

### 9.1 完了扱いにできない境界
- 23/23 Entityの存在・責務を一覧化したことと、23/23完全Schemaがあることを区別する。
- Canonical Schema 10 Entity分の対応があることと、全属性表があることを区別する。
- 外部正本 / DB Mirrorの分類があることと、各EntityのRestore可否・再生成証拠が閉じたことを区別する。
- CH1 / CH2独立性はDB論理上のScope / Measurement分離の要求として記録し、Battery固有RawLog契約の不足をDB部門で推測補完しない。


## 10. Entity 23種の一次根拠・Authority・契約所有者マップ（2026-11-21）

### 10.1 判定の意味

本表は、Entityの定義根拠がどの文書に存在するか、外部正本とDB MirrorのどちらがAuthorityか、他部門の正式契約が必要かを分離する。Main draftに記載があることは、Entityの完全Schemaが承認済みであることを意味しない。

- **DB草案根拠**: v0.8.3本文または補助資料に概念・最低条件が記載されている。
- **外部正式契約**: DB部門以外の正本に仕様が明記され、DB側で変更・補完できない。
- **契約未回収**: 対象Entityに必要な完全属性・保存形式・Capture終端等の正式契約が現在の証拠から確認できない。
- **Authority分類**: 現行草案の分類を記録する。物理的保存先、durability、Restore可否の実証完了を意味しない。

### 10.2 Entity別の根拠と責務

| # | Entity | DB草案上の根拠 | Authority / Mirror | 外部正式契約・責任境界 | 判定 |
|---:|---|---|---|---|---|
| 1 | Physical Run / Run Manifest | Main §§1.1, 6, 9, 10。Receipt ContractのManifest / ancestry項 | Run Manifestが外部正本。DB Run生成後の検索Mirrorは任意 | Run開始・終了Event、Manifest完全Schema、Actor、revision/hashは統括Run管理契約が必要 | 部分定義。Run lifecycle契約未完 |
| 2 | DB Run | Main §§1.1, 5.3, 6, 10 | DB Mirror。PhysicalRunIDから再生成候補 | DB Run IDのCanonical Namespace / field domainは統括承認待ち | 部分定義。ID方式未承認 |
| 3 | RUN_SCOPE | Main §§1.2, 5.3, 6, 10 | Scope Manifest / Assignment Snapshotが外部正本。DB Mirrorは再生成可能 | ScopeKeyの正式語彙・許容値・Scope追加規則は未提示 | 部分定義。Scope domain未確定 |
| 4 | Assignment Snapshot | Main §§1.2–1.3, 6。CC-02はIssue #210 | Scope単位の不変外部正本。DBはMirror | Assignment状態とInstanceID NULL条件は明記。Snapshot完全属性・ID/revision/hash契約は未完 | 部分定義。Snapshot schema未完 |
| 5 | Assignment History / Event | Main §1.3, §6。Receipt/Operation資料は別系統 | 外部正本の追記履歴。DB Mirror | Assignment EventとOperation Eventの同一性・ordinal/hash境界は未決定 | 境界未確定。統合を推測しない |
| 6 | Session | Main §§1.2, 1.4, 6, 9, 10。CC-01はIssue #210 | DB Mirror。Scopeごと最大1。LifecycleはRun管理の明示Closeに従う | CC-01でLifecycleとMeasurement Outcome分離、初回ASSIGNED時生成、Close条件を統括決定 | Lifecycle方針は確定。ID・Close payloadは未完 |
| 7 | Measurement Envelope | Main §§6–7, 9–10。Motor #35 / Battery #16 | 外部正本。測定時Assignmentを不変保持し、DB Mirror再生成 | Motor #35はRawLog v2契約を別途要求。Battery #16はE2E検証タスクであり完全DB契約ではない | 共通最低項目のみ。機器別契約未完 |
| 8 | Measurement Profile Snapshot | Main §§6–7, 9 | Envelopeが参照する不変外部Snapshot。Hash検証後Mirror | Model / Instance Profileの完全Field Schema、version、単位、校正は各Profile正式契約が必要 | 部分定義。Profile schema未回収 |
| 9 | RawLog Object / RawLog Reference | Main §§6, 8–9。Canonical RAWLOG_REFERENCE。Motor #35 / #170 | RawLog Object本文が外部正本。Reference Manifest / DB Referenceは参照Mirror | Motor #35はv1保全・非変換、v2を独立形式とし詳細を#170で定義。#170は通信・保存契約タスク。Batteryの同等完全契約は未確認 | Object / Reference分離は明記。完全Schema・durability・retention未完 |
| 10 | Sample Reference | Main §§7, 9。Canonical SAMPLE_REFERENCE。Motor #170 | Reference Manifest由来の参照情報。DB Mirror | SampleLocator grammar、sample/time/channel意味はRawLog v2正式契約が必要。Battery固有定義は未確認 | 部分定義。Locator contract未完 |
| 11 | Measurement Sample Link | Main §§7, 10。Canonical MEASUREMENT_SAMPLE_LINK | DB Mirror上のMeasurement-Sample関係 | Role / Ordinal / Required / uniquenessと機器別Sample cardinalityは未定義 | 部分定義。Link semantics未完 |
| 12 | Operation Journal / Intent | Main §§2.1–2.3, 6, 9。Receipt Contract §§15–21 | Physical Run Journalが外部正本。DB Marker / Journal Mirror | Intent / Operation Event / Assignment EventのEntity境界、writer authority、ordinal消費・回復契約が未完 | 部分定義。DB-RV-03 OPEN |
| 13 | Receipt Envelope | Main §§2.1–2.3, 9。Receipt Recovery Contract | 外部正本。DB Mirrorは再生成 | Receipt ID derivation、Expected Receipt Hash、Hash DAG、full payload schema未承認 | 部分定義。Hash / ID contract OPEN |
| 14 | Receipt Event | Main §§2.1–2.3, 9。Canonical RECEIPT_EVENT | 外部正本Event Log。DB Mirror | Event payloadごとのschema、NULL条件、Actor、EventType registry、partial append recovery未完 | 部分定義。Event contract OPEN |
| 15 | DB Operation Marker | Main §§2.1–2.3, 6, 9。Receipt Recovery Contract | DB内Mirror。DB更新と同一Transactionという論理要求 | Marker identity/hash payload、DB transaction durability / isolationの物理実証は別工程 | 部分定義。Marker hash / durability未完 |
| 16 | Analysis Artifact | Main §§4, 6, 9–10 | Artifact Envelope / Result Payloadが外部正本。DBは参照・検索Mirror | Motor #35はAnalysis入力の一部制約のみ。Artifact完全Schema・algorithm provenanceはDB/解析正式契約が必要 | 不変/DAG方針のみ。完全schema未完 |
| 17 | Simulation Artifact | Main §§4, 6, 9–10 | Artifact Envelope / Result Payloadが外部正本候補。DB Mirror | Analysisと同一Entityか別Entityか、Simulation専用Input/Output契約が未決 | Entity境界未決 |
| 18 | Artifact Input | Main §§4, 5.3, 9–10。Canonical ARTIFACT_INPUT | Artifact Envelopeに従属する外部正本 / DB Mirror | InputType許容集合、polymorphic reference全型、Role / Required / source revision未定義 | DAG方針あり。参照schema未完 |
| 19 | Aggregate Request | Main §3, §§6, 9–10 | Aggregate Envelopeが外部正本。DB Mirror | Request Fingerprint完全項目・scope/run cardinality・retry closeが未完 | 部分定義。DB-RV-04 OPEN |
| 20 | Aggregate Attempt | Main §3, §§6, 9–10 | Aggregate Envelopeが外部正本。DB Mirror | Attempt ordinal、retry terminal event、failure detail / NULL規則未定義 | 部分定義。DB-RV-04 OPEN |
| 21 | Aggregate Result Revision | Main §3, §§5.3, 6, 9–10。Canonical AGGREGATE_RESULT_REVISION | Result Payloadが外部正本。DB Mirror | Revision scope / sequence、Algorithm / Config provenance、Payload schema未完 | 部分定義。Revision domain未完 |
| 22 | Aggregate Pointer | Main §§3.2–3.3, 6, 9 | 派生Pointer。外部正本から再構築 | Owner scope、concurrency、rebuild ordering、stale result protection未定義 | 派生概念のみ。独立Entity/IDは未決 |
| 23 | Recovery Operation / Integrity Report | Main §§2.3, 9。Receipt Recovery Contract §§18–21 | Recovery Operationは新規Operation外部正本候補。ReportのAuthorityは未確定 | Recovery authority、Report identity/schema、approval/retentionが未定義 | 責務境界未完。別Entity要否も未決 |

### 10.3 この照合から確定できること / できないこと

**確定できること**
1. v0.8.3本文には23 Entityの概念・最低責務の根拠があるが、完全属性Schemaが揃ったEntityはない。
2. Main §6は正本 / Mirrorの分類案を提示し、§7はMeasurementの最低Envelope項目、§8はRawLog保存完了の論理要求、§9はRestore二段階検証案を提示する。
3. MotorのRawLog v1/v2境界はIssue #35、v2通信・保存契約の作業範囲はIssue #170にある。Issue #35は未記載事項の担当側復元を禁止する。
4. Battery Issue #16は5A E2E検証タスクであり、Batteryの完全Measurement / RawLog / durability / retention契約ではない。
5. NONE / ANONYMOUSの方針はIssue #210 CC-02に従う。NONE Session membershipのA/B/C選択は未決定のまま。

**この資料だけでは確定できないこと**
- Entityごとの全属性、型、NULL、PK/UK/FK、CHECK、Cardinality、Retention。
- RawLog v2の全Field・ファイル形式・耐久性・保持期間、およびBattery RawLogの同等契約。
- Restore / Bootstrapが各Entityのどの証拠を使ってどこまで再生成できるかの実証。
- UUIDv5適用対象、Namespace、Canonical Name field domain、Content Hashとの一意な境界。
- Issue #210 CC-02のNONE MeasurementとSession membershipの選択。

このマップは証拠所在と契約所有者の整理であり、未回収契約の代替や承認済Schemaではない。


## 11. Aggregate Request / Attempt / Resultの決定論点分解（DB-RV-04 / 2026-11-21）

### 11.1 IdentityとRequest Fingerprintを分離する

現行Main §3.1はRequest IDとInput Set Hash等を保持すると定める。State Matrix §5.1はRequest FingerprintへRequest ID、Scope / DB Run ID、Input Set Hash、Assignment Snapshot Set Hash、Algorithm / Configuration、Measurement / Profile / Policy Revision、Aggregate Definition Versionを含める案を示す。

この2つは同じ概念ではない。
- Request ID: 受理された要求インスタンスの識別子。再試行で変えないか、新Requestで必ず変えるか等の発行規則は別途必要。
- Request Fingerprint: その要求が何を計算するかを識別する値。Request IDを含める場合は同一入力の別Requestも異なるFingerprintになる。
- Input Set Hash: 入力集合の内容同一性を示す値であり、Assignment / Algorithm / Policy / Definition等を含む全要求条件の代用にはならない。

### 11.2 未決定の選択肢（採用案ではない）

| 論点 | 案 | 内容 | 未解決 / リスク |
|---|---|---|---|
| Fingerprint構成 | A | State Matrix §5.1の全項目を固定順序でcanonicalizeしHash化。Request IDを含める | 同じ計算条件で再要求しても別Fingerprint。IDを含める意味とCache/同値性の境界が必要 |
| Fingerprint構成 | B | 計算条件だけをFingerprint化し、Request IDは別管理 | 同一条件の別Requestが同一Fingerprintになり得る。Request identityとsemantic equivalenceを分離できるが、どの項目が計算条件か確定が必要 |
| Fingerprint構成 | C | Input Set Hashのみで判定 | Assignment / Algorithm / Configuration / Policy / Definition差を見逃し得るため、現行Matrix案を満たさない |
| 保存形式 | 1 | Full fingerprint fields + fingerprint hashをRequest Envelopeに保持 | canonical field schema / version / NULL / orderingが必要 |
| 保存形式 | 2 | Hashのみ保存 | 監査・再計算時に何を比較したか復元できず、Hash preimage不在の問題がある |
| Latest Successful順序 | A | Request Ordinalを第一キー、同一Request内はAttempt Ordinalを第二キー | Attempt Ordinalの正式定義・成功複数回の許否が必要 |
| Latest Successful順序 | B | Result Revisionの独立Ordinalを用いる | Revision採番主体・遅延成功・Request順との整合が必要 |
| Retry終端 | A | 明示Retry Closed Eventを追記し、Actor / Time / Reason / Policyを保持 | Event schema、閉鎖権限、閉鎖後Attempt拒否規則が必要 |
| Retry終端 | B | Request状態にRetryClosedAt等を持つ | 不変Requestと状態更新が衝突。別の不変Eventを使わない場合の証拠更新問題 |
| Retry終端 | C | 現時点で失敗AttemptしかないことからFAILED推定 | 将来の再試行を排除できず、明示終端を要求するMatrix §5.3と整合しない |
| Pointer更新 | A | 最新Request / Fingerprint / generationを比較する条件付き更新 | DB transaction / concurrency制御の物理契約が必要 |
| Pointer更新 | B | 全履歴から再構築し、派生Pointerは常に再計算 | 再構築順序・同時更新・計算コスト・read consistencyが必要 |

### 11.3 現時点で確定してよい最低限

- Request / Attempt / Result Revisionは別概念として維持する。
- Request / Attempt / Resultの過去証拠をUPDATE / DELETEで書き換えない。
- 失敗AttemptからResult Revisionを生成しない。
- 遅延した旧Requestの成功結果を、より新しいRequestのCurrent Validへ昇格させない。
- Input Set Hash単独では要求全体の同一性を証明しない。
- Retry終端が証拠で明示されるまではFAILEDを確定しない。
- Pointerは派生値として扱い、履歴正本の代替にしない。

### 11.4 決定待ち

Fingerprintの完全Field Schema / Request IDを含むか、Latest Successfulの順序キー、Attempt Ordinal、Retry Closed Event schema / authority、Pointer更新のconcurrency保証は未承認。Main §3は変更していない。統括判断なしにState Matrix候補を規範へ昇格させない。


## 12. RawLog durability / identity / recoveryの未閉鎖条件（DB-RV-07 / 08）

### 12.1 Main §8で明記されている論理受入条件

Main §8は、RawLog保存完了に対し、temporary write完了、File Handle fsync相当、temporary file read-back SHA-256、最終Path衝突確認、同一Filesystem Atomic Rename、親Directory fsync相当、final Path read-back hash、Journal completion Eventを要求する。失敗・電源断はPENDING_RECOVERYとし、部分ファイルを削除・上書きせず隔離可能に残す。同じRawLog ID / Expected Hashの再試行は冪等、同一IDの異Hash再保存は禁止。

### 12.2 この条件を実行可能な契約にするため未定義の属性

| 論点 | 現在の根拠 | 未定義・決定待ち |
|---|---|---|
| RawLog ID | Main §8のRawLog ID、Motor #35 / #170のlog_id概念 | IDの発行Authority、Scope、Entity UUIDか外部Log IDか、再利用禁止範囲 |
| Expected Hash | Main §8のSHA-256 / Expected Hash | Hashの対象byte範囲、format/headerを含むか、canonical file representation、Hash algorithm version |
| Final Path | Main §8のPath衝突・Atomic Rename | Path grammar、Run/Scope/Channelの包含、case sensitivity、PathからIDを導出するか |
| Temporary File | Main §8の一時ファイル | Temp ID、作成場所、同一Filesystem判定、孤児Tempの識別、再起動時の所有者 |
| Completion Event | Main §8のJournal完了Event | EventType / payload / expected hash / final path / Actor / timestamp / OperationIDとの関係 |
| PENDING_RECOVERY | Main §8の失敗・電源断状態 | どの証拠でpendingと判定するか、誰が回復を開始できるか、再試行・quarantine境界 |
| Duplicate Path / ID | Main §8–9 | 同一ID・同一Hashの別Path、別ID・同一Hashの同一Object、同一Pathの複数Manifest参照の扱い |
| Retention / Loss | Main §§6, 8–9 | RawLog種別ごとの保持期間、複製要件、許容損失、外部保管先、削除承認主体 |

### 12.3 正式契約との照合

- Motor Issue #35はRawLog v1原本の保全・非変換、RawLog v2の独立Schema、保存表現等のIssue #170定義・統括承認を要求する。Issue #35 / #170の現行本文から、Main §8のすべてのfsync / rename / read-back / recovery項目がMotor v2の正式な実装契約として承認済みとは確認できない。
- Battery Issue #16は5A E2E検証であり、Battery RawLogの完全Schema、RawLog ID / Expected Hash、durability / retention / loss toleranceを定義していない。
- したがってMain §8はDB論理案の要求として保持するが、機器別実装が成立している・各OS/filesystemで保証される・Batteryにも同一方式を適用できるとは扱わない。

### 12.4 受入試験の分離

1. **論理契約試験**: ID / Hash / Path collision / same-ID-same-hash retry / same-ID-different-hash reject / completion event linkage / PENDING_RECOVERY分類。
2. **Filesystem実証**: file fsync、directory fsync、rename atomicity、read-after-rename、電源断・process crashの各OS/filesystem組合せ。
3. **機器別契約試験**: Motor RawLog v2とBattery RawLogの各正式Schema、Capture end、保存完了、loss toleranceに対する適合性。
4. **Restore試験**: partial temp、final path only、completion event missing、hash mismatch、duplicate ID/path、manifest reference missingをPhase A/Bで分類し、未検証をVERIFIED扱いしない。

試験条件・OS/filesystem・機器別仕様が未確定のため、上記は受入試験案であり実行済みPASSではない。

## 13. Entity 23種の最終Identity / Storage / 未契約時処置（Main §14）

> Main §14が最終Decision Authority。§1〜§12のOPEN / candidate / gap記録は調査時点の履歴であり、現在の設計選択は本節とMain §14に従う。

| # | Entity | Identity / Storage決定 | 未契約時の固定動作 |
|---:|---|---|---|
| 1 | Physical Run / Run Manifest | Run Manager UUIDv4、外部正本 | Manifest欠落・forkはQUARANTINED |
| 2 | DB Run | UUIDv4、DB Mirror | 初回ASSIGNEDまで生成しない |
| 3 | RUN_SCOPE | (PhysicalRunID, ScopeKey)複合キー | MOTOR / BATTERY_CH1 / BATTERY_CH2以外は拒否 |
| 4 | Assignment Snapshot | UUIDv4 + Scope/Revision unique、不変外部正本 | Snapshot欠落・Hash不一致はAssignment更新拒否 |
| 5 | Assignment History / Event | Scope + EventOrdinal、append-only | 部分TailはScope隔離 |
| 6 | Session | UUIDv4、Scopeごと最大1 | 初回ASSIGNED前は生成しない |
| 7 | Measurement Envelope | UUIDv4、外部正本 + DB Mirror | 機器固有契約のないPayloadはopaque、意味解析不可 |
| 8 | Measurement Profile Snapshot | UUIDv4、不変外部Snapshot | Schema不明時はopaque、解析・Aggregate入力不可 |
| 9 | RawLog Object / Reference | Object UUIDv4 / Reference UUIDv4、別Entity | Hash・durability未検証はPENDING_RECOVERY / QUARANTINED |
| 10 | Sample Reference | UUIDv4、RawLog Referenceに従属 | Locator不明はopaque、時刻/Channel推定禁止 |
| 11 | Measurement Sample Link | MeasurementID + SampleReferenceID + Role + Ordinal | Link cardinality不明時は作成拒否 |
| 12 | Operation Journal / Intent | Operation UUIDv4、Intentは1件、外部正本 | Intent partial tailはRun隔離 |
| 13 | Receipt Envelope | UUIDv4をIntentに固定、不変外部正本 | Intentから再構成不能はQUARANTINED |
| 14 | Receipt Event | ReceiptID + EventOrdinal、append-only | Genesis以外のgap / partial tailは隔離 |
| 15 | DB Operation Marker | OperationID unique、DB内同一Transaction | Marker不一致はQUARANTINED |
| 16 | Analysis Artifact | UUIDv4、共通Artifact Envelope | 未知Payloadはopaque、計算入力不可 |
| 17 | Simulation Artifact | UUIDv4、ArtifactKindで区別 | 未知Payloadはopaque、計算入力不可 |
| 18 | Artifact Input | ArtifactID + Ordinal | 未知InputType / cycle / hash mismatch拒否 |
| 19 | Aggregate Request | UUIDv4 + Owner内RequestOrdinal | Fingerprint完全項目がないRequest拒否 |
| 20 | Aggregate Attempt | UUIDv4 + RequestID/AttemptOrdinal | Retry Closed後は新規Attempt拒否 |
| 21 | Aggregate Result Revision | UUIDv4 + RequestID/ResultOrdinal | 成功Attempt以外はResult生成不可 |
| 22 | Aggregate Pointer | Derived View、独立Identityなし | 検証不能時破棄・再構築 |
| 23 | Recovery Operation / Integrity Report | 別UUIDv4 Entity | Recoveryは元証拠不変。Reportは監査用 |

### 13.1 共通Entity Envelopeの扱い
外部正式契約がないEntityの未知Fieldは創作しない。既知の共通EnvelopeとPayloadReference / PayloadHashのみをMirror化し、完全な外部正本byteを保全する。opaque保全できない場合は受入拒否。未知Payloadを解析・Aggregate・再関連付けに使用しない。

### 13.2 決定状態
Identity、Storage class、Unknown schemaの扱い、削除/更新方針はMain §14で確定。物理DDL・列型・index・trigger・複合FKの実装形は本論理設計の対象外であり、実装Gateで別途確定する。
