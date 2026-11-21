# 共通DB論理設計 v0.8.3 差戻し解消案（統括再審査用）

- 基準日: 2026-11-20
- 対象ベース: v0.8.2 / commit `75a3b6d31e7d9e66fe7ef6e34622a05242a6b5ec`
- 状態: **修正案・未承認**
- 本書の位置付け: 統括Issue #209のDB-RV-01〜08に対する規範的な置換案。統括承認前にv0.8.2を承認済みと扱わない。
- 禁止: 物理設計、DDL、DB生成、Migration、DB実装、実装PR、旧DB復旧・移行、main反映。

## 0. 適用・優先順位

本書はv0.8.2の該当節を置き換える論理修正案である。矛盾がある場合、本書の該当条項を優先する。その他のv0.8.2条項は変更しない。物理実装方式・SQLite固有DDL・トリガーは本書で決めない。

用語:
- **外部正本**: DBの有無に依存せず、Physical Runの事実・履歴を復元できる不変ファイル群。
- **DB Mirror**: 外部正本から再生成可能な検索・集計用DB表現。DB Mirrorを唯一の証拠にしない。
- **Assignment-at-Measurement**: Measurement開始確定時に有効だったAssignment SnapshotのRevision / State / Instance ID。
- **Current Assignment**: Scopeの最新Assignment Snapshot。
- **Historical Session**: Scopeが過去に一度でもASSIGNEDとなったことで生成され、その後もIDを保持するSession。

## 1. DB-RV-01 / 02 / 08 — Run・Scope・Session・Assignmentの統一ライフサイクル

### 1.1 Physical Run / DB Run

1. Physical Runは測定実行の外部正本上の単位であり、必ずUUIDv4を持つ。
2. DB RunはPhysical Runにつき最大1件。Physical Run IDとは別のUUIDv4を持つ。
3. DB Runは、そのPhysical Run内で**DBが正常利用可能な状態で最初のASSIGNED Assignment Operationが確定した時点で一度だけ生成**する。DB unavailable時はIssue #201のAnonymous Modeとして扱い、その期間中にDB Runを生成しない。障害期間中に取得したMeasurement / RawLogは外部正本に保全するが、復旧後のBootstrap・再取込・Mirror化の対象にしない。既に存在するDB Runは削除せず履歴として保持する。
4. 一度生成されたDB Runは履歴コンテナとして保持し、全ScopeがNONE / ANONYMOUSへ移行しても削除しない。後日再ASSIGNEDとなっても同一DB Run IDを再利用する。
5. 一度もDB正常利用可能時に有効なASSIGNED Assignment Operationが確定していないPhysical RunにはDB Runを作らない。DB unavailable期間はIssue #201のAnonymous Modeであり、Instance / Manager / DB Assignmentを利用できない。障害期間中のCapture / MeasurementのAssignment-at-MeasurementはANONYMOUS（InstanceID=NULL）とし、オフラインの選択・申告を有効なASSIGNED Assignment Snapshotとして扱わない。初期状態が全Scope NONE / ANONYMOUSであることと、過去にDB管理下でASSIGNED履歴がありDB Runが残存する状態を区別する。
6. DB Runの削除・再生成・ID再採番は禁止。訂正はOperation / Historyとして追加する。

### 1.2 RUN_SCOPE / Session

1. RUN_SCOPEはPhysical Run初期化時に全Scopeについて外部正本として作成する。Scope Keyごとに一意。
2. SessionはRUN_SCOPEにつき最大1件。**Run Managerが、DB正常利用可能時に当該Scopeで初めて有効なASSIGNED Assignment Operationが確定した時点でUUIDv4の論理Session IDを一度だけ発行し、同じ外部Run Manifest Commitへ先行記録する。** Assignment Operation / Manifest Commitが検証済みになるまでSession生成を確定しない。DB Session Mirror Managerは別IDを発行せず同一Session IDのMirrorを作成する。DB unavailable期間に初回ASSIGNEDを成立させることはできず、その期間はAnonymous ModeとしてSessionを新規生成しない。障害開始前から存在する論理Session identity / Lifecycleは外部正本上の履歴として保持するが、障害期間中のCapture / MeasurementをDB Session / Measurement Mirrorへ復旧後に取り込まない。
3. 初期ANONYMOUS / NONEで一度もASSIGNEDになっていないScopeにはSessionを生成しない。
4. ASSIGNED→NONE→ASSIGNED、ASSIGNED→ANONYMOUS→ASSIGNED、ASSIGNED→別InstanceのいずれでもSession IDは変更しない。
5. Sessionの存在は「現在ASSIGNED」を意味しない。現在の割当状態はCurrent Assignment Snapshotのみで判定する。
6. Session membershipは、Measurementを外部Run Manifestへ初回確定記録する時点で同一Physical Run / Scopeの論理Session identityが既に存在する場合に限り、そのSessionへ不変に所属させる。DB Mirrorの有無はmembershipの事実を変えない。Session生成前に登録されたNONE / ANONYMOUS MeasurementはSessionに遡及所属させない。NONE期間のMeasurementは、DB正常利用可能時に取得され、外部正本およびDB管理下のMeasurement記録が既に存在する場合に限り、後日の明示Association Operationを許可する。AssociationはInstanceへの関連付け履歴であり、Session membershipを新規作成・変更しない。測定時AssignmentはNONE・InstanceID NULLのまま保持し、Actor / UTC時刻 / 変更前後 / Reason / OperationIDを監査記録へ残す。既存DB管理Measurementのみを対象とし、新規RawLog取込・Measurement Mirror生成を意味しない。NONE Associationだけを理由にCurrent Aggregateへ算入しない。ANONYMOUS期間およびDB unavailable期間のMeasurement / RawLogは外部正本に保全し、後日DB取込・Mirror化・Instance再紐付けを禁止する。障害開始前にSession identityが存在した場合、その履歴identityは保持できるが、障害期間のMeasurementはANONYMOUSでありDBへ遡及取込しない。

### 1.3 Assignment遷移

| Before | After | Session / DB Run | 新規Measurementの取扱い |
|---|---|---|---|
| 初期NONE | NONE | 生成しない | 外部正本のみ |
| 初期ANONYMOUS | ANONYMOUS | 生成しない | 外部正本のみ |
| 初期NONE/ANONYMOUS | ASSIGNED | DB正常利用可能時に有効なAssignment Operationが確定した場合のみ論理Session identityとDB Run / Session Mirrorを生成。DB unavailable中は初回ASSIGNED・Session生成を認めない | DB正常利用可能時の新規ASSIGNED測定のみDB Mirrorへ登録。障害期間中はAssignment-at-Measurement=ANONYMOUS、外部正本のみ・後日取込禁止 |
| ASSIGNED | ASSIGNED（同一Instance） | 維持 | 測定時Assignment Revisionを記録 |
| ASSIGNED | ASSIGNED（別Instance） | 維持 | 過去測定の帰属は変更しない |
| ASSIGNED | NONE | 維持・非アクティブ | DB正常利用可能時に既存DB管理Measurementとして登録されたもののみ明示Association対象。AssociationはSession membershipを変更しない。障害期間のCaptureはAnonymous Mode扱いで後日取込禁止 |
| ASSIGNED | ANONYMOUS | 維持・制限状態 | ANONYMOUS期間の測定は外部正本のみ。後日取込・Mirror化・再紐付け禁止 |
| NONE/ANONYMOUS（過去ASSIGNEDあり） | ASSIGNED | 既存IDを再利用 | 新規測定のみ現在のAssignmentに従う |

ANONYMOUSは「その期間の測定をInstanceに帰属させない」状態であり、過去にASSIGNEDだった期間の履歴を自動消去・書換えする命令ではない。過去データの消去・匿名化要求はAssignment変更と分離した、別の明示的なプライバシー処理として扱う。通常のAssignment Operationで既存Session・Measurement・Historyを削除しない。

### 1.4 Session Lifecycle / Measurement Outcome / Aggregate対象

1. Session LifecycleとMeasurement Outcomeは完全に分離する。Session LifecycleはNOT_CREATED / OPEN / CLOSED / QUARANTINEDとし、Measurement Outcome（COMPLETE / STOP / ERROR / CANCEL / INCOMPLETE / UNKNOWN）の集合・混在・件数からSession Lifecycleを導出しない。NOT_CREATEDは論理Session identityが存在しない状態である。DB正常利用可能時の初回有効ASSIGNED Assignment Operation確定時に外部Run Manifest上で論理Session identityを生成してOPENとし、同一IDのDB Session Mirrorを生成する。DB unavailable期間は初回ASSIGNED・新規Session生成を認めず、Capture / MeasurementをAnonymous Modeとして外部正本へ保全する。障害開始前から存在する論理Session Lifecycleは履歴として保持するが、障害期間のCaptureをDBへ遡及Mirror化しない。Assignment変更や個々のMeasurement終了では閉じない。CLOSEDはRun管理側の明示的Close Operationが外部正本へ記録され、その記録と依存参照を検証できた場合に限る。Close Operationは論理Run管理イベントであり、STOP ACK・最終Telemetry・アプリ終了・プロセス消失・無通信時間からRun終了を推定しない。Close受入時は対象ScopeのCaptureが終端または明示的に放棄・保留され、未確定MeasurementをCOMPLETEへ読み替えない。終端不明・参照不整合はOPEN維持またはQUARANTINEDとし、推測でCLOSEDにしない。DB unavailable / ANONYMOUS運用ではDB Session Mirrorを生成せず、初回ASSIGNEDで生成されたLogical Session identity / LifecycleおよびRun / Capture情報を外部正本で保持する。
2. **Current Aggregate**の対象は、現在ASSIGNEDであるScopeのうち、Measurement開始時点もASSIGNEDで、かつ測定時Instance IDが現在Instance IDと一致するMeasurementだけとする。
3. NONE / ANONYMOUS期間に開始したMeasurementは、後日ASSIGNEDになってもCurrent Aggregateへ遡及追加しない。NONEの既存DB管理Measurementに対する明示AssociationはInstance関連付け履歴のみであり、Measurement Mirrorの新規生成・Session membership変更・Current Aggregateへの追加を伴わない。
4. 過去に別InstanceへASSIGNEDだったMeasurementは、再割当後のInstanceのCurrent Aggregateへ混入させない。
5. Current AssignmentがNONE / ANONYMOUSのScopeはCurrent Aggregate対象外。除外理由、Current Assignment Revision / State / HashをAggregate Requestに固定する。
6. 過去Assignmentの測定結果を分析する場合は、Current Aggregateとは別の明示的なHistorical Analysis Artifactを生成する。Pair Analysisも入力Measurementの時点帰属を維持し、CH1/CH2を平均化しない。

## 2. DB-RV-03 — Operation / Journal / Receiptの厳密な順序

### 2.1 正規順序（Main §14.4準拠）
1. Run Manager Authority RegistryからPhysical Run単位のWriter Grant / Epochを取得し、Manifest Commit ChainとJournal Tailを検証する。Epochの一意性・旧Epoch fencingを証明できなければ更新を開始しない。
2. Operation ID / Receipt IDをUUIDv4で発行し、Operation Ordinal、Plan Payload、Plan Hash、Expected Source Payload Hashes、Writer Epochを確定する。Receipt IDはIntentに先行固定する。
3. Journal Intentを追記し、file fsync相当とread-back Hash一致を確認する。この時点でOperation Ordinalを消費済みとする。部分書込み・結果不明はRunをQUARANTINEDとし、Ordinalを再利用しない。
4. Intentから再構成可能なReceipt Envelopeを作成し、M4W-JCS-1 / SHA-256でEnvelope Hashを算出する。Envelope本体と親Directoryを永続化し、read-back一致を確認する。
5. Receipt Event PREPAREDをEventOrdinal=1 / PreviousEventHash=NULLで追記し、永続化する。
6. 変更対象の外部正本Revisionと不変Source Commit Recordを追記する。Commit RecordはOperationID / ExpectedPredecessorHash / PayloadHash / CommitHashを持ち、単一Hash Chainを形成する。HeadはChainから導出し、mutable Head Pointer単独をCommit証拠にしない。
7. Source Commit Recordと全依存正本を読み戻して検証し、SOURCE_COMMITTED Eventを追記する。
8. DB transaction内で対象DB MirrorとDB Operation Markerを同時Commitする。MarkerはOperationID / Ordinal / IntentHash / ReceiptID / SourceCommitHash / MirrorChangeHashを保持し、Marker Payload HashはSource Commit後に実Payloadから算出する。Expected DB Marker Hashを事前に固定しない。
9. Commit結果を読み戻し、Marker / Mirror / Intent / Receipt / Source CommitのID・Hashを照合する。Commit結果不明で完全な読戻し証拠を得られなければQUARANTINED。
10. Receipt Event DB_COMMITTEDを追記・永続化する。
11. Journal / Marker / Receipt / 全依存外部正本を再検証する。
12. 全検証成功後にReceipt Event VERIFIEDを追記・永続化する。
13. すべての永続化・照合が成功した後にWriter Grantを解放し、Authority Registryへ解放Eventを記録する。

Journal Intent、Receipt Envelope、Receipt Event、Source Commit Record、DB Markerは別Artifactである。後段Hashを前段Payloadへ逆参照させない。DBは外部正本から再生成可能なMirrorとする。

### 2.2 Receipt State
- PREPARED: Intent / Receipt Envelopeが永続化され、PREPARED Event Chainが検証済み。
- SOURCE_COMMITTED: 外部正本Revisionと不変Source Commit Recordが単一Chainへ永続化され、Expected predecessor / Payload Hash / ancestryが検証済み。
- DB_COMMITTED: DB MirrorとOperation Markerが同一TransactionでCommitされ、Marker / Mirrorが読み戻し一致。
- VERIFIED: Journal / Receipt / Source Commit / DB Marker / 全依存正本の整合性が検証済み。
- ABORTED: PREPARED後、Source Commit不存在を完全検証し、明示Cancel Intentを記録した場合のみ。
- QUARANTINED: 欠落・競合・Hash不一致・部分Tail・Authority不明・DB Commit結果不明等で自動判定不能。元証拠上の終端隔離状態とし、自動解除しない。

正常遷移はPREPARED → SOURCE_COMMITTED → DB_COMMITTED → VERIFIED。PREPAREDからのABORTEDはSource Commit前に限る。SOURCE_COMMITTED以降はABORTED禁止。QUARANTINED元Receiptは編集しない。解決は別Recovery Operationの監査結果として記録する。

### 2.3 クラッシュ復旧表
| 停止点 | 再起動後の根拠 | 固定処置 |
|---|---|---|
| Writer Grant / Intent前 | 永続証拠なし | 未実行。Ordinal未消費 |
| Intent append中・結果不明 | Journal tail / partial bytes | Run QUARANTINED。Ordinal再利用・後続Operation禁止 |
| Intent永続化後・Envelope前 | 完全Intent / Intent Hash | 同一Operation / Receipt IDでEnvelope再構成 |
| Envelope後・PREPARED Event前 | Intent / Envelope Hash | 同一ReceiptのPREPARED Eventのみ補完 |
| PREPARED後・Source Commit前 | Intent / Envelope / Event Chain | 同一Operation再開、またはSource Commit不存在 + Cancel Intent証明時のみABORTED |
| Source Commit後・Event前 | Commit Record / ancestry | 同一ReceiptのSOURCE_COMMITTED Event補完 |
| SOURCE_COMMITTED後・DB transaction前 | Source Commit Chain / Intent | 同一OperationでDB Mirror再開 |
| DB transaction結果不明 | DB Marker / DB integrity / consistent read | Marker完全一致ならCommit済み。MarkerなしでもDB原子性・整合読戻しを証明できなければQUARANTINED |
| DB Commit後・DB_COMMITTED Event前 | Marker / Source Commit | Marker一致を検証してEvent補完 |
| DB_COMMITTED後・VERIFIED前 | 全依存正本 / Marker / Journal | 全検証成功時のみVERIFIED |
| Hash / ID / Ordinal / Epoch競合 | 不一致証拠 | QUARANTINED。推測修復・last-write-wins禁止 |



## 3. DB-RV-04 — Aggregate Request / Attempt / Result Revision（v0.8.3決定）

### 3.1 IdentityとRequest Fingerprint
- Request IDは要求インスタンスのUUIDv4 identity。Request Fingerprintは計算意味条件の同一性Hashであり、Request ID・Request Ordinal・時刻を含めない。
- Fingerprintは次の固定Fieldを含む: DBRunID、ScopeKey、AggregateType、InputSetHash、AssignmentSnapshotSetHash、AlgorithmVersion、ConfigurationVersion、MeasurementSchemaRevision、ProfileSnapshotSetHash、PolicyRevision、AggregateDefinitionVersion、ChannelKey（該当時）。
- 上記Fieldの全値をRequest Envelopeに保存し、M4W-JCS-1 / SHA-256でFingerprintを算出する。Hashのみ保存は禁止。
- RequestOrdinalは(DBRunID, ScopeKey, AggregateType)単位で1から単調増加。欠番可、再利用不可。AttemptOrdinalはRequest内で1から単調増加、欠番可、再利用不可。

### 3.2 Attempt / Retry / Result
- Requestは不変。Attempt Envelopeは試行開始時に一度だけ作成し、Attempt OutcomeはOperation Journal Eventで追記する。Attempt StatusはRUNNING / SUCCEEDED / FAILED / CANCELLED / INDETERMINATEとし、Event Chainから導出する。同一Request内で同時にRUNNINGとなるAttemptは最大1件。Attempt Envelope自体をUPDATEしない。
- Request StateはOPEN / SUCCEEDED / FAILED / CANCELLED / INDETERMINATE。RetryableはOPENの既定状態とし、Retry Closedは少なくとも1件のFAILED Attemptがあり、RUNNING Attemptがない場合のみ明示Request Eventで記録する。Request / Attempt / Request Eventは不変追記記録とし、Request StateはEventから導出する。Retry Closed EventはActor / UTC timestamp / Reason / PolicyVersionを必須とする。
- Retry Closed後の新規Attemptは禁止。RequestがRetry Closedとなり、成功Attemptが一つもない場合だけFAILEDと確定する。成功Attemptが一つ存在した時点でRequestはSUCCEEDED終端となり、追加Attemptを禁止する。Attempt CANCELLEDはRequestを終端させず、明示Retry ClosedまたはRequest CancelledまでOPENを維持する。Attempt結果が証明不能なクラッシュでは、Workerの停止 / fencing proofが得られるまでAggregate OwnerをQUARANTINEDとし、新Request / Attemptを含む更新を停止する。Worker停止を証明できた場合はAttempt / RequestをINDETERMINATE終端とし、同じRequestの再試行を禁止する。再計算が必要なら新Requestを発行する。ATTEMPT_INDETERMINATE EventにはWorkerID / FenceProofHash / Reason / UTC timestampを含める。
- Request Cancelledは認証済みOperatorの明示Eventでのみ成立し、RUNNING Attemptがない場合に限る。ATTEMPT_STARTEDはAttemptID / WorkerID / StartedAtUTC / AlgorithmVersionを、ATTEMPT_SUCCEEDEDはResultHash / CompletedAtUTCを、ATTEMPT_FAILEDはFailureCode / FailureDetail / CompletedAtUTCを、ATTEMPT_CANCELLEDはActorID / Reason / CompletedAtUTCを保持する。RETRY_CLOSED / REQUEST_CANCELLEDはActorID / Reason / PolicyVersion / OccurredAtUTCを保持する。Attempt StateはRUNNINGからSUCCEEDED / FAILED / CANCELLED / INDETERMINATEのいずれか一度だけ遷移し、終端後の更新を禁止する。Result Revisionは成功Attemptのみが生成できる。Request内で成功Resultは最大1件（ResultOrdinal=1）。失敗 / CANCELLED / INDETERMINATE AttemptからResult Revisionを生成しない。
- 同じ計算条件で再要求した場合も新Request ID / RequestOrdinalを発行する。Fingerprintが同じでもRequest identityは別である。

### 3.3 PointerとCurrent Valid
- Latest Requested RequestはAggregate Owner内で最大RequestOrdinalのRequest。
- Latest Successful Revisionは成功ResultのうちRequestOrdinalが最大のもの。Request内の成功Resultは最大1件なのでAttempt順の同順位は発生しない。
- Current Valid RevisionはLatest Requested Requestに属し、そのRequest Fingerprintと完全一致する成功Resultのみ。該当がなければNULL。
- 古いRequestの遅延成功は履歴に保存するが、Current ValidまたはLatest Requestedを後退させない。
- Aggregate Pointerは履歴から再構築可能な派生値。Pointer単独を正本とせず、永続キャッシュを持つ場合も検証不能なら破棄して再計算する。
- CH1 / CH2は独立Aggregate Owner / Input Setとして扱う。平均化・合算は標準Aggregateで禁止。Pair Analysisは明示的な別Artifactとしてのみ許可する。


## 4. DB-RV-05 — Artifact Input DAG / 再解析不変性

1. Analysis Artifact / Simulation Artifactは作成後不変。再解析・Algorithm更新・Configuration更新・入力変更は必ず新Artifact IDを発行する。
2. Artifact InputがANALYSIS_ARTIFACT / SIMULATION_ARTIFACTを参照する場合、入力Artifactは参照先が確定済みでHash検証済みの既存Artifactでなければならない。
3. Artifactは自分自身を入力にできない。新Artifactから既存Artifactへの参照のみ許可し、作成時に依存グラフを走査して循環を拒否する。
4. Input Set HashはInput Type / Reference ID / Input Hash / Role / Ordinal / Required / Source Revisionの順序固定Canonical列から生成する。
5. 同じInput Set / Algorithm / Configurationを再実行しても、実行ごとに新Artifact IDを発行する。内容Hashが同じなら同一内容であることを示すが、旧Artifactを上書き・再利用しない。
6. 参照先Artifactが欠落・Hash不一致・未確定の場合、生成を中止し、依存ArtifactをQUARANTINED扱いにする。入力の推測補完は禁止。
7. 削除は禁止。不要化はLifecycle / Superseded参照等の追記で表現する。


## 5. DB-RV-06 — Identity / Hash Contract（v0.8.3決定）

### 5.1 ID発行方式
- v0.8.3で新規発行する独立Entity IDはUUIDv4とし、暗号学的に安全な乱数源で発行元Authorityが一度だけ生成して外部正本へ先行記録する。乱数品質を確認できない環境では発行を拒否する。
- Physical Run IDおよびLogical Session IDはRun Managerが発行する。DB Run / Assignment Snapshot / Measurement / Profile Snapshot / RawLog Object / RawLog Reference / Sample Reference / Operation / Receipt / Artifact / Aggregate Request / Attempt / Result Revision / Recovery Operation / Integrity Reportは、それぞれの作成AuthorityがUUIDv4を発行する。DB Session MirrorはLogical Session IDを再利用し、別IDを発行しない。
- Receipt IDはOperation IDから導出しない。Receipt作成前にUUIDv4を発行し、Intent内に固定する。再起動時はIntentに記録された同じIDを使用する。
- RUN_SCOPEは独立UUIDを持たず、(PhysicalRunID, ScopeKey)を複合識別子とする。Measurement-Sample LinkとArtifact Inputも親ID + Ordinal等の複合識別子を用いる。Aggregate Pointerは派生値でありIDを持たない。
- UUID文字列表現は小文字・ハイフン付きCanonical形式のみを受け入れる。大文字、波括弧、短縮形、非Canonical表現は拒否する。全Entity ID間で重複を禁止し、参照時はEntity Typeも一致させる。UUID collisionを外部正本へ永続化する前に検出した場合のみ新しいUUIDv4を発行できる。永続化後にcollisionが検出された場合は再採番せずQUARANTINED。
- UUIDv5 / Canonical Binary Name v2 / Namespaceはv0.8.3のID発行方式として採用しない。過去に生成済みのIDは変更・再採番しない。

### 5.2 Structured Hash Profile M4W-JCS-1
- 構造化PayloadのHashはSHA-256を使用し、RFC 8785 JSON Canonicalization Schemeに従うUTF-8バイト列を入力とする。
- Duplicate JSON key、invalid Unicode scalar、NaN / Infinity、浮動小数点数、未知Schema Version、未知Entity Type / Fieldは拒否する。欠落FieldとNULLは区別する。
- 整数はIEEE-754 safe integer範囲（-(2^53-1)〜+(2^53-1)）に限定する。範囲外整数と精度が必要な測定値・小数値は正規化済みDecimal文字列（指数表記・先頭+・不要な先頭/末尾0・負の0を禁止）で表し、JSON numberとして格納しない。
- Timestampはtimezone-aware値のみ受け入れ、UTCへ変換し、YYYY-MM-DDTHH:mm:ss.ffffffZの6桁小数秒で固定する。naive timestamp、microsecond未満の精度、範囲外値、leap second（秒=60）は拒否し、丸めない。
- Unicodeは正規化・case-foldを行わず、入力されたUnicode scalar列をそのまま保持する。JCSの文字列順序規則に従う。見た目が同じ文字列でもcode point列が異なれば異なるHashとなる。Decimal文字列は指数表記・先頭+・不要な先頭ゼロ・不要な小数末尾ゼロを禁止し、負の0表現（-0）は拒否する。
- Byte StringはBase64url（paddingなし）で表現する。NULLはEntity Schemaでnullableと明記されたFieldのみ許可する。
- 自己Hash Field（例: payload_hash / event_hash）はHash入力から除外する。除外対象FieldはEntityごとに固定し、後から暗黙変更しない。SchemaまたはCanonicalization規則変更は新Versionとする。
- RawLog ObjectのContent Hashだけは例外として、変換・正規化前のファイル全バイト（header / metadataを含む）にSHA-256を直接適用する。Structured HashとRawLog Content Hashを混同しない。 M4W-JCS-1の規範例・期待Canonical UTF-8 bytes / SHA-256はCanonicalization Audit §19に記録する。§19は設計ベクトルであり、独立実装の適合PASSではない。

### 5.3 Entity Identityの確定表
| Entity / Concept | Identity |
|---|---|
| Physical Run | Run Manager発行UUIDv4 |
| DB Run | 独立UUIDv4。最初のASSIGNED Operation時に発行 |
| RUN_SCOPE | (PhysicalRunID, ScopeKey) |
| Assignment Snapshot | UUIDv4 + (PhysicalRunID, ScopeKey, Revision) unique |
| Assignment History Event | (PhysicalRunID, ScopeKey, EventOrdinal) |
| Session | 独立UUIDv4 + (PhysicalRunID, ScopeKey) unique |
| Measurement Envelope | 独立UUIDv4 |
| Measurement Profile Snapshot | 独立UUIDv4 |
| RawLog Object | 独立UUIDv4。Device Native Log IDは別Field |
| RawLog Reference | 独立UUIDv4 |
| Sample Reference | 独立UUIDv4 |
| Measurement Sample Link | (MeasurementID, SampleReferenceID, Role, Ordinal) |
| Operation / Intent | Operation UUIDv4。IntentはOperationにつき1件 |
| Operation Journal Event | (OperationID, EventOrdinal) |
| Receipt Envelope | Intentに固定された独立UUIDv4 |
| Receipt Event | (ReceiptID, EventOrdinal) |
| DB Operation Marker | OperationID（Operationにつき最大1件） |
| Analysis / Simulation Artifact | 独立UUIDv4。ArtifactKindで区別 |
| Artifact Input | (ArtifactID, Ordinal) |
| Aggregate Request | 独立UUIDv4 + Aggregate Owner内RequestOrdinal unique |
| Aggregate Attempt | 独立UUIDv4 + (RequestID, AttemptOrdinal) unique |
| Aggregate Result Revision | 独立UUIDv4 + (RequestID, ResultOrdinal) unique |
| Aggregate Pointer | 派生値。独立Identityなし |
| Recovery Operation | 独立UUIDv4 |
| Integrity Report | 独立UUIDv4。Recovery Operationとは別Entity |

### 5.4 互換性・移行
- UUIDv4への決定はv0.8.3で新規発行するIDに適用する。既存IDの型・値・参照は変更しない。
- v0.8.2以前のUUIDv5 / 旧Canonical Nameで生成された可能性のあるIDは、その由来を検証できるまで既存値を保持し、再計算・再採番しない。
- Canonical Binary Name監査の既存byte vectorsは過去の候補方式の検証記録として保管するが、v0.8.3 ID生成の合格条件にはしない。


## 6. DB-RV-07 — 外部正本 / DB Mirrorマトリクス

| Entity / Record | 正本 | DB Mirror | 作成・再生成条件 |
|---|---|---|---|
| Physical Run | Run Manifest | DB Run生成後に任意の検索Mirror | Manifestから復元。ID再発行禁止 |
| DB Run | Run Manifest上のDB Run identity reference | DB正常利用可能時に生成するDB Run Mirror | DB unavailable期間の初回ASSIGNEDでは生成しない。復旧後の同一Physical Runへの遡及生成は禁止 |
| RUN_SCOPE | Scope Manifest / Assignment Snapshot | DB Run生成後、Physical Run内の全ScopeをMirror可能 | 外部Scope一覧から再生成 |
| Session | Run Manifest上のLogical Session identity / Lifecycle | DB正常利用可能時の初回有効ASSIGNED時に同一Session IDのDB Session Mirrorを生成 | Logical Session identityはDB正常利用可能時の初回有効ASSIGNEDでのみ生成。DB unavailable中に初回ASSIGNED・Session生成は行わない。既存identityは外部正本で保持し、障害中のMeasurementは遡及Mirror化しない。Session LifecycleのAuthorityは外部正本 |
| Assignment Snapshot / History | Scope単位の不変ファイル | あり（Mirrorのみ） | Hash Chain検証後に再生成 |
| Measurement | Measurement Envelope | DB正常利用可能時の有効ASSIGNED Measurementを登録。DB unavailable期間のCapture / MeasurementはAssignment-at-Measurement=ANONYMOUS（InstanceID=NULL）として外部正本のみへ保存し、復旧後のBootstrap / DB取込 / Mirror再構築 / Associationを禁止。NONEは既存DB管理Measurementのみ明示Association対象 | Envelopeから再生成。測定時Assignmentを変更しない。NONE AssociationはInstance関連付け履歴のみで、Session membershipを変更しない。Operation ID / Actor / UTC時刻 / 変更前後 / 理由を監査履歴へ記録 |
| Measurement Profile Snapshot | Measurement Envelopeが参照する不変Snapshot | あり（Mirrorのみ） | Snapshot Hash検証後に再生成 |
| RawLog / Sample Reference | RawLog本体 / Reference Manifest | 参照Mirrorのみ | 本文Hash一致を検証して再生成 |
| Analysis / Simulation Artifact | Artifact Envelope / Result Payload | 参照・検索Mirror | DAGと入力Hash検証後に再生成 |
| Operation Journal | Physical Run Journal | Marker / Journal Mirror | Journal正本から再生成 |
| Receipt / Receipt Event | Receipt Envelope / Event Log | あり（Mirrorのみ） | 依存証拠の二段階検証後に再生成 |
| Aggregate Request / Attempt / Result | Aggregate Envelope / Result Payload | Pointer / 検索Mirror | Request/Attempt/ResultのHash検証後に再生成 |

全ScopeがNONE / ANONYMOUSで一度もDB正常利用可能時に有効ASSIGNEDとなっていない場合、Physical Run / RUN_SCOPE / Assignment Snapshot / Measurement Envelope / RawLog / Artifact等は外部正本だけで保全し、DB Run / DB Session Mirror / DB Mirrorを作らない。DB正常利用可能時に初回有効ASSIGNEDとなったScopeのみDB Run / DB Session Mirrorを生成する。DB unavailable期間はIssue #201 Anonymous Modeであり、オフラインのASSIGNED申告・選択は有効なAssignment Operationではない。障害期間のCapture / MeasurementはAssignment-at-Measurement=ANONYMOUS（InstanceID=NULL）として外部正本に保全し、復旧後のBootstrap / DB取込 / Mirror化 / Associationを禁止する。DB unavailable前から存在するDB Run / DB Session Mirrorは削除せず、既存履歴として保持する。NONEの後日Associationは、DB正常利用可能時に既にDB管理Measurementとして登録済みのものに限り、Instance関連付け履歴として明示Operationで許可する。AssociationはSession membershipを変更せず、Assignment-at-Measurement=NONEを保持し、Actor / UTC時刻 / before-after / Reason / OperationIDを監査履歴に残す。Session生成前のNONE Measurementは後からSessionへ遡及所属させない。ANONYMOUS / DB unavailable期間のMeasurement / RawLogは後日取込・Mirror化・Instance再紐付けを禁止する。

外部正本の欠落・Hash不一致・ID競合はQUARANTINED。DB Mirrorから外部正本を逆生成して事実を補完してはならない。DB Mirrorが欠落・破損した場合は外部正本から再生成する。

## 7. DB-RV-08補足 — Measurement Envelope必須の測定時帰属

Measurement Envelopeは最低限、以下を保持する。
- Measurement ID / Physical Run ID / Scope Key
- Measurement Type / Benchmark Type / Purpose
- Started At / Ended At / Measurement Status / Termination Reason
- **Assignment Snapshot Reference / Assignment Revision / Assignment State**
- **Assignment Instance ID（Assignment State=ASSIGNEDの場合必須。それ以外NULL）**
- Model Profile Snapshot Reference / Instance Profile Snapshot Reference / Snapshot Status
- RawLog Reference / Sample Reference
- Canonicalization Version / Envelope Hash

Assignment Snapshot Referenceは測定開始確定時点で有効な不変Snapshotを指す。Assignment-at-MeasurementはMeasurementの属性として固定し、後日Assignment変更で更新しない。

## 8. RawLog耐障害完了条件の補足

### 8.1 適用範囲・責務境界

本節は**DB側のExternal Evidence Storageが、Producerから引き渡された確定byte objectを外部正本として永続化する段階**にのみ適用する。以下の機器固有仕様を定義・代替しない。

- Motor / BatteryのCapture開始・終了条件、Serial protocol、RawLog framing / Field Schema / Version、Sample境界、正常完了・中断・異常の判定。
- CH1 / CH2の取得境界・Channel判定・RawLog生成規則。
- Device固有のRetention、許容損失、再取得可否。

責務Authorityを次のように分離する。
1. **Device / Capture Owner（Motor / Battery担当）**: Capture範囲、RawLog byte列の生成・終端、Schema、Measurement Outcome、Channel分離、機器固有Retention / Loss契約を定義する。DB部門はこれらを補完しない。
2. **External Evidence Storage Authority（DB側論理責務）**: 引渡し済みbyte objectを変換せず保存し、Object ID / Content Hash / Path collision / 永続化検証を管理する。保存成功はCapture正常完了やMeasurement COMPLETEの証明ではない。
3. **Run Manager**: Storage Authorityの永続化証拠を確認し、Manifest / JournalへのSource Commitを記録する。Storage側のread-back成功だけでCapture Outcomeを決めない。

Producerが完全なObject境界を正式に提示しない場合、受領byteはopaque evidence fragmentとしてのみ保全できる。完全なRawLog / Measurementとしての終端、Outcome=COMPLETE、Feature Extraction、Aggregate入力を宣言しない。未知Schema / 未受領Capture契約のbyteは解析・再構成・補完しない。

以下のfsync / read-back / rename条件は、External Evidence Storageが受領済みobjectを永続化するための**共通ストレージ受入条件**であり、Motor / Battery固有のCapture・RawLog契約ではない。
1. 一時ファイルの全内容を書き終え、File Handleに対してfsync相当の永続化要求を行う。
2. 一時ファイルを読み戻してSHA-256を再計算し、期待Hashと一致させる。
3. 最終Pathが未使用であることを確認する。同一Pathが存在しHash一致なら既存正本として参照可能、Hash不一致なら上書きせずQUARANTINED。
4. 同一ファイルシステム内でAtomic Renameする。
5. 親ディレクトリにfsync相当を行い、Renameの永続化を要求する。
6. 最終Pathを再度開いてHashを検証する。
7. 完了EventをJournalへ記録する。失敗・電源断時はPENDING_RECOVERYとし、部分ファイルを削除・上書きせず隔離可能な形で残す。
8. 再試行は同じRawLog ID / Expected Hashで冪等に行う。異なるHashの同一ID再保存は禁止。

OS / filesystemが上記永続化操作を保証しない場合は、その制約をRestore / durability reportへ記録し、完全耐障害を主張しない。

## 9. Restore / Bootstrapの二段階Receipt検証

RestoreはReceiptを最初に最終判定しない。以下の二段階とする。

### Phase A — 構造・索引検査
1. 外部ファイル一覧とManifest取得。Path重複・ID重複・同一Path異Hashを検出。
2. Physical Run / Scope / Snapshot Revision 0 / Assignment History / Journalの構造とHash Chainを検査。
3. Receipt / Receipt Eventの形式、ID、Ordinal、State遷移、自己Hashのみを仮検査する。ここではVERIFIED認定しない。
4. RawLog / Envelope / Sample Reference / Profile Snapshot / Artifact Envelope / Result Payloadをそれぞれ検証。
5. Artifact DAG循環、入力欠落、入力Hash不一致を検証。
6. Aggregate Request / Attempt / Resultの参照・Hash・Pointer整合性を仮検査。

### Phase B — Cross-evidence最終照合
1. Journal IntentとReceipt PREPAREDの一致を検査。
2. DB Markerが存在する場合はOperation ID / Ordinal / Intent Hash / Receipt IDを照合。
3. Envelope / RawLog / Snapshot / Artifact等のPhase A検証結果を使ってReceiptの依存Hashを照合。
4. ReceiptをVERIFIED / ABORTED / QUARANTINEDのいずれかへ確定する。証拠不足はQUARANTINED。
5. DB Run / DB Session Mirror / Measurement Mirrorの生成条件を1章・6章に従って判定。
6. 検証済み外部正本からDB Mirrorを再構築し、外部正本との一致を再検証。
7. Aggregate Pointerを再構築。Current Validは最新RequestのInput Set Hashと一致する成功Revisionがある場合だけ設定。
8. Integrity Checkを実施。成功後にのみ通常接続を許可。

Manifest / RawLog / Envelope / Snapshot / Receiptの欠落、重複、競合は種類別に記録する。DB Mirrorで外部正本の欠落を補わない。Bootstrapは新規DBへの明示管理操作のみであり、通常接続時に暗黙実行しない。

## 10. Entity論理制約の最低契約（物理方式は保留）

1. すべてのIDは型付きUUIDとして扱い、異なるEntity TypeのIDを参照先として受け入れない。
2. Physical Run ID、Scope Key、Revision、Operation Ordinal、Event Ordinal、Request Ordinal、Artifact Input Ordinalには非NULL・正値等の個別制約を定義する。
3. ASSIGNEDならInstance ID必須、NONE / ANONYMOUSならInstance ID NULL。
4. DB RunはPhysical Runにつき最大1件。SessionはRUN_SCOPEにつき最大1件。
5. Sessionの保持は過去のASSIGNED確定履歴で決定し、Current Assignmentから削除判定しない。
6. MeasurementのAssignment-at-Measurementは必須。ASSIGNEDならInstance ID必須、他状態ならNULL。
7. Artifact InputはInput Typeと参照Entity Typeの一致を必須とし、参照先存在・Hash一致・DAG非循環を検証する。
8. ReceiptはOperationにつき最大1件。Receipt EventはReceipt内Ordinal一意。
9. Aggregate Request / Attempt / Result Revisionはそれぞれ不変IDと親参照を持つ。失敗AttemptはResult Revisionを生成しない。
10. 通常運用でDELETE / UPDATEによる証拠変更を禁止。訂正は新Operation / 新Revisionで表現する。
11. ON DELETE / ON UPDATEの物理設定は物理設計に持ち越すが、論理契約として正本・履歴の削除禁止、参照整合性維持、Mirror再生成可能性を必須とする。
12. 複合FK / 多態参照の具体方式は物理設計項目。ただし論理的な型整合性・存在整合性・Hash整合性は本版で必須とする。

## 11. 追加受入試験案（V082-031〜050）

| Test ID | 条件 | 期待結果 |
|---|---|---|
| V082-031 | 初期NONE / ANONYMOUSのみ | DB Run / Sessionなし |
| V082-032 | ASSIGNED後に全Scope NONE | DB Run / Session IDを保持。Current Aggregate対象外 |
| V082-033 | ASSIGNED→ANONYMOUS→ASSIGNED | DB Run / Session ID維持。Anonymous期間の測定はDB Mirrorへ遡及登録しない |
| V082-034 | ASSIGNED Instance A→B | Session ID維持。A時代の測定をBのCurrent Aggregateへ含めない |
| V082-035 | NONE中Measurement後にASSIGNED | Measurement Envelopeの測定時State=NONEを維持しCurrent Aggregateへ含めない |
| V082-036 | Receipt PREPARED後・DB Commit前クラッシュ | 同一Operationで再開またはABORTED。Ordinal再利用なし |
| V082-037 | DB Commit後・Receipt DB_COMMITTED Event前クラッシュ | Marker検証後に同一Receiptを補完 |
| V082-038 | DB MarkerとReceipt Intent Hash不一致 | QUARANTINED |
| V082-039 | Aggregate Request失敗・再試行 | Request不変、Attempt追加、失敗AttemptからResult Revisionを作らない |
| V082-040 | 古いRequestの遅延成功 | Result履歴に保持、Current Validへ昇格させない |
| V082-041 | Artifact自己参照 | 作成拒否 |
| V082-042 | Artifact A→B→A循環 | 作成拒否・既存Artifact不変 |
| V082-043 | 同一入力/Algorithmで再解析 | 新Artifact ID、旧Artifact不変 |
| V082-044 | Input Artifact欠落/Hash不一致 | 新Artifact生成拒否、依存を隔離 |
| V082-045 | Canonical NULLと空文字 | 異なるbyte列 |
| V082-046 | Canonical値内の区切り/%/NUL | 長さ付きpayloadで境界一意 |
| V082-047 | Unicode NFC / NFD | 正規化後同一byte列 |
| V082-048 | Timestamp sub-nanosecond | 入力拒否 |
| V082-049 | RestoreでReceiptがRawLog検証前に存在 | Phase A仮検査のみ。最終VERIFIEDにしない |
| V082-050 | 全Anonymous/NONEの外部正本のみRestore | DB Run / Session / DB MirrorなしでID/Hashを再現 |
| V082-051 | Source Commit後・DB Commit前クラッシュ | ABORTED禁止。同一OperationでDB Mirror再開 |
| V082-052 | DB Commit後・DB_COMMITTED Event前クラッシュ | Marker / Source Hash照合後に同一Receipt Event補完 |
| V082-053 | Source Commit前のOperation中止 | ABORTEDを記録。Ordinalは消費済みのまま再利用禁止 |

V082-001〜030は既存のまま保持する。V082-031〜053は追加案であり、統括承認・試験実装・実行前はPASS扱いしない。


## 12. 未回収証拠・適用対象外・受入ゲート（決定済み）

本節に列挙する項目は、設計上の選択を未決定として残すものではない。v0.8.3では次の運用処置に確定する。

1. DB-001〜124の個別原文・承認・テスト実物が回収できないIDは、Evidence Ledgerの定義どおりREFERENCE_ONLY_NOT_EXECUTABLEとして凍結する。原文・テストがない状態を推測補完しない。DB-125〜154は正式体系対象外、DB-155〜176は撤回番号として再利用しない。
2. V082 crosswalkで根拠がない対応はNO_MAPPINGとする。候補一致・番号の近さ・意味の推測で紐付けない。旧IDを現行受入試験の代替にしない。
3. Motor Issue #35 / #170に正式定義されていないMotor RawLog field / durability / retentionはDB v0.8.3の対象外。Issue #35のv1原本は非変換で保全し、v2は正式契約のFieldだけを受け入れる。
4. Battery Issue #16はE2E検証範囲としてのみ扱う。5A DATAの原本byte保全、共通Measurement Envelope、CH1 / CH2独立Session / Measurementの保存は許可する。RawLog Schema未回収時はopaque payloadとして保存し、意味解析しない。Feature Extraction / Benchmark Resultの再計算、mAh / Wh / voltage dropの数値妥当性判定、スコア、内部抵抗、CH1 / CH2合算は、単位・計算式・Capture End・RawLog Schemaの正式契約が揃うまで実行しない。CH1 / CH2独立性と平均化禁止は維持する。
5. Profile Snapshot / Artifact / Recovery / Integrity Report等で完全なField Schemaがない部分は、v0.8.3で未知Fieldを創作しない。外部正本の不透明なPayload Reference + exact Content Hashとして保全し、DB Mirrorでは既知の共通Envelope項目だけを索引化する。未知Payloadの意味解析・Aggregate入力は禁止する。
6. Run Close Operationの発行AuthorityはRun Managerに限定する。正式なClose証拠がない場合SessionはOPENを維持し、終端矛盾・Hash不一致・Writer競合はQUARANTINEDとする。
7. RawLogの物理耐久性は、対象OS / filesystem / mount条件でSection 8の全工程が試験合格するまでSUPPORTEDとしない。未検証環境ではRawLogをDurable / VERIFIEDとして確定せず、PENDING_RECOVERYまたはQUARANTINEDとする。
8. SQLiteのTransaction / Marker / WAL / read-back / crash recoveryは物理受入試験合格まで保証済みと扱わない。論理規則は§14で固定し、試験未実施の環境ではDB_COMMITTED / VERIFIEDを宣言しない。
9. 全Entityの完全物理Schema・DDL・複合FK・Triggerは本論理版の決定範囲外。§14.1 / §14.3 / §14.4の共通Envelope / identity / relation contractのみを確定し、物理DDLは別承認後に作成する。
10. v0.8.3の設計判断は本書§14およびIssue #210 CC-01 / CC-02で閉じる。実装・受入試験の実行結果、他部門正式契約の回収、統括最終承認は別のGateであり、未実施をPASSとみなさない。


## 13. 自己検証・実証ステータス

| 項目 | 論理設計 | 実装 / 実行証拠 |
|---|---|---|
| DB Run / Session / Assignment | §14で決定済み | 未実施 |
| Measurement Outcome / Close | §14で決定済み | Run Manager / device contract未受領・未実施 |
| Journal / Receipt / DB Marker | §14で決定済み | Filesystem / SQLite crash test未実施 |
| Aggregate / Artifact | §14で決定済み | 実装・受入試験未実施 |
| UUIDv4 / M4W-JCS-1 | §5・§14で決定済み | JCS conformance / payload schema test未実施 |
| RawLog / Restore | §14で決定済み | OS / filesystem別durability / Restore test未実施 |
| Entity 23種 | Identity / Storage / unsupported動作決定済み | 完全Field Schemaの機器別契約は一部未受領 |

「設計決定済み」は実装PASS・受入PASS・統括承認を意味しない。未実施項目は未実施のまま記録する。
- [ ] Measurement EnvelopeにAssignment-at-Measurement必須参照を追加
- [ ] RawLogのFile fsync / Directory fsync / collision / recovery条件を確認
- [ ] Restore二段階Receipt検証とMirror再生成条件を確認
- [ ] DB-001〜124台帳とV082クロスウォークを完成
- [ ] Motor / Battery正式契約照合を完了

**提出状態: 差戻し解消案。統括再審査・承認前。実装移行不可。**


## 14. v0.8.3 Decision Baseline — 未決定事項の最終処置

**Status: DB部門設計判断確定 / 統括最終承認・実装許可とは別**

本節は、従来のOPEN / PROPOSAL / TBD項目を、採用・不採用・適用対象外・証拠不足時の固定動作へ閉じる。Issue #210 CC-01 / CC-02はそのまま優先し、本節はその判断を変更しない。本節と旧節に矛盾がある場合、本節を優先する。

### 14.1 Run / Scope / Session / Assignment
1. Physical RunはRun Manager発行UUIDv4。DB Runは独立UUIDv4で、DB正常利用可能時にPhysical Run内の最初の有効ASSIGNED Assignment Operationが確定した場合に一度だけ生成する。DB RunはPhysical Runにつき最大1件。DB unavailable期間はAnonymous Modeであり、有効なASSIGNED Assignment Operationを発行できない。障害期間中のCapture / MeasurementのAssignment-at-MeasurementはANONYMOUS（InstanceID=NULL）とし、DB Runを生成しない。論理Session identityも障害期間中には新規生成しない。
2. RUN_SCOPEは(PhysicalRunID, ScopeKey)複合識別子。v0.8.3のScopeKey許容値はMOTOR / BATTERY_CH1 / BATTERY_CH2の3値に固定し、未知値は拒否する。Motor / Battery CH1 / Battery CH2を別Scopeとして扱う。CH1 / CH2の同一化・平均化は禁止。
3. SessionはScopeごと最大1件。Run ManagerがDB正常利用可能時の初回有効ASSIGNED Assignment Operation確定時にUUIDv4の論理Session identityを発行し、同じ外部Run Manifest Commitへ記録する。以後Assignment Stateにかかわらず保持する。NONE / ANONYMOUSだけで一度も有効ASSIGNEDにならないScopeには生成しない。DB Session Mirrorは同一IDで生成する。DB unavailable期間に初回ASSIGNED・論理Session identity生成は行わない。障害開始前から存在するidentityは外部正本上で保持するが、障害期間のCapture / Measurementを復旧後にMirror化しない。
4. Session membershipはMeasurementを外部Run Manifestへ初回確定記録した時点で同一Scopeの論理Session identityが存在する場合のみ成立し、後からSessionへ遡及所属させない。DB Run生成済みの別Scopeがあっても、未ASSIGNED ScopeのNONE Measurementを自動Mirror化しない。NONE MeasurementのAssignment-at-MeasurementはNONE・InstanceID NULLのまま不変。DB unavailable期間のMeasurementはAssignment-at-Measurement=ANONYMOUS・InstanceID=NULLとし、障害開始前に既存Session identityがある場合も外部正本のみで保持する。復旧後の取込・Mirror化・Associationは禁止する。 **NONE Session membershipの選択はDB部門案であり、Issue #210 CC-02はこのmembershipを決定していないため、統括の明示確認を要する。提案理由は、Session生成後に同一Scope / Physical Runで登録されたMeasurementを履歴コンテナへ一貫して所属させ、存在しないSessionへの遡及接続だけを禁止すること。代替案（Session存在中のNONEをmembership対象外にする案）は履歴定義を分断するため不採用候補とするが、統括確認までは最終承認扱いにしない。
5. NONE Measurementの後日Associationは、DB正常利用可能時に既にDB管理Measurementとして登録済みのMeasurementに対する認証済みOperatorの明示Operationのみ許可する。ANONYMOUS / DB unavailable期間のMeasurement、外部正本にしか存在しないMeasurementは対象外。AssociationはSession membershipと独立したInstance関連付け履歴であり、Sessionへの追加・移動を行わない。
   - Association Historyは独立UUID Entityではなく、Operation Journalの型付きEventで表す。各Measurement内のAssociationOrdinalは1から連続増加し、再利用しない。Event自体のIdentityは(OperationID, EventOrdinal)、Association History Recordの論理Identityは(MeasurementID, AssociationOrdinal)。
   - Event RegistryにNONE_ASSOCIATION_CREATEDとNONE_ASSOCIATION_CLOSEDを登録する。CREATED PayloadはPhysicalRunID / ScopeKey / MeasurementID / AssignmentSnapshotID・Revision / AssociationOrdinal / TargetInstanceID / ActorID / OccurredAtUTC / Reasonを必須とする。CLOSED PayloadはPhysicalRunID / ScopeKey / MeasurementID / AssignmentSnapshotID・Revision / AssociationOrdinal / PreviousCreatedEventRef / ActorID / ClosedAtUTC / CloseReasonを必須とする。
   - ActiveはCREATED Eventが存在し対応するCLOSED Eventがない状態、Closedは同一AssociationOrdinalのCLOSED Eventが検証済みで存在する状態とする。1 MeasurementにつきActiveは最大1件。Closeは現在ActiveのAssociationOrdinalに限り、CloseReason必須。新規作成はActiveがない場合に限る。
   - Reassignmentは1つのOperation内で、旧AssociationのCLOSED Eventを先に、次AssociationOrdinalのCREATED Eventを後に記録する。Operation PlanはCREATE / REASSIGN / CLOSEのいずれかと必要Event集合を事前固定する。必要Event集合の欠落・順序違反・部分Tail・Hash不一致はOperation / ScopeをQUARANTINEDとし、後続Association更新を停止する。元Eventを補修・削除・再採番しない。
   - Source Commit Recordは必要なEvent集合全体のHashとOperationIDを束ねて一度に確定する。DB Mirror上のActive Association更新とOperation Markerは同一DB Transactionで反映する。Commit結果不明はReceipt / Journal規則に従いQUARANTINEDとする。
   - Current Associationは検証済みAssociation Event Chainから導出し、過去Eventは不変保持する。Assignment-at-MeasurementはNONEのまま変更しない。Session生成前のNONE MeasurementはSessionへ遡及所属させない。Associationだけを理由にCurrent Aggregateへ算入しない。
6. 初回有効ASSIGNED前のNONE期間のMeasurement、ANONYMOUS期間のMeasurement / RawLog、DB unavailable期間のすべてのCapture / Measurementは外部正本のみ。Issue #201によりDB unavailableはAnonymous Modeとして扱うため、障害期間中にASSIGNED状態を新規成立させず、Assignment-at-Measurement=ANONYMOUS・InstanceID=NULLとする。障害期間中は新規DB Run / Session identity / DB Session Mirror / Measurement Mirrorを生成せず、復旧後のBootstrap・取込・Mirror化・Associationも禁止する。障害開始前から存在するDB Run / Session identity / DB Session Mirrorは履歴として保持する。ANONYMOUS / outage期間の将来取込は別設計・統括の明示承認が必要。
7. NONE MeasurementはCurrent Aggregateから常に除外する。Historical Analysisでの利用は、明示的に指定された場合のみ許可し、ArtifactにRETROSPECTIVE_NONEを記録する。ANONYMOUSは分析入力としても現行範囲外。
8. Assignment SnapshotはScope単位の不変Revision。初期SnapshotはRevision=0（StateはNONEまたはANONYMOUS）。以降、実際のState / Instance変更ごとにRevisionを1ずつ増やし、欠番・再利用を禁止する。同じState / Instanceへの重複Assignmentはidempotent no-opとし、新Revisionを作らない。Current Assignmentは最新の検証済みSnapshotから導出する。履歴は追記のみ。
9. DB unavailable期間に当該Physical Runの初回有効ASSIGNED Assignment Operationは成立しない。したがって、そのPhysical RunにはDB Run / Logical Session identityを生成せず、Anonymous Modeとして外部正本のPhysical Run / Capture identityのみを保持する。DB復旧後にDB管理を開始する場合は新しいPhysical Runを開始する。DB unavailable以前にDB Run / Session identity / DB Session Mirrorが既に生成されていた場合は、その既存Identityを削除・再採番せず、障害期間のCapture / MeasurementはAssignment-at-Measurement=ANONYMOUSとして外部正本のみで保持し、後日取込しない。

### 14.2 Measurement Outcome / Session Close
1. Measurement OutcomeはCOMPLETE / STOP / ERROR / CANCEL / INCOMPLETE / UNKNOWN。OutcomeはMeasurement単位でありSession Lifecycleへ伝播しない。
2. COMPLETEは機器固有Capture契約が正常終端と必須Sample完了を明示した場合のみ。STOP / ERROR / CANCELは明示された終端Eventのみ。開始が確認でき、Capture終端または必須Sampleの欠落が確認された場合INCOMPLETE。開始・終端の存在や順序を確定できない、または証拠が矛盾する場合UNKNOWN。時間経過・無通信・アプリ終了・最終値の有無から推定しない。
3. 各機器の詳細Termination Reasonは発行元の文字列・コードを原形保存し、DB側で意味を再解釈しない。正式MappingがないReasonはUNKNOWN扱い。Current Aggregateへ入るのはOutcome=COMPLETEのMeasurementのみ。 **理由:** Current Aggregateは現行Instanceに帰属する完全な測定結果を表すため、STOP / ERROR / CANCEL / INCOMPLETE / UNKNOWNを成功した測定値として混在させない。COMPLETEは機器固有Capture契約が正常終端と必須Sample完了を証明した場合に限り成立し、Motor / Battery契約が未受領または終端証拠が不足するMeasurementはCOMPLETEへ推定せずAggregateから除外する。この規則はSession Lifecycle分離とは別のAggregate受入条件であり、実装・試験PASSを意味しない。
4. Session LifecycleはNOT_CREATED / OPEN / CLOSED / QUARANTINED。CLOSEDはRun Managerが発行するPHYSICAL_RUN_CLOSED Operationが外部正本に永続化され、全ScopeのDispositionがTERMINAL / ABANDONED / HELDのいずれかで、依存証拠が検証済みの場合のみ。未終端をCOMPLETEに読み替えない。
5. Close OperationにはPhysicalRunID、OperationID、ActorID、UTC timestamp、Reason、各ScopeのDisposition、各Capture / Measurementの参照とHash、未解決事項一覧を含める。ActorIDは認証済みOperator principalとし、UI画面・ボタン名はAuthorityではない（Client / UI versionは任意監査Metadata）。HELD / ABANDONEDは理由必須。未解決の矛盾・欠落・Hash不一致・Authority不明はOPEN維持またはQUARANTINED。機器プロトコルの既存Eventを新設・変更しない。

### 14.3 Entity / Schema境界
1. 23 Inventory概念は保持するが、23すべてを独立SQL Tableにする要求は採用しない。Authority・identity・lifecycleに従い、外部正本Object / Append-only Event / DB Mirror / Derived Viewに分類する。
2. OPERATION_EVENTは独立Entityとして採用しない。Operation Journal Eventの型付きEventとして扱い、Identityは(OperationID, EventOrdinal)。TEST_VALUEは試験ベクトル専用で業務Entityではない。
3. Analysis Artifact / Simulation Artifactは共通Artifact Envelopeを使い、ArtifactKindで区別する。Payload Schemaと検証器はKindごとに分離する。Recovery OperationとIntegrity Reportは別Entity。Aggregate PointerはDerived Viewであり独立ID・正本・独立Tableを持たない。
4. RawLog ObjectとRawLog Reference、Measurement EnvelopeとMeasurement Content Hash、Artifact IDとPayload Hash、Operation IntentとOperation Eventは別概念として保持する。
5. 完全なField Schemaが外部契約で定義されていないEntityは、既知の共通Envelope（EntityType、SchemaVersion、EntityID、OwnerReference、CreatedAtUTC、PayloadReference、PayloadHash）と既知の関係だけを扱う。未知のPayloadは不透明データとして保存し、意味解析・Aggregate入力・フィールド補完を禁止する。Payloadの不透明保全も外部正本の保存検証ができない場合は受け入れない。
6. 共通Envelopeの必須条件はEntityType（既知の大文字Registry値）、SchemaVersion（発行元Version文字列）、EntityID（§5.3の独立UUIDまたは指定複合Identity）、CreatedAtUTC（UTC RFC3339固定精度）とする。OwnerReferenceはRoot Entity以外必須で、参照先EntityType + Identityを保持する。外部正本ObjectはPayloadReferenceとPayloadHash（小文字64桁SHA-256 hex）を必須とする。DB Mirrorだけの派生値はPayloadReferenceを持たない場合があるが、外部正本の代替にはならない。
6. 全Entityの独立Identityは§5.3に従う。関係Entityは指定複合キーを使用する。全IDはGlobal unique、型付き参照を必須とする。
7. DELETE / UPDATEによる正本・履歴の書換えは禁止。FKの論理動作はRESTRICT。CASCADE DELETE / CASCADE UPDATEは禁止。訂正・再関連付け・再解析は新Operation / Event / Revisionで表現する。

### 14.4 Operation / Intent / Receipt / Event
1. Operation IDとReceipt IDは別々のUUIDv4。Receipt IDはIntent永続化前に発行し、Intentに固定する。OperationにつきReceiptは最大1件。
2. Operation Plan / Intent / Receipt Envelope / Receipt Event / Source Commit Record / DB Markerは別Artifact。IntentはReceipt Envelope再構成に必要な全immutable input、Receipt ID、Plan Hash、Operation Ordinal、Writer Epochを保持する。
3. Hash依存はPlan Payload → Plan Hash → Intent Payload → Intent Hash → Receipt Envelope Payload → Envelope Hashの順に確定する。PREPARED EventはEnvelope Hash確定後、SOURCE_COMMITTED EventはSource Commit Record / Hash確定後、DB_COMMITTED EventはDB Marker Payload / Hash確定後にそれぞれ追記し、VERIFIED Eventは全依存検証後に追記する。後段Hashを前段Payloadへ戻して含めない。Expected Receipt Hashは廃止。PREPARED時点で将来のSource Commit / DB Marker Hashを予測・固定しない。
4. Structured HashはM4W-JCS-1 / SHA-256。自己Hash Fieldは除外。Event HashはEvent Payload + Previous Event Hashを対象としEventHash自身を除外する。最初のEventはOrdinal=1、PreviousEventHash=NULL。以降は連続Ordinal・直前EventHash必須。
5. Operation OrdinalはPhysicalRun単位で1から単調増加、欠番可、再利用不可。完全Intentの永続化（file fsync相当 + read-back hash一致）が確認できた時点で消費。書込み結果不明・partial tailはINDETERMINATEとしてRunをQUARANTINED、Ordinal再利用・後続Operationを禁止。
6. Receipt Event OrdinalはReceipt単位で1から連続増加、欠番不可、再利用不可。Partial / malformed tail、Hash不一致、Writer競合時はReceiptをQUARANTINEDにし、後続Event追記・tail切捨て・再採番を禁止。
7. PREPAREDはIntentとEnvelopeが完全永続化された後にのみ記録。中止はPREPARED後、Source Commit不存在を検証し、明示Cancel Intentがある場合のみABORTED。Source Commit後はABORTED禁止。
8. Manifestは不変Commit Recordの単一系列として扱う。各CommitはOperationID、ExpectedPredecessorHash、PayloadHash、CommitHashを保持。HeadはCommit Chainから導出する。Current Head単独はCommit証拠にしない。後続Commitがある場合も祖先Chainを検証する。同一PredecessorからのFork、Commit欠落、Chain破損はQUARANTINED。
9. Writer AuthorityはPhysicalRun単位で単一有効Writer。Run Manager Authority RegistryのみがWriter Grantを発行し、PhysicalRun単位のAuthority Epochを単調増加させる。Grant Eventは(PhysicalRunID, Epoch)で識別し、OwnerID / PreviousEpoch / GrantedBy / UTC timestamp / FenceProofHash / PreviousGrantHash / GrantHashを不変Authority Chainへ記録する。すべての更新にEpochを付し、旧EpochのWriterは拒否する。新Epoch発行には旧Epochのfencing proofが必須。時計・PID・Lock fileの存在だけでAuthorityを証明しない。Epochの一意な発行・比較を証明できない実装は受入不可。
10. Recovery AuthorityはBootstrapで明示登録されたPROJECT_RECOVERY_ADMIN principalに限定する。通常Writer / OperatorだけではRecovery Operationを発行できない。元Intent / Receipt / Event / Manifest Commitを編集しない。Recoveryができるのは検証、検証済みSourceからのMirror再構築、Derived View再構築、Integrity Report / 隔離記録の追記のみ。元証拠の書換え・削除・Hash再計算による置換・遡及Assignmentは禁止。v0.8.3ではRecovery OperationによるQUARANTINED解除を許可しない。解除機能は別設計・別承認とする。
11. DB MarkerはMirror更新と同一DB Transactionで一度だけ作成し、OperationIDを一意キーとする。Marker Payload HashはSource Commit後に実際のMarker Payloadから計算し、DB_COMMITTED Eventへ記録する。MarkerとMirrorの不一致、同一Operationの異Hash MarkerはQUARANTINED。
12. DB Commit結果不明時はMarkerとDB整合性を検証する。Marker完全一致ならCommit済み。MarkerなしでもDB integrity / transaction atomicity / consistent readを証明できない場合はQUARANTINEDとし、検索0件だけで未Commit・Rollbackを断定しない。再試行は同一Operation・同一Payloadに限る。
13. Receipt EventType RegistryはPREPARED / SOURCE_COMMITTED / DB_COMMITTED / VERIFIED / ABORTED / QUARANTINEDに固定する。未知EventTypeは拒否する。QUARANTINED Eventを元Chainへ追記できない破損時は別Integrity Reportへ記録し、元Chainを変更しない。
14. Operation Journal EventType RegistryはINTENT_PERSISTED / CANCEL_REQUESTED / SOURCE_COMMIT_RECORDED / DB_MARKER_COMMITTED / PHYSICAL_RUN_CLOSED / NONE_ASSOCIATION_CREATED / NONE_ASSOCIATION_CLOSED / ATTEMPT_STARTED / ATTEMPT_SUCCEEDED / ATTEMPT_FAILED / ATTEMPT_CANCELLED / ATTEMPT_INDETERMINATE / RETRY_CLOSED / REQUEST_CANCELLED / RECOVERY_OPERATION_CREATED / INTEGRITY_REPORT_CREATEDに固定する。EventにはEventType / EventOrdinal / OperationID / ActorID（system principalを含む）/ OccurredAtUTC / PayloadSchemaVersion / Payload / PreviousEventHash / EventHashを持たせる。Operation単位でOrdinal=1から連続し、最初のPreviousEventHashはNULL。Authority不明のEvent、未知EventType、partial tailは拒否・QUARANTINED。
15. Writer Grant EventはOperation Journal Eventと分離したAuthority Registry Chainとし、(PhysicalRunID, Epoch)で識別する。Epochは1から単調増加、欠番可・再利用不可。Grant Chainのpartial tail / Hash mismatch / ForkはWriter交代を禁止しRunをQUARANTINEDとする。
16. Assignment History EventはScope単位のappend-only chainとし、初期EventOrdinal=1、以降連続増加させる。Snapshot Revisionは初期0、以降の実変更ごとに連続増加させる。初期EventのBeforeStateはNULL、AfterStateはNONEまたはANONYMOUS。以降EventにはBeforeState / AfterState / AssignmentSnapshotID / Revision / ActorID / Reason / OccurredAtUTC / PreviousEventHash / EventHashを保持する。許容StateはASSIGNED / NONE / ANONYMOUS。未知State・Revision gap・Hash不一致はAssignment更新拒否・Scope隔離。
17. Event AuthorityはEventTypeごとに固定する。PHYSICAL_RUN_CLOSEDはRun Manager、WRITER_GRANTED / WRITER_RELEASEDはRun Manager Authority RegistryのAuthority Chain専用Event（Operation Journal Eventではない）、NONE_ASSOCIATION_CREATED / NONE_ASSOCIATION_CLOSEDは当該Scope / Physical Runの認証済みDB Session Manager、ATTEMPT_STARTED / ATTEMPT_SUCCEEDED / ATTEMPT_FAILED / ATTEMPT_CANCELLEDはAggregate ManagerのWorker principal、RETRY_CLOSED / REQUEST_CANCELLEDはAggregate Managerまたは権限を持つOperator、ATTEMPT_INDETERMINATEはAggregate ManagerがWorker停止 / fencing proofを検証した場合のみ、RECOVERY_OPERATION_CREATEDはRecovery Authorityのみが発行できる。ActorIDまたは権限証拠がない場合はEventを作成しない。
18. Physical Run Writer Authorityは、そのRunのJournal / Manifest / Receipt Chainだけを保護し、共有DB全体の排他を意味しない。異なるPhysical RunのDB transactionはDB engineのtransaction / isolation / unique constraintで整合させる。競合時はlast-write-winsを禁止し、同じOperation / Payloadの冪等再試行または新Operationでの再計画のみ許可する。DB側の競合分離・一意性を実証できないSQLite構成はSupported Environmentにしない。

### 14.5 Aggregate / Artifact
1. Request Fingerprintは§3.1の完全Field集合を用いる。Request ID・Ordinal・時刻を含めず、計算意味条件のみを表す。Full fieldsとHashを両方保存する。
2. RequestOrdinal / AttemptOrdinalは各Owner内で単調増加・再利用不可。Request内の成功Attemptは最大1件。Retry Closedは明示Eventで記録し、閉鎖後のAttemptを禁止する。
3. Current Validは最新RequestのFingerprintと一致する成功Resultだけ。古いRequestの遅延成功は履歴に保存するがCurrent Validへ昇格しない。PointerはDerived View。
4. Artifactは不変。再解析・Simulation・Algorithm / Config変更は新Artifact ID。Analysis / SimulationはArtifactKindで区別する。v0.8.3のArtifact InputTypeはMEASUREMENT_ENVELOPE / RAWLOG_REFERENCE / SAMPLE_REFERENCE / MEASUREMENT_PROFILE_SNAPSHOT / ANALYSIS_ARTIFACT / SIMULATION_ARTIFACT / AGGREGATE_RESULT_REVISIONの7種に固定し、未知Type / missing input / hash mismatch / cycleは拒否する。Input Ordinalは1から連続増加、Roleは非NULL、同一Artifact内Ordinal unique。Measurement Sample LinkはRole / Ordinal / Requiredを必須とする。Ordinalは(MeasurementID, Role)内で1から連続増加し、再利用不可。RoleはMeasurement Typeの正式Contractで定義された値のみ許可し、未知Roleは拒否する。Required=trueのLink欠落時はMeasurementをCOMPLETEにしない。Artifact InputのRequired / RoleはArtifactKindの正式Contractに従い、Required input欠落時はArtifact生成を拒否する。
5. CH1 / CH2を別Aggregate Ownerとし、暗黙平均・合算を禁止。Pair Analysisは明示入力を持つ別Artifactに限る。

### 14.6 RawLog / Sample / Measurement
1. RawLog Objectは原本byteを不変保管し、SHA-256はファイル全byteに適用。変換・改行統一・圧縮・metadata追加後のbyteを原本Hashと呼ばない。Format / Schema Versionは発行元の正式Contractから取得し、未知Versionはopaque保全のみ、解析不可。
2. RawLog IDはUUIDv4。Device Native Log ID、Path、Filenameは別属性でありIdentityにしない。Pathはcase-sensitive exact string。Path変更はReference更新履歴として記録し、RawLog Object identityを変えない。
3. 同一RawLog ID + 同一Hashの再試行は冪等。ID同一・Hash異なる場合はQUARANTINED。IDが異なりHash同一の場合は別Object identityとして保持可能。同一Path・同一Hashは既存Objectを参照し、同一Path・異Hashは上書き禁止・QUARANTINED。
4. SampleLocatorは発行元Schemaで定義された形式だけ解釈する。未定義Locatorはopaque referenceとして保全し、時刻・Channel・Sample ordinalを推測しない。Measurement Sample Linkは明示的なRole / Ordinal / Requiredを持つ。
5. RawLog保存完了は§8の全fsync / read-back / rename / directory fsync / final read-back / completion eventが成功した場合のみ。対象OS / filesystem / mount条件で実証されていない場合はDurable / VERIFIEDにしない。PENDING_RECOVERYまたはQUARANTINEDに固定する。
6. Measurement Outcomeは§14.2に従う。RawLog / Capture終端契約がないMotor / Batteryデータはopaque保存のみ許可し、意味解析・Current Aggregateに使用しない。Battery Issue #16の範囲で5A DATA原本・共通Measurement Envelope・CH1 / CH2独立Measurement / Sessionを保存できるが、正式な単位・式・RawLog Schemaが揃うまでFeature Extraction / Benchmark再計算 / mAh / Wh / voltage drop妥当性判定は行わない。CH1 / CH2は独立Measurement / RawLog / Session / Aggregateを保持し、標準Aggregateで平均化・合算しない。

### 14.7 Restore / Bootstrap
1. 外部正本を唯一の事実Authorityとし、DB Mirrorから外部正本を逆生成しない。
2. RestoreはPhase A structural validationとPhase B cross-evidence validationの二段階。Phase B完了前はVERIFIED / normal connectionを許可しない。
3. Missing / duplicate / fork / hash mismatch / unknown schema / partial tailは対象Objectと依存をQUARANTINED。推測補完・last-write-wins・tail truncationは禁止。
4. DB Mirror再生成は検証済み外部正本からのみ実行。Bootstrapは明示管理Operationのみで通常起動時に自動実行しない。
5. Retention Policyが未定義の正本は自動削除しない。既定保持は無期限。削除は別途明示承認されたRetention PolicyとAudit Eventがある場合のみ。

### 14.8 物理方式・受入証拠
1. 物理Lock方式、Epoch fencing、Filesystem durability、SQLite WAL / synchronous / isolation、crash injectionは本論理版で製品実装を指定しない。ただし§14の論理保証を実現・実証できない方式は採用不可。
2. 未検証OS / filesystem / SQLite設定ではSource Commit / DB_COMMITTED / VERIFIEDを宣言しない。試験済み構成だけをSupported Environmentとして登録する。
3. DB-RV-01〜08の論理選択は本節で確定。残るのは実装・テスト・外部契約の証拠回収と統括最終審査であり、設計選択を未決定に戻さない。
