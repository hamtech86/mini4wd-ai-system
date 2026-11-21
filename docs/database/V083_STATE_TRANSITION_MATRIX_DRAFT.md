# v0.8.3 状態遷移・集約判定マトリクス（検証用ドラフト）

- 基準日: 2026-11-21
- 対象: v0.8.3 remediation draft
- 状態: 検証用補助資料・未承認
- 目的: Assignment / DB Run / Session / Measurement / Aggregate / Receiptの状態組合せを列挙し、本文の曖昧さを検出する。
- 本書は新たな統括承認ではない。Issue #210 CC-02で許容されたNONE既存DB管理Measurementの明示Associationを定義する。DB unavailableはIssue #201のAnonymous Modeとして扱い、障害期間のCaptureを復旧後にBootstrap / 取込することは含めない。

## 1. 前提と範囲境界

1. Physical Run IDは外部正本上の識別子。DB Run IDとは別ID。
2. DB Runは、利用承認済みで既に存在するDBが正常利用可能な場合に限り、Physical Run内で最初の確定ASSIGNED Operationに伴うMirror recordとして作成する。
3. この作成規則はDB file / schema / empty DB / migration / Bootstrapの生成許可ではない。
4. SessionはScopeごとに最大1件。DB正常利用可能時の初回有効ASSIGNED Assignment Operation確定時にRun ManagerがUUIDv4の論理Session identityを発行し、同じ外部Run Manifest Commitへ記録する。以後NONE / ANONYMOUS / 別Instanceへの遷移でも保持する。DB Session Mirrorは同一IDで生成する。DB unavailable期間はAnonymous Modeとして有効ASSIGNED Operation・新規Session identity・DB Session Mirrorを生成しない。
5. ANONYMOUS期間およびDB unavailable期間のMeasurement / RawLogは外部正本に保全し、後日DB取込・Mirror化・Instance再紐付けを禁止する。DB unavailableはAssignment StateにかかわらずAnonymous Mode扱いとする。NONE期間は別扱いとし、DB正常利用可能時に取得され既にDB管理Measurementとして登録済みのものに限り、後日の明示Association Operationを許容する。AssociationはInstance関連付け履歴のみでSession membershipを変更せず、Assignment-at-Measurement=NONEを保持し、Current Aggregateへ自動算入しない。
6. MeasurementのAssignment-at-Measurementは開始確定時の不変Snapshotであり、Current Assignmentの変更で更新しない。

## 2. Assignment / DB Run / Session状態遷移

| 遷移 | DB Run | 対象Scope Session | Measurement保存・登録 | Current Aggregate |
|---|---|---|---|---|
| 初期 → NONE | なし | なし | 外部正本のみ | 対象外 |
| 初期 → ANONYMOUS | なし | なし | 外部正本のみ | 対象外 |
| NONE → ASSIGNED(A) | DB正常利用可能時になければ作成 | Run Managerが論理Session UUIDv4を外部Manifestへ生成。DB正常利用可能時のみ同一IDのDB Session Mirror作成 | DB正常利用可能時の以後のASSIGNED測定をMirror登録 | A測定のみ候補 |
| ANONYMOUS → ASSIGNED(A) | DB正常利用可能時の有効Assignment Operation確定時に作成 | 論理Session identityとDB Session Mirrorを同一IDで生成 | 以後の有効ASSIGNED測定をMirror登録。過去ANONYMOUSデータは取込禁止 | A測定のみ候補 |
| ASSIGNED(A) → ASSIGNED(A) | 保持 | 保持 | 測定時Revisionを固定 | A測定のみ候補 |
| ASSIGNED(A) → ASSIGNED(B) | 保持 | 保持 | 新規測定はB。A測定の帰属は不変 | B測定のみ候補 |
| ASSIGNED(A) → NONE | 保持 | 保持・非アクティブ | DB正常利用可能時に登録されたNONE MeasurementはSession membershipを登録時点で固定。後日のAssociationはInstance関連付けのみ。障害期間のCaptureはAnonymous Mode扱いで後日取込禁止 | 対象外 |
| ASSIGNED(A) → ANONYMOUS | 保持 | 保持・非アクティブ | ANONYMOUS期間は外部正本のみ。後日DB取込・Mirror化・Instance再紐付け禁止 | 対象外 |
| 過去ASSIGNEDあり NONE → ASSIGNED(A) | 同一IDを保持 | 同一IDを保持 | 新規A測定をMirror登録。NONE期間の既存DB管理Measurementは明示Associationのみ可。測定時Assignment=NONEを維持 | A測定のみ候補。NONE由来は対象外 |
| 過去ASSIGNEDあり ANONYMOUS → ASSIGNED(A) | 同一IDを保持 | 同一IDを保持 | 新規A測定のみMirror登録。過去ANONYMOUSデータは後日取込・Mirror化・再紐付け禁止 | A測定のみ候補 |
| DB unavailable中に初回ASSIGNEDを試行 → DB復旧（同一Physical Run） | 有効Assignment / DB Runなし | Logical Session identityも生成しない。CaptureのAssignment-at-Measurement=ANONYMOUS（InstanceID=NULL） | 障害期間のCaptureは外部正本のみ。復旧後のBootstrap / DB化 / 取込を禁止。DB管理は新Physical Runから開始 | 対象外 |

補足:
- Physical Run内で別Scopeが後日初めてASSIGNEDになった場合、DB Runは既存IDを使い、そのScopeだけSessionを新規生成する。
- 一つのPhysical Run内で全ScopeがNONE / ANONYMOUSになっても、既に生成済みDB Run / Sessionを削除しない。
- Sessionが存在することは現在ASSIGNEDであることを意味しない。
- Assignmentの変更は既存Measurement / RawLog / Artifactの削除・書換えを行わない。
- Session membershipはMeasurementを外部Run Manifestへ初回確定記録した時点で同一Scopeの論理Session identityが存在する場合に固定し、後からSessionへ遡及所属させない。DB Mirrorの有無はmembershipの事実を変えない。outage前から既存identityがある場合、outage中Captureは外部membershipへ記録できるが、Assignment-at-Measurement=ANONYMOUSであり、DB Session Mirror membershipへは追加・後日遡及追加しない。outage中に初回ASSIGNEDを試みたScopeはSession identityなし。NONEの後日Associationは既存DB管理Measurementに対する明示操作に限定し、Instance関連付け履歴のみを作成する。Session membershipは変更しない。実行主体・時刻・変更前後・理由・OperationIDを監査履歴へ残し、Assignment-at-MeasurementはNONEのまま不変。
- ANONYMOUSは現行設計範囲で後日DB取込・Mirror化・Instance再紐付けを禁止する。将来拡張には別設計と統括承認を要する。
- Anonymous化・消去要求はAssignment遷移とは別の明示的プライバシー処理。通常のAssignment Operationで履歴を消去しない。

### 2.1 Session Lifecycle独立性（Issue #210 CC-01）

Session LifecycleはSession Entityの独立状態であり、Measurement Outcome / 件数 / 混在パターンから導出しない。

| 状況 | Measurement Outcome | Session Lifecycleの期待 |
|---|---|---|
| 初期NONE / ANONYMOUSのみ | Measurementなし、または外部正本上のOutcome | NOT_CREATED（Session rowなし） |
| DB正常利用可能時の初回有効ASSIGNED確定 | Measurement 0件 | 外部Manifestに論理Session identity生成、OPEN。同一IDのDB Session Mirror生成 |
| Session OPEN、Measurement 0件 | 該当なし | OPEN維持 |
| Session OPEN、全Measurement COMPLETE | 各Measurement=COMPLETE | OPEN維持 |
| Session OPEN、全Measurement STOP / ERROR / CANCEL | 各Measurement固有Outcome | OPEN維持 |
| Session OPEN、Outcome混在 | 各Measurement固有Outcome | OPEN維持 |
| Run管理側の明示Close Operationを受理・外部正本と依存参照検証済み | 対象Captureが終端または明示放棄/保留 | CLOSED |
| Close Operationなし、STOP ACK / 最終Telemetry / app exit / inactivityのみ | 任意 | CLOSED禁止 |
| Close対象Capture未終端または参照不整合 | UNKNOWN等を含み得る | OPEN維持またはQUARANTINED |

Session LifecycleにNOT_STARTED / IN_PROGRESS / COMPLETE / PARTIAL / FAILEDを割り当てない。これらは旧V082 Session集約案の語彙であり、現行CC-01 Lifecycleではない。MeasurementのOutcomeとCaptureの終端確定条件は機器固有契約に従い、DB側で推測しない。

### 2.2 CC-01 / CC-02追加受入ケース（提案・未実行）

| Test ID | 条件 | 期待結果 |
|---|---|---|
| SES-017 | 初回ASSIGNED後、Measurement 0件 | SessionはOPEN。Measurement件数からNOT_STARTED等へ変化しない |
| SES-018 | Session OPEN、全Measurement COMPLETE | SessionはOPEN。Outcomeを理由にCLOSEDにしない |
| SES-019 | Session OPEN、全Measurement ERROR / STOP | SessionはOPEN。Outcomeを理由にCLOSEDにしない |
| SES-020 | COMPLETE / STOP / ERROR / CANCEL混在 | Measurement Outcomeを個別保持。Session LifecycleはOPEN |
| SES-021 | STOP ACKのみ / 最終Telemetryのみ / app exitのみ | Close OperationがないためCLOSEDにしない |
| SES-022 | 明示Close Operationあり、Capture全件終端または明示放棄/保留、依存参照検証成功 | SessionをCLOSEDにできる |
| SES-023 | 明示Close Operation時に未終端Captureまたは参照不整合 | CLOSED拒否。OPEN維持またはQUARANTINED |
| SES-024 | Close Operationの外部正本が欠落・Hash不一致 | CLOSED拒否。OPEN維持またはQUARANTINED |
| SES-025 | NONE期間の既存DB管理Measurementを明示Association | Assignment-at-Measurement=NONEを保持し監査記録。自動Aggregate算入なし |
| SES-026 | ANONYMOUS期間のMeasurement / RawLogを後日関連付け要求 | 取込・Mirror化・Instance再紐付けを拒否 |
| SES-027 | DB正常利用可能時、Session生成前のNONE Measurementを登録し、その後初回ASSIGNED | Session membershipへ遡及追加しない |
| SES-028 | 既存SessionのあるScopeでDB正常利用可能時にNONE Measurementを登録 | 登録時点で同一Scope Session membershipを固定。後日Associationでmembership変更なし |
| SES-029 | DB unavailable中にASSIGNEDを試みCaptureを取得しDB復旧 | 有効Assignment / Logical Session identity / DB Session / Measurement Mirrorなし。Assignment-at-Measurement=ANONYMOUS。障害期間データのBootstrap / DB取込 / Mirror化 / Associationを拒否 |
| SES-030 | NONE Measurementへ初回Associationを作成 | NONE_ASSOCIATION_CREATEDを記録。AssociationOrdinal=1、Active最大1件、Assignment-at-Measurement / Session membership不変 |
| SES-031 | Active Associationを解除 | 対応するNONE_ASSOCIATION_CLOSEDを記録。CloseReason必須。過去Event不変 |
| SES-032 | Active Associationを別Instanceへ再関連付け | 同一Operation内で旧AssociationをCloseし、次AssociationOrdinalをCreate。Source Commitは必要Event集合を束ね、DB Mirror / Markerは同一Transaction |
| SES-033 | Reassignment中にClose / Createの片方欠落、partial tail、順序違反、Hash mismatch | Operation / Scope QUARANTINED。元Event修復・後続Association更新禁止 |
| SES-034 | 既にClosedのAssociationを再度Close、またはActiveがある状態で別Create | 拒否。Ordinal再利用・二重Active禁止 |
| SES-035 | DB unavailable中に初回ASSIGNEDを試みる | 有効Assignment / Logical Session identity / DB Run / DB Session Mirrorを生成しない。Anonymous Modeの外部Captureのみ |

これらはIssue #210決定の受入ケース案であり、実装・実行・PASSを意味しない。

## 3. MeasurementのDB登録・Current Aggregate判定

| Measurement開始時 | Measurement時Instance | 現在Assignment | 現在Instance | DB Mirror | Current Aggregate |
|---|---|---|---|---|---|
| ASSIGNED | A | ASSIGNED | A | 登録 | 対象候補 |
| ASSIGNED | A | ASSIGNED | B | 登録 | 対象外 |
| ASSIGNED | A | NONE | NULL | 履歴Mirror保持 | 対象外 |
| ASSIGNED | A | ANONYMOUS | NULL | 履歴Mirror保持 | 対象外 |
| NONE | NULL | ASSIGNED | A | 既存DB管理Measurementに限り明示Association可。新規取込・自動Mirror生成禁止。Session membershipは遡及作成しない | 対象外 |
| ANONYMOUS | NULL | ASSIGNED | A | 後日取込・Mirror化・再紐付け禁止 | 対象外 |
| ASSIGNED | B | ASSIGNED | A（B→A再割当後） | 登録 | 対象外 |
| ASSIGNED | A | ASSIGNED | A（A→B→A後） | 登録 | 対象候補 |

「対象候補」は、Measurement Status、Profile Snapshot、RawLog/Artifact整合性、Benchmark Type等の他の受入条件を満たす場合に限る。Current AssignmentがNONE / ANONYMOUSならScope全体を対象外とする。

### 3.1 Scope / Channel独立性

- CH1 / CH2はそれぞれ独立したScope、Measurement、Session、Benchmark入力として扱う。
- CH1とCH2のMeasurementを単一値へ平均化してはならない。
- 両者の関係評価が必要な場合は、独立したPair Analysis Artifactとして、CH1 / CH2それぞれの入力ID・Hash・測定時Assignmentを保持する。
- この表はBattery担当への実装指示ではなく、DB論理設計上の帰属・参照ルール案である。Battery最終契約は統括経由で照合する。

## 4. Receipt状態遷移・クラッシュ回復マトリクス

Receipt EnvelopeはOperationにつき一つの不変記録。Receipt Eventは状態遷移を追記する履歴とし、現在Stateは検証済みEvent Chainから導出する。EnvelopeとEventを同じレコード・同じ意味として扱わない。

| 現在状態 / 停止点 | 必須証拠 | 許される次状態 | 回復動作 |
|---|---|---|---|
| Intentなし | なし | なし | 未実行。Ordinal未消費 |
| Intent書込み中・結果不明 | 部分/不正Journal Tail、Ordinalの発行・消費証拠 | QUARANTINED | Intent完全性を検証できない場合はOrdinalを未消費と推測せず、再利用せず、Physical Runを隔離する。Recovery条件が定義されるまで追加Operationを発行しない |
| Intent永続化後・Receipt Envelope作成前 | 完全なJournal Intent / Intent Hash | PREPARED | 同一OperationからReceipt Envelopeを決定的に再構成・永続化し、PREPARED Eventを追記する。中止要求がある場合も、まずPREPAREDを成立させる |
| PREPARED成立後・Source Commit前の中止 | Intent / Envelope / PREPARED Event / Source Commit不存在証拠 / 明示中止Intent | ABORTED、または証拠不十分時は保留・QUARANTINED | Source Commit不存在を完全検証し、明示中止Intentを記録した場合のみ、同一ReceiptへABORTED Eventを追記する。PREPAREDを経由せずABORTEDにしない |
| PREPARED・Source Commit前 | Intent / PREPARED Envelope + Event | SOURCE_COMMITTED、ABORTED、QUARANTINED | 同一Operationを再開。中止はSource Commit不存在を検証できた場合のみ |
| Source Manifest Commit後・SOURCE_COMMITTED Event前 | Intent / PREPARED / Manifest Head / Source Hash | SOURCE_COMMITTED | Source Commitを検証し、同一ReceiptへSOURCE_COMMITTED Eventを補完 |
| SOURCE_COMMITTED後・DB Commit前 | 上記 + SOURCE_COMMITTED Event | DB_COMMITTED、QUARANTINED | 同一OperationでDB Mirrorを再開 |
| DB transaction中 | Source Commit証拠 / DB Markerの有無 | DB_COMMITTED、SOURCE_COMMITTED継続、QUARANTINED | MarkerのCommit有無を読み戻し、二重Commitを避け同一Operationで再開 |
| DB Marker Commit後・DB_COMMITTED Event前 | Marker / Source Hash / Receipt | DB_COMMITTED | Markerを照合し、同一ReceiptへDB_COMMITTED Eventを補完 |
| DB_COMMITTED後・VERIFIED前 | Journal / Marker / 全依存正本 | VERIFIED、QUARANTINED | 全依存証拠を検証。成功のみVERIFIED |
| ABORTED | 中止Event / Source Commit不存在の証拠 | 終端 | 元Operationの再開・Source Commit禁止。再実行は新Operation |
| VERIFIED | 全検証証拠 | 終端 | 編集・巻戻し禁止 |
| QUARANTINED | 競合・欠落・Hash不一致等 | 終端（元Receipt上） | 元Receiptを編集せず、新Recovery Operationでのみ解決 |

### 4.1 単調遷移規則

- 正常: PREPARED → SOURCE_COMMITTED → DB_COMMITTED → VERIFIED
- Source Commit前の中止: PREPARED → ABORTED
- 各未解決段階から証拠不整合: → QUARANTINED
- SOURCE_COMMITTED以降はABORTED禁止。
- DB_COMMITTED / VERIFIEDからABORTEDへの遷移禁止。
- QUARANTINEDを同一Receipt上で解除・書換えしない。
- Source ManifestのCommit状態が検証不能なら、未Commitと推測してABORTEDにせずQUARANTINED。
- Receipt Event欠落は、先行する正本・Markerを検証できる場合のみ同一Receiptの次Eventを補完する。

## 5. Aggregate Request / Attempt / Result Pointer

### 5.1 Request Fingerprint

Current Valid判定に使うRequest Fingerprintは、少なくとも以下をCanonical順序で含む。

- Request ID
- Scope / DB Run ID
- Input Set Hash
- Assignment Snapshot Set Hash
- Algorithm Version
- Configuration Version
- Measurement / Profile / Policy Revision
- Aggregate Definition Version

Input Set HashのみでRequest同一性を判定しない。

### 5.2 Pointer候補規則

- Latest Requested Request: 受理済みRequestの最大Request Ordinal。
- Latest Successful Revision: 成功Revisionのうち、Request Ordinalが最大のもの。完了時刻だけで旧Requestが新Requestを上書きしない。同一Request内の複数成功はAttempt Ordinal等の明示規則で順序を決める。
- Current Valid Revision: Latest Requested Request IDに属し、そのRequest Fingerprintと完全一致する成功Result Revisionのみ。該当なしはNULL。
- 遅延した旧Requestの成功Resultは履歴として保存するが、Latest Successful / Current ValidのPointerを新しいRequestより後退させない。

### 5.3 Retry終端

Requestは不変。Attemptは実行ごとに新規作成。FAILEDを確定するには、Retryable / Retry Closedの区別と、再試行受付を閉じる明示Eventまたは状態が必要。単に現時点で失敗Attemptしかないことを理由にFAILEDへ確定しない。

## 6. 決定済み処置・受入ゲート

本マトリクスの旧TBD項目はMain §14により設計処置を確定した。下記は設計未決定ではなく、対象外・fail-closed・実証待ちとして扱う。

| 項目 | v0.8.3確定処置 |
|---|---|
| Run Close Actor / UI / Operation | Run ManagerのみがPHYSICAL_RUN_CLOSED Operationを発行。UI・Actor identityはRun Manager契約の値を必須とし、未提供ならClose拒否 |
| Measurement Outcome | Main §14.2の6値。機器固有終端契約がない値はCOMPLETEにせずUNKNOWN / INCOMPLETE |
| DB Run / Session生成 | 初回ASSIGNEDで生成。初回ASSIGNED前のNONE / ANONYMOUSは外部正本のみ |
| Receipt Event Schema | Main §14.4のOrdinal=1 / PreviousHash=NULL、連続Ordinal、JCS-1 / SHA-256。未知EventType拒否 |
| RawLog durability | Main §14.6の全工程を対象OS/filesystemで実証するまでDurable / VERIFIED禁止 |
| UUIDv5 Canonical Name | v0.8.3では不採用。UUIDv4 + M4W-JCS-1を採用 |
| Entity complete fields | 外部正式契約がないFieldは作らない。共通Envelope + opaque payload referenceのみ |
| Legacy IDs / crosswalk | 未回収IDはREFERENCE_ONLY_NOT_EXECUTABLE、根拠のないcrosswalkはNO_MAPPING |
| Motor / Battery | 正式契約外のfield / meaning / durabilityを推測しない。未契約データは意味解析・Aggregate対象外 |

**受入ゲート:** 論理選択は確定。実装・試験実行・OS/filesystem/SQLite実証・他部門契約受領・統括最終審査は別工程であり、未実施をPASSとしない。

## 7. Receipt Event初回・部分Tailの状態組合せ追加

| 現在状態 / Event追記結果 | 必須証拠 | 許される扱い | 禁止事項 |
|---|---|---|---|
| 初回Event未作成 | Envelope / Intent、Event Chainが空であることの完全検証 | 初回Eventの初期Ordinal・Previous Hash表現が正式定義された後に限り作成 | 初期Ordinal・Genesis/NULL表現を推測 |
| Event append未開始 | 対象Ordinalのappend未開始を証明する証拠 | 同じ次Ordinalでappend開始可能 | append開始有無が不明なまま未消費扱い |
| Event append後、完全Eventを読み戻せる | Event Schema / Ordinal / Previous Hash / Event Hash一致 | 既存Eventとして受理し、同じEventを重複追記しない | 重複Event追記 |
| Event append結果不明・部分Tail・Hash不一致 | 完全なEventとして検証できないTail | Receipt Event Chainを隔離。後続Eventを停止 | gapを空けて後続追記、Tail黙示切捨て、Ordinal再利用 |
| Event ChainのWriter競合 | 同じReceiptに対する複数Writerの証拠 | 追加追記停止・隔離 | 最終更新勝ち、時刻順での採用 |
| 元Receiptが隔離済み | 元Receipt / Event Chainの証拠 | Authority定義済みの新Recovery Operationで別Artifactとして検証結果を記録する候補 | 元ReceiptのEvent Chainを無断修復・書換え |

この追加行は論理受入条件の候補であり、Event初期値・Hash Canonicalization・Recovery Authorityを確定しない。


## 8. Manifest競合・後続Commitの復旧受入ケース追加

| Test ID | 条件 | 必須証拠 | 期待扱い |
|---|---|---|---|
| RCP-001 | A/Bが同じExpected predecessorを読んで並行Commitを試行 | A/BのOperation ID、Expected predecessor、Commit Payload、Head更新結果 | 一方のCommit後、他方のstale Commitを拒否。両方を同じpredecessorから成功扱いしない |
| RCP-002 | AのCommit後、応答前に停止。HeadはAのCommit Hash | Aの不変Commit証拠と現Head | AのSource Commitを検証し同一Operationで再開可能 |
| RCP-003 | AのCommit後にCがCommitし、Recovery時HeadはC | AとCのCommit証拠、predecessor連鎖、Head ancestry | AがCの祖先として検証できればAのCommit成立を認定。HeadがAと不一致という理由だけで失敗にしない |
| RCP-004 | Bがstale predecessorを使いCommit前に拒否 | BのExpected predecessorと現Headの不一致証拠 | BのSource Commitは不成立。古いpredecessorを書換えて同一Operationを再利用しない |
| RCP-005 | 同一Operation IDに異なるCommit Payloadが存在 | Operation / Receipt / Commit identity / Payload Hash | QUARANTINED候補。最終更新勝ち禁止 |
| RCP-006 | Manifest Headは存在するがCommit履歴が欠落 | Headと履歴の完全性検証結果 | Source Commit成否を断定せず隔離 |
| RCP-007 | Manifest append / Head更新途中で結果不明 | 部分Tail / Head / Commit証拠 | 後続Commitを停止し、黙示切捨て・Head推測再構築を禁止 |

これらは論理受入試験案であり、実装・実行・PASSを意味しない。Manifest履歴の物理構造やCAS方式は定義しない。


## 9. Manifest後続Commit・Writer交代・Recovery Authorityの受入ケース追加

| Test ID | 条件 | 必須証拠 | 期待扱い |
|---|---|---|---|
| RCP-008 | Operation AがManifest Commit後に停止し、後続Operation CがHeadを進めた | A/CのCommit identity、Expected predecessor、Commit Payload Hash、Head ancestry | AのCommitがCの祖先として検証できればAをSource Committedと認定可能。現Head≠Aだけで不成立としない |
| RCP-009 | A/Bが同じExpected predecessorを使い、両方がCommit成功を主張 | 両OperationのCommit証拠とManifest履歴 | 同一predecessorからの競合Commitを検出し、両方を正当な単一系列として扱わない |
| RCP-010 | Writer AからBへ交代後、Aが古いAuthorityで復帰し更新 | Authority交代証拠、Owner identity / generation等の論理証拠 | 旧Writerの更新を拒否できる証拠が必要。拒否を証明できなければ更新停止・隔離 |
| RCP-011 | Authorityが期限切れに見えるが旧Writerの停止を証明できない | Authority状態・Writer更新履歴 | 時刻だけで旧Writer停止を推定しない。新Writerの有効化を保留 |
| RCP-012 | Recovery要求があるが発行Actor / Scope / 権限が未定義 | Recovery要求と元Receipt / Run証拠 | 元Receipt / Manifestを変更しない。Recovery Operationの発行を保留 |
| RCP-013 | Recovery Operationが元Receipt Event Chainを修復しようとする | 元Receipt不変条件とRecovery Authority定義 | Authority・許可操作が明示承認されるまで修復・追記禁止 |
| RCP-014 | Physical Run lockは単一でも、共有DBで別Runのtransactionが競合 | 各Run AuthorityとDB transaction結果 | Physical Run単一WriterだけでDB全体の排他を推定しない。DB側競合は別途検証 |

これらは未実行の論理受入ケース案である。Authority generation、lease、fencing token、OS lock、CAS、DB isolation等の具体方式を定義・採用しない。


## 10. Decision Baseline追加受入ケース（未実行）

| Test ID | 条件 | 期待結果 |
|---|---|---|
| RCP-015 | Receipt Eventの初回Eventを生成 | Ordinal=1 / PreviousHash=NULL。2件目以降は連続 |
| RCP-016 | Operation Journal Eventに未知EventType | 作成拒否 |
| RCP-017 | Assignment HistoryのRevision / EventOrdinalにgap | Assignment更新拒否・Scope QUARANTINED |
| RCP-018 | Writer GrantのEpochが旧Epoch以下、またはFenceProof欠落 | Writer Grant拒否・Run QUARANTINED |
| RCP-019 | PROJECT_RECOVERY_ADMIN以外がRecovery Operationを要求 | 作成拒否 |
| RCP-020 | Recovery Operationが元Receipt / Manifestを変更またはQUARANTINED解除しようとする | 拒否。元証拠不変・隔離維持 |
| RCP-021 | M4W-JCS-1に浮動小数点・duplicate key・unknown field | Hash対象として拒否 |
| RCP-022 | RawLog orphan tempにIntent / Operation / Expected Hashの対応がない | 削除・上書きせず隔離 |

| RCP-023 | Retry ClosedをAttempt未完了 / RUNNING中 / 完了Attemptなしで要求 | Request Event / Attempt一覧 | Retry Closed拒否。RequestはOPEN維持 |
| RCP-024 | FAILED Attempt後にRetry Closedを明示 | Actor / UTC / Reason / PolicyVersion / 全Attempt終端証拠 | Request State=FAILED。以後Attempt拒否 |
| RCP-025 | RUNNING Attemptの結果がクラッシュ後も不明 | Worker / Attempt / Result証拠 + Worker停止 / fencing proof | proof取得前はAggregate Owner QUARANTINED・全更新停止。proof後はAttempt / Request=INDETERMINATE。Same Request retry禁止。再計算は新Request |
| RCP-026 | RUNNING Attemptがある状態でRequest Cancelled | Request Event / Active Attempt | Cancel拒否。Attemptを先に終端 |
| RCP-027 | 全Attempt終端後にOperatorがRequest Cancelled | 認証Actor / Reason / UTC | Request State=CANCELLED。以後Attempt / Result生成禁止 |
