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
3. DB Runは、そのPhysical Run内で**最初のASSIGNED Assignment Operationが確定した時点で一度だけ生成**する。
4. 一度生成されたDB Runは履歴コンテナとして保持し、全ScopeがNONE / ANONYMOUSへ移行しても削除しない。後日再ASSIGNEDとなっても同一DB Run IDを再利用する。
5. 一度もASSIGNEDになっていないPhysical RunにはDB Runを作らない。初期状態が全Scope NONE / ANONYMOUSであることと、過去にASSIGNED履歴がありDB Runが残存する状態を区別する。
6. DB Runの削除・再生成・ID再採番は禁止。訂正はOperation / Historyとして追加する。

### 1.2 RUN_SCOPE / Session

1. RUN_SCOPEはPhysical Run初期化時に全Scopeについて外部正本として作成する。Scope Keyごとに一意。
2. SessionはRUN_SCOPEにつき最大1件。**当該Scopeが一度でもASSIGNEDになった最初の確定Operationで生成し、その後はAssignment Stateにかかわらず保持する。**
3. 初期ANONYMOUS / NONEで一度もASSIGNEDになっていないScopeにはSessionを生成しない。
4. ASSIGNED→NONE→ASSIGNED、ASSIGNED→ANONYMOUS→ASSIGNED、ASSIGNED→別InstanceのいずれでもSession IDは変更しない。
5. Sessionの存在は「現在ASSIGNED」を意味しない。現在の割当状態はCurrent Assignment Snapshotのみで判定する。
6. Sessionに所属するMeasurement集合は、Session生成後にDBへ登録されたMeasurement Mirrorの集合であり、各MeasurementのAssignment-at-Measurementを必ず保持する。NONE期間のMeasurementについては、DB利用可能時に取得され、外部正本およびDB管理下のMeasurement記録が既に存在する場合に限り、後日の明示的Association Operationを論理設計対象としてよい。この操作は測定時AssignmentをNONEのまま保持し、実行主体・時刻・変更前後・理由を監査履歴へ記録する。既存DB管理Measurementを対象とし、新規RawLog取込やMeasurement Mirrorの自動生成を意味しない。NONEからの後日関連付けだけを理由にCurrent Aggregateへ算入しない。ANONYMOUS期間のMeasurement / RawLogは現行設計範囲で後日DB取込・Mirror化・Instance再紐付けを禁止し、明示操作による例外も認めない。将来の拡張は別設計と統括承認を要する。

### 1.3 Assignment遷移

| Before | After | Session / DB Run | 新規Measurementの取扱い |
|---|---|---|---|
| 初期NONE | NONE | 生成しない | 外部正本のみ |
| 初期ANONYMOUS | ANONYMOUS | 生成しない | 外部正本のみ |
| 初期NONE/ANONYMOUS | ASSIGNED | DB RunとSessionを生成 | 開始時点以降のASSIGNED測定をDB Mirrorへ登録 |
| ASSIGNED | ASSIGNED（同一Instance） | 維持 | 測定時Assignment Revisionを記録 |
| ASSIGNED | ASSIGNED（別Instance） | 維持 | 過去測定の帰属は変更しない |
| ASSIGNED | NONE | 維持・非アクティブ | NONE期間のAssignment-at-Measurementを固定。既にDB管理下にあるMeasurementのみ後日明示Association対象になり得る。新規取込・自動Mirror生成は禁止 |
| ASSIGNED | ANONYMOUS | 維持・制限状態 | ANONYMOUS期間の測定は外部正本のみ |
| NONE/ANONYMOUS（過去ASSIGNEDあり） | ASSIGNED | 既存IDを再利用 | 新規測定のみ現在のAssignmentに従う |

ANONYMOUSは「その期間の測定をInstanceに帰属させない」状態であり、過去にASSIGNEDだった期間の履歴を自動消去・書換えする命令ではない。過去データの消去・匿名化要求はAssignment変更と分離した、別の明示的なプライバシー処理として扱う。通常のAssignment Operationで既存Session・Measurement・Historyを削除しない。

### 1.4 Session Lifecycle / Measurement Outcome / Aggregate対象

1. Session LifecycleとMeasurement Outcomeは完全に分離する。Session LifecycleはNOT_CREATED / OPEN / CLOSED / QUARANTINEDとし、Measurement Outcome（COMPLETE / STOP / ERROR / CANCEL / INCOMPLETE / UNKNOWN）の集合・混在・件数からSession Lifecycleを導出しない。NOT_CREATEDはSessionレコードが存在しない状態である。初回ASSIGNED確定時にSessionを生成してOPENとし、Assignment変更や個々のMeasurement終了では閉じない。CLOSEDはRun管理側の明示的Close Operationが外部正本へ記録され、その記録と依存参照を検証できた場合に限る。Close Operationは論理Run管理イベントであり、STOP ACK・最終Telemetry・アプリ終了・プロセス消失・無通信時間からRun終了を推定しない。Close受入時は対象ScopeのCaptureが終端または明示的に放棄・保留され、未確定MeasurementをCOMPLETEへ読み替えない。終端不明・参照不整合はOPEN維持またはQUARANTINEDとし、推測でCLOSEDにしない。DB unavailable / ANONYMOUS運用ではDB Sessionを生成せず、外部正本上のRun / Capture情報を保持する。
2. **Current Aggregate**の対象は、現在ASSIGNEDであるScopeのうち、Measurement開始時点もASSIGNEDで、かつ測定時Instance IDが現在Instance IDと一致するMeasurementだけとする。
3. NONE / ANONYMOUS期間に開始したMeasurementは、後日ASSIGNEDになってもCurrent Aggregateへ遡及追加しない。既存Measurement IDをDB Mirrorへ明示登録する場合も、測定時AssignmentとInstance IDは不変であり、Current Aggregateの対象外とする。
4. 過去に別InstanceへASSIGNEDだったMeasurementは、再割当後のInstanceのCurrent Aggregateへ混入させない。
5. Current AssignmentがNONE / ANONYMOUSのScopeはCurrent Aggregate対象外。除外理由、Current Assignment Revision / State / HashをAggregate Requestに固定する。
6. 過去Assignmentの測定結果を分析する場合は、Current Aggregateとは別の明示的なHistorical Analysis Artifactを生成する。Pair Analysisも入力Measurementの時点帰属を維持し、CH1/CH2を平均化しない。

## 2. DB-RV-03 — Operation / Journal / Receiptの厳密な順序

### 2.1 正規順序

1. Physical Run単位の排他ロックを取得し、Journalと直近Ordinalを検証。
2. Operation ID / Ordinal / Intent Payload / Intent Hashを確定。
3. Journal Intentを追記し、ファイル本体・親Directoryを永続化する。Intent永続化完了時にOrdinalを消費済みとする。
4. Receipt本体を`PREPARED`として外部正本へ作成する。Receipt IDはUUIDv4を発行し、Journal Intentへ永続化する。ReceiptにはOperation ID / Ordinal / Intent Hash / Expected Source Payload Hashes / Expected DB Marker Hash / 対象Entity ID / Canonicalization Versionを含める。
5. Receipt本体・親Directoryを永続化し、Receipt PREPARED Eventを追記・永続化する。
6. 変更対象の外部正本（Assignment Snapshot / History / Envelope / Artifact / Aggregate Request等）を不変Revisionとして書き込み、File fsync・Hash再読込検証を行う。Current Manifest / Head Pointerは同一Operationのcommit markerとして原子的に更新し、親Directoryを永続化する。
7. 外部正本の新Revision / Manifest Hashを読み戻し、Journal Intent / Receipt PREPAREDのExpected Source Payload Hashesと照合する。成功したらReceipt Event `SOURCE_COMMITTED`を追記・永続化する。
8. DB transactionを開始し、対象DB Mirror変更とOperation Markerを同一transactionでCommitする。MarkerにはOperation ID / Ordinal / Intent Hash / Receipt ID / Source Commit Hash / DB Commit Payload Hashを含める。
9. Commit結果を読み戻し、MarkerとJournal Intent / Receipt / Source Commit Hashを照合する。
10. Receipt Event `DB_COMMITTED`を外部正本へ追記・永続化する。
11. Journal / Marker / Receipt / 関連外部正本を再検証する。
12. Receipt Event `VERIFIED`を追記・永続化する。
13. すべての永続化・照合が成功した後に排他ロックを解放する。

Journal IntentとReceipt PREPAREDは別の証拠であり、同一視しない。PREPAREDはSource CommitおよびDB Commitより前に外部正本として永続化される。外部正本のcommit markerが先に確定し、DBはその外部正本から再生成可能なMirrorとして後続Commitする。

### 2.2 Receipt State

- PREPARED: Intentが永続化され、DB Commit前の証拠が存在する。
- SOURCE_COMMITTED: 変更対象の外部正本RevisionとManifest Headが永続化され、Hash照合済み。
- DB_COMMITTED: DB MirrorのMarkerが同一TransactionでCommitされ、読み戻し照合済み。
- VERIFIED: 関連Hash・外部正本・Markerの整合性が確認済み。
- ABORTED: DB Commitが存在しないことを確認し、明示的中止Eventを永続化済み。
- QUARANTINED: 証拠欠落・競合・Hash不一致等で自動判定不能。自動復帰禁止。

Stateは単調遷移とし、PREPAREDからABORTEDへ進めるのは外部正本のSource Commit前に限る。SOURCE_COMMITTED後はOperationを中止・巻戻しせず、同じOperationでDB Mirrorを再構築するかQUARANTINEDへ隔離する。DB_COMMITTED後にABORTEDへ戻してはならない。VERIFIEDは終端状態。QUARANTINEDは隔離状態であり、元Receiptを編集しない。解決操作は新しいRecovery Operationとして記録する。

### 2.3 クラッシュ復旧表

| 停止点 | 再起動後の根拠 | 許可される処理 |
|---|---|---|
| Journal Intent前 | 永続証拠なし | 未実行として扱う。Ordinal未消費 |
| Intent後、Receipt PREPARED前 | Journal Intent | 同一Operation ID / OrdinalでReceipt PREPAREDを作成、またはABORTEDを記録 |
| PREPARED後、Source Commit前 | Journal + PREPARED | 同一Operationを再開、またはSource Commit未実施を確認してABORTED |
| Source Commit後、DB transaction前 | Journal + PREPARED + Source Manifest Head | ABORTED禁止。同一OperationでDB Mirrorを再開 |
| DB transaction中 | Journal + PREPARED + DB Marker有無 | MarkerのCommit有無を読み戻し、同一Operationで再開 |
| DB Commit後、DB_COMMITTED Event前 | DB Marker + SOURCE_COMMITTED | Hash一致を確認してDB_COMMITTED Eventを補完 |
| DB_COMMITTED後、VERIFIED前 | Marker + Journal + Receipt | 全依存正本を検証しVERIFIED、またはQUARANTINED |
| Hash / ID / Ordinal競合 | 不一致証拠 | QUARANTINED。推測修復・別Operationへの付替え禁止 |

同一Operation IDでIntent Hashが異なる再実行は即時QUARANTINED。Ordinalは欠番を許容し再利用しない。Receipt EventはEvent Ordinal単調増加・Hash Chainで保全する。


## 3. DB-RV-04 — Aggregate Request / Attempt / Result Revision（v0.8.3決定）

### 3.1 IdentityとRequest Fingerprint
- Request IDは要求インスタンスのUUIDv4 identity。Request Fingerprintは計算意味条件の同一性Hashであり、Request ID・Request Ordinal・時刻を含めない。
- Fingerprintは次の固定Fieldを含む: DBRunID、ScopeKey、AggregateType、InputSetHash、AssignmentSnapshotSetHash、AlgorithmVersion、ConfigurationVersion、MeasurementSchemaRevision、ProfileSnapshotSetHash、PolicyRevision、AggregateDefinitionVersion、ChannelKey（該当時）。
- 上記Fieldの全値をRequest Envelopeに保存し、M4W-JCS-1 / SHA-256でFingerprintを算出する。Hashのみ保存は禁止。
- RequestOrdinalは(DBRunID, ScopeKey, AggregateType)単位で1から単調増加。欠番可、再利用不可。AttemptOrdinalはRequest内で1から単調増加、欠番可、再利用不可。

### 3.2 Attempt / Retry / Result
- Requestは不変。Attemptは試行ごとに新規作成。Attempt StatusはRUNNING / SUCCEEDED / FAILED / CANCELLEDとする。
- Retryable / Retry ClosedはAttempt結果とは別のRequest Eventで記録する。Retry Closed EventはActor / UTC timestamp / Reason / PolicyVersionを必須とする。
- Retry Closed後の新規Attemptは禁止。RequestがRetry Closedとなり、成功Attemptが一つもない場合だけFAILEDと確定する。成功Attemptが一つ存在した時点でRequestはSUCCEEDED終端となり、追加Attemptを禁止する。
- Result Revisionは成功Attemptのみが生成できる。Request内で成功Resultは最大1件。失敗AttemptからResult Revisionを生成しない。
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
- Physical Run IDはRun Managerが発行する。DB Run / Session / Assignment Snapshot / Measurement / Profile Snapshot / RawLog Object / RawLog Reference / Sample Reference / Operation / Receipt / Artifact / Aggregate Request / Attempt / Result Revision / Recovery Operation / Integrity Reportは、それぞれの作成AuthorityがUUIDv4を発行する。
- Receipt IDはOperation IDから導出しない。Receipt作成前にUUIDv4を発行し、Intent内に固定する。再起動時はIntentに記録された同じIDを使用する。
- RUN_SCOPEは独立UUIDを持たず、(PhysicalRunID, ScopeKey)を複合識別子とする。Measurement-Sample LinkとArtifact Inputも親ID + Ordinal等の複合識別子を用いる。Aggregate Pointerは派生値でありIDを持たない。
- UUID文字列表現は小文字・ハイフン付きCanonical形式のみを受け入れる。大文字、波括弧、短縮形、非Canonical表現は拒否する。全Entity ID間で重複を禁止し、参照時はEntity Typeも一致させる。
- UUIDv5 / Canonical Binary Name v2 / Namespaceはv0.8.3のID発行方式として採用しない。過去に生成済みのIDは変更・再採番しない。

### 5.2 Structured Hash Profile M4W-JCS-1
- 構造化PayloadのHashはSHA-256を使用し、RFC 8785 JSON Canonicalization Schemeに従うUTF-8バイト列を入力とする。
- Duplicate JSON key、invalid Unicode scalar、NaN / Infinity、浮動小数点数、未知Schema Version、未知Entity Type / Fieldは拒否する。欠落FieldとNULLは区別する。
- 整数はIEEE-754 safe integer範囲（-(2^53-1)〜+(2^53-1)）に限定する。範囲外整数と精度が必要な測定値・小数値は正規化済みDecimal文字列（指数表記・先頭+・不要な先頭/末尾0・負の0を禁止）で表し、JSON numberとして格納しない。
- Timestampはtimezone-aware値のみ受け入れ、UTCへ変換し、YYYY-MM-DDTHH:mm:ss.ffffffZの6桁小数秒で固定する。naive timestamp、microsecond未満の精度、範囲外値は拒否し、丸めない。
- Unicodeは正規化・case-foldを行わず、入力されたUnicode scalar列をそのまま保持する。JCSの文字列順序規則に従う。見た目が同じ文字列でもcode point列が異なれば異なるHashとなる。Decimal文字列は指数表記・先頭+・不要な先頭ゼロ・不要な小数末尾ゼロを禁止し、負の0は0へ正規化する。
- Byte StringはBase64url（paddingなし）で表現する。NULLはEntity Schemaでnullableと明記されたFieldのみ許可する。
- 自己Hash Field（例: payload_hash / event_hash）はHash入力から除外する。除外対象FieldはEntityごとに固定し、後から暗黙変更しない。SchemaまたはCanonicalization規則変更は新Versionとする。
- RawLog ObjectのContent Hashだけは例外として、変換・正規化前のファイル全バイト（header / metadataを含む）にSHA-256を直接適用する。Structured HashとRawLog Content Hashを混同しない。

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
| RUN_SCOPE | Scope Manifest / Assignment Snapshot | DB Run生成後、Physical Run内の全ScopeをMirror可能 | 外部Scope一覧から再生成 |
| Assignment Snapshot / History | Scope単位の不変ファイル | あり（Mirrorのみ） | Hash Chain検証後に再生成 |
| Measurement | Measurement Envelope | 測定時ASSIGNEDのMeasurementを登録。NONE期間はDB利用可能時に取得され、既にDB管理下にあるMeasurementに限り、後日ASSOCIATION OperationでInstance関連付け可能。ANONYMOUS期間のMeasurement / RawLogは後日取込・Mirror化・再紐付け禁止 | Envelopeから再生成。測定時Assignmentを変更しない。NONEの関連付けはOperation ID / Actor / 時刻 / 変更前後 / 理由を監査履歴へ記録 |
| Measurement Profile Snapshot | Measurement Envelopeが参照する不変Snapshot | あり（Mirrorのみ） | Snapshot Hash検証後に再生成 |
| RawLog / Sample Reference | RawLog本体 / Reference Manifest | 参照Mirrorのみ | 本文Hash一致を検証して再生成 |
| Analysis / Simulation Artifact | Artifact Envelope / Result Payload | 参照・検索Mirror | DAGと入力Hash検証後に再生成 |
| Operation Journal | Physical Run Journal | Marker / Journal Mirror | Journal正本から再生成 |
| Receipt / Receipt Event | Receipt Envelope / Event Log | あり（Mirrorのみ） | 依存証拠の二段階検証後に再生成 |
| Aggregate Request / Attempt / Result | Aggregate Envelope / Result Payload | Pointer / 検索Mirror | Request/Attempt/ResultのHash検証後に再生成 |

全ScopeがNONE / ANONYMOUSで一度もASSIGNEDになっていない場合、Physical Run / RUN_SCOPE / Assignment Snapshot / Measurement Envelope / RawLog / Artifact等は外部正本だけで再構築可能とする。DB Run / Session / DB Mirrorを作らない。後日初回ASSIGNEDでDB Runを生成した後は、必要な全ScopeのManifestとSnapshotをMirrorする。NONE期間のMeasurementは、DB利用可能時に取得され、外部正本およびDB管理下のMeasurement記録が既に存在する場合に限り、既存Measurement IDを維持した明示的Association Operationの対象にできる。関連付け時もAssignment-at-MeasurementはNONEのままとし、実行主体・時刻・変更前後・理由を監査履歴へ残す。関連付けだけを理由にCurrent Aggregateへ遡及包含しない。ANONYMOUS期間のMeasurement / RawLogは後日DB取込・Mirror化・Instance再紐付けを禁止し、明示操作による例外も認めない。

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

RawLogの保存完了は、同一ファイルシステム内のAtomic Renameだけでは成立しない。論理受入条件として以下を要求する。
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
5. DB Run / Session / Measurement Mirrorの生成条件を1章・6章に従って判定。
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
4. Battery Issue #16はE2E検証範囲としてのみ扱う。Batteryの完全Measurement / RawLog / Capture End / durability / retention契約は、正式契約受領までDB登録・解析の対象外とする。CH1 / CH2独立性と平均化禁止は維持する。
5. Profile Snapshot / Artifact / Recovery / Integrity Report等で完全なField Schemaがない部分は、v0.8.3で未知Fieldを創作しない。外部正本の不透明なPayload Reference + exact Content Hashとして保全し、DB Mirrorでは既知の共通Envelope項目だけを索引化する。未知Payloadの意味解析・Aggregate入力は禁止する。
6. Run Close Operationの発行AuthorityはRun Managerに限定する。正式なClose証拠がない場合SessionはOPENを維持し、終端矛盾・Hash不一致・Writer競合はQUARANTINEDとする。
7. RawLogの物理耐久性は、対象OS / filesystem / mount条件でSection 8の全工程が試験合格するまでSUPPORTEDとしない。未検証環境ではRawLogをDurable / VERIFIEDとして確定せず、PENDING_RECOVERYまたはQUARANTINEDとする。
8. SQLiteのTransaction / Marker / WAL / read-back / crash recoveryは物理受入試験合格まで保証済みと扱わない。論理規則は§14で固定し、試験未実施の環境ではDB_COMMITTED / VERIFIEDを宣言しない。
9. 全Entityの完全物理Schema・DDL・複合FK・Triggerは本論理版の決定範囲外。§14.3 / §14.8の共通Envelope / identity / relation contractのみを確定し、物理DDLは別承認後に作成する。
10. v0.8.3の設計判断は本書§14およびIssue #210 CC-01 / CC-02で閉じる。実装・受入試験の実行結果、他部門正式契約の回収、統括最終承認は別のGateであり、未実施をPASSとみなさない。


## 13. 自己検証チェックリスト

- [ ] DB Run / Sessionの初期生成と履歴保持の状態遷移を全組合せ確認
- [ ] Current AssignmentとAssignment-at-Measurementを分離してAggregate対象を確認
- [ ] Journal / Receipt / DB Markerの永続化順と全クラッシュ点を確認
- [ ] Request / Attempt / Result Revision / Pointerの全状態遷移を確認
- [ ] Artifact DAG循環禁止と不変再解析を確認
- [ ] Canonical Binary Name v2の文法・byte vector・Namespace承認状況を確認
- [ ] 外部正本 / DB Mirrorの全Entityを復元条件付きで確認
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
1. Physical RunはRun Manager発行UUIDv4。DB Runは独立UUIDv4で、Physical Run内の最初のASSIGNED Assignment Operationで一度だけ生成する。DB RunはPhysical Runにつき最大1件。
2. RUN_SCOPEは(PhysicalRunID, ScopeKey)複合識別子。v0.8.3のScopeKey許容値はMOTOR / BATTERY_CH1 / BATTERY_CH2の3値に固定し、未知値は拒否する。Motor / Battery CH1 / Battery CH2を別Scopeとして扱う。CH1 / CH2の同一化・平均化は禁止。
3. SessionはScopeごと最大1件。初回ASSIGNED確定時にUUIDv4で生成し、以後Assignment Stateにかかわらず保持する。NONE / ANONYMOUSだけで一度もASSIGNEDにならないScopeにはSessionを生成しない。
4. DB Run / Session生成前の初期NONE Measurementは外部正本のみ。当該Scopeの初回ASSIGNED後に取得され、当該ScopeのSessionが既に存在し、DB利用可能時に外部正本とDB管理下のMeasurement記録が確定したNONE MeasurementだけがSessionに所属できる。他ScopeのASSIGNEDによるDB Run生成は、未ASSIGNED ScopeのNONE Measurementを自動的にDB管理対象へ昇格させない。NONE Measurementの測定時AssignmentはNONE・InstanceID NULLのまま不変。
5. NONE Measurementの後日Associationは、既存DB管理Measurementに対する明示Operationのみ許可する。1つのMeasurementに同時に有効なAssociationは最大1件。再関連付けは新Operationで旧Associationを閉じ、新Associationを追加する。Actor / UTC time / Reason / before-after / OperationIDを記録する。Assignment-at-Measurementは変更しない。
6. 初回ASSIGNED前のNONE期間のMeasurement、ANONYMOUS期間のMeasurement / RawLogは外部正本のみ。後日DB取込・Mirror化・Associationは禁止。ANONYMOUSの将来拡張は別設計・明示承認が必要。
7. NONE MeasurementはCurrent Aggregateから常に除外する。Historical Analysisでの利用は、明示的に指定された場合のみ許可し、ArtifactにRETROSPECTIVE_NONEを記録する。ANONYMOUSは分析入力としても現行範囲外。
8. Assignment SnapshotはScope単位の不変Revision。Revisionは1から単調増加、欠番不可、再利用不可。Current Assignmentは最新の検証済みSnapshotから導出する。履歴は追記のみ。

### 14.2 Measurement Outcome / Session Close
1. Measurement OutcomeはCOMPLETE / STOP / ERROR / CANCEL / INCOMPLETE / UNKNOWN。OutcomeはMeasurement単位でありSession Lifecycleへ伝播しない。
2. COMPLETEは機器固有Capture契約が正常終端と必須Sample完了を明示した場合のみ。STOP / ERROR / CANCELは明示された終端Eventのみ。開始が確認でき、Capture終端または必須Sampleの欠落が確認された場合INCOMPLETE。開始・終端の存在や順序を確定できない、または証拠が矛盾する場合UNKNOWN。時間経過・無通信・アプリ終了・最終値の有無から推定しない。
3. 各機器の詳細Termination Reasonは発行元の文字列・コードを原形保存し、DB側で意味を再解釈しない。正式MappingがないReasonはUNKNOWN扱い。Current Aggregateへ入るのはOutcome=COMPLETEのMeasurementのみ。
4. Session LifecycleはNOT_CREATED / OPEN / CLOSED / QUARANTINED。CLOSEDはRun Managerが発行するPHYSICAL_RUN_CLOSED Operationが外部正本に永続化され、全ScopeのDispositionがTERMINAL / ABANDONED / HELDのいずれかで、依存証拠が検証済みの場合のみ。未終端をCOMPLETEに読み替えない。
5. Close OperationにはPhysicalRunID、OperationID、ActorID、UTC timestamp、Reason、各ScopeのDisposition、各Capture / Measurementの参照とHash、未解決事項一覧を含める。HELD / ABANDONEDは理由必須。未解決の矛盾・欠落・Hash不一致・Authority不明はOPEN維持またはQUARANTINED。機器プロトコルの既存Eventを新設・変更しない。

### 14.3 Entity / Schema境界
1. 23 Inventory概念は保持するが、23すべてを独立SQL Tableにする要求は採用しない。Authority・identity・lifecycleに従い、外部正本Object / Append-only Event / DB Mirror / Derived Viewに分類する。
2. OPERATION_EVENTは独立Entityとして採用しない。Operation Journal Eventの型付きEventとして扱い、Identityは(OperationID, EventOrdinal)。TEST_VALUEは試験ベクトル専用で業務Entityではない。
3. Analysis Artifact / Simulation Artifactは共通Artifact Envelopeを使い、ArtifactKindで区別する。Payload Schemaと検証器はKindごとに分離する。Recovery OperationとIntegrity Reportは別Entity。Aggregate PointerはDerived Viewであり独立ID・正本・独立Tableを持たない。
4. RawLog ObjectとRawLog Reference、Measurement EnvelopeとMeasurement Content Hash、Artifact IDとPayload Hash、Operation IntentとOperation Eventは別概念として保持する。
5. 完全なField Schemaが外部契約で定義されていないEntityは、既知の共通Envelope（EntityType、SchemaVersion、EntityID、OwnerReference、CreatedAtUTC、PayloadReference、PayloadHash）と既知の関係だけを扱う。未知のPayloadは不透明データとして保存し、意味解析・Aggregate入力・フィールド補完を禁止する。Payloadの不透明保全も外部正本の保存検証ができない場合は受け入れない。
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
9. Writer AuthorityはPhysicalRun単位で単一有効Writer。Run Manager Authority RegistryのみがWriter Grantを発行し、PhysicalRun単位のAuthority Epochを単調増加させ、OwnerID / PreviousEpoch / GrantedBy / UTC timestamp / FenceProofHashを不変Grant Eventに記録する。すべての更新にEpochを付し、旧EpochのWriterは拒否する。新Epoch発行には旧Epochのfencing proofが必須。時計・PID・Lock fileの存在だけでAuthorityを証明しない。Epochの一意な発行・比較を証明できない実装は受入不可。
10. Recovery Authorityは新しいRecovery Operationを発行できる主体に限定。元Intent / Receipt / Event / Manifest Commitを編集しない。Recoveryができるのは検証、Mirror再構築、Derived View再構築、隔離記録の追記のみ。元証拠の書換え・削除・Hash再計算による置換・遡及Assignmentは禁止。
11. DB MarkerはMirror更新と同一DB Transactionで一度だけ作成し、OperationIDを一意キーとする。Marker Payload HashはSource Commit後に実際のMarker Payloadから計算し、DB_COMMITTED Eventへ記録する。MarkerとMirrorの不一致、同一Operationの異Hash MarkerはQUARANTINED。
12. DB Commit結果不明時はMarkerとDB整合性を検証する。Marker完全一致ならCommit済み。MarkerなしでもDB integrity / transaction atomicity / consistent readを証明できない場合はQUARANTINEDとし、検索0件だけで未Commit・Rollbackを断定しない。再試行は同一Operation・同一Payloadに限る。

### 14.5 Aggregate / Artifact
1. Request Fingerprintは§3.1の完全Field集合を用いる。Request ID・Ordinal・時刻を含めず、計算意味条件のみを表す。Full fieldsとHashを両方保存する。
2. RequestOrdinal / AttemptOrdinalは各Owner内で単調増加・再利用不可。Request内の成功Attemptは最大1件。Retry Closedは明示Eventで記録し、閉鎖後のAttemptを禁止する。
3. Current Validは最新RequestのFingerprintと一致する成功Resultだけ。古いRequestの遅延成功は履歴に保存するがCurrent Validへ昇格しない。PointerはDerived View。
4. Artifactは不変。再解析・Simulation・Algorithm / Config変更は新Artifact ID。Analysis / SimulationはArtifactKindで区別する。v0.8.3のArtifact InputTypeはMEASUREMENT_ENVELOPE / RAWLOG_REFERENCE / SAMPLE_REFERENCE / MEASUREMENT_PROFILE_SNAPSHOT / ANALYSIS_ARTIFACT / SIMULATION_ARTIFACT / AGGREGATE_RESULT_REVISIONの7種に固定し、未知Type / missing input / hash mismatch / cycleは拒否する。Input Ordinalは1から連続増加、Roleは非NULL、同一Artifact内Ordinal unique。Measurement Sample LinkはRole / Ordinal / Requiredを必須とする。
5. CH1 / CH2を別Aggregate Ownerとし、暗黙平均・合算を禁止。Pair Analysisは明示入力を持つ別Artifactに限る。

### 14.6 RawLog / Sample / Measurement
1. RawLog Objectは原本byteを不変保管し、SHA-256はファイル全byteに適用。変換・改行統一・圧縮・metadata追加後のbyteを原本Hashと呼ばない。Format / Schema Versionは発行元の正式Contractから取得し、未知Versionはopaque保全のみ、解析不可。
2. RawLog IDはUUIDv4。Device Native Log ID、Path、Filenameは別属性でありIdentityにしない。Pathはcase-sensitive exact string。Path変更はReference更新履歴として記録し、RawLog Object identityを変えない。
3. 同一RawLog ID + 同一Hashの再試行は冪等。ID同一・Hash異なる場合はQUARANTINED。IDが異なりHash同一の場合は別Object identityとして保持可能。同一Path・同一Hashは既存Objectを参照し、同一Path・異Hashは上書き禁止・QUARANTINED。
4. SampleLocatorは発行元Schemaで定義された形式だけ解釈する。未定義Locatorはopaque referenceとして保全し、時刻・Channel・Sample ordinalを推測しない。Measurement Sample Linkは明示的なRole / Ordinal / Requiredを持つ。
5. RawLog保存完了は§8の全fsync / read-back / rename / directory fsync / final read-back / completion eventが成功した場合のみ。対象OS / filesystem / mount条件で実証されていない場合はDurable / VERIFIEDにしない。PENDING_RECOVERYまたはQUARANTINEDに固定する。
6. Measurement Outcomeは§14.2に従う。RawLog / Capture終端契約がないMotor / Batteryデータは意味解析・Current Aggregateに使用しない。Battery CH1 / CH2は独立Measurement / RawLog / Session / Aggregateを保持する。

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
