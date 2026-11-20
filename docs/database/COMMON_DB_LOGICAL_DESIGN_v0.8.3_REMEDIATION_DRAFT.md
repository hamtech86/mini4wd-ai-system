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
2. DB RunはPhysical Runにつき最大1件。Physical Run IDとは別のUUIDv5を持つ。
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
6. Sessionに所属するMeasurement集合は、Session生成後にDBへ登録されたMeasurement Mirrorの集合であり、各Measurementの測定時Assignmentを必ず保持する。後日ASSIGNEDとなった際、既存Measurement IDを維持した明示的なAssociation Operationで過去MeasurementをDB Mirrorへ登録してよい。登録は測定時Assignmentを書き換えず、NONE / ANONYMOUS測定を遡及的にASSIGNED扱いしない。ANONYMOUS期間のデータは自動取込せず、ユーザーが明示的に関連付けを指示した場合のみ処理する。

### 1.3 Assignment遷移

| Before | After | Session / DB Run | 新規Measurementの取扱い |
|---|---|---|---|
| 初期NONE | NONE | 生成しない | 外部正本のみ |
| 初期ANONYMOUS | ANONYMOUS | 生成しない | 外部正本のみ |
| 初期NONE/ANONYMOUS | ASSIGNED | DB RunとSessionを生成 | 開始時点以降のASSIGNED測定をDB Mirrorへ登録 |
| ASSIGNED | ASSIGNED（同一Instance） | 維持 | 測定時Assignment Revisionを記録 |
| ASSIGNED | ASSIGNED（別Instance） | 維持 | 過去測定の帰属は変更しない |
| ASSIGNED | NONE | 維持・非アクティブ | NONE期間の測定は外部正本のみ |
| ASSIGNED | ANONYMOUS | 維持・制限状態 | ANONYMOUS期間の測定は外部正本のみ |
| NONE/ANONYMOUS（過去ASSIGNEDあり） | ASSIGNED | 既存IDを再利用 | 新規測定のみ現在のAssignmentに従う |

ANONYMOUSは「その期間の測定をInstanceに帰属させない」状態であり、過去にASSIGNEDだった期間の履歴を自動消去・書換えする命令ではない。過去データの消去・匿名化要求はAssignment変更と分離した、別の明示的なプライバシー処理として扱う。通常のAssignment Operationで既存Session・Measurement・Historyを削除しない。

### 1.4 Session Status / Aggregate対象

1. Session StatusはHistorical SessionのMeasurement集合から導出する。Current AssignmentがNONE / ANONYMOUSでも、Session自体が存在する場合は履歴状態として導出可能。
2. **Current Aggregate**の対象は、現在ASSIGNEDであるScopeのうち、Measurement開始時点もASSIGNEDで、かつ測定時Instance IDが現在Instance IDと一致するMeasurementだけとする。
3. NONE / ANONYMOUS期間に開始したMeasurementは、後日ASSIGNEDになってもCurrent Aggregateへ遡及追加しない。既存Measurement IDをDB Mirrorへ明示登録する場合も、測定時AssignmentとInstance IDは不変であり、Current Aggregateの対象外とする。
4. 過去に別InstanceへASSIGNEDだったMeasurementは、再割当後のInstanceのCurrent Aggregateへ混入させない。
5. Current AssignmentがNONE / ANONYMOUSのScopeはCurrent Aggregate対象外。除外理由、Current Assignment Revision / State / HashをAggregate Requestに固定する。
6. 過去Assignmentの測定結果を分析する場合は、Current Aggregateとは別の明示的なHistorical Analysis Artifactを生成する。Pair Analysisも入力Measurementの時点帰属を維持し、CH1/CH2を平均化しない。

## 2. DB-RV-03 — Operation / Journal / Receiptの厳密な順序

### 2.1 正規順序

1. Physical Run単位の排他ロックを取得し、Journalと直近Ordinalを検証。
2. Operation ID / Ordinal / Intent Payload / Intent Hashを確定。
3. Journal Intentを追記し、ファイル本体を永続化する。Intent永続化完了時にOrdinalを消費済みとする。
4. Receipt本体を`PREPARED`として外部正本へ作成する。Receipt IDはOperation IDから決定的に導出。ReceiptにはOperation ID / Ordinal / Intent Hash / Expected DB Marker Hash /対象Entity ID / Canonicalization Versionを含める。
5. Receipt本体・親ディレクトリを永続化し、Receipt PREPARED Eventを追記・永続化する。
6. DB transactionを開始し、対象DB Mirror変更とOperation Markerを同一transactionでCommitする。MarkerにはOperation ID / Ordinal / Intent Hash / Receipt ID / Commit Payload Hashを含める。
7. Commit結果を読み戻し、MarkerとJournal Intent / Receipt PREPAREDのHashを照合する。
8. Receipt Event `DB_COMMITTED`を外部正本へ追記・永続化する。
9. Journal / Marker / Receipt / 関連外部正本を再検証する。
10. Receipt Event `VERIFIED`を追記・永続化する。
11. すべての永続化・照合が成功した後に排他ロックを解放する。

Journal IntentとReceipt PREPAREDは別の証拠であり、同一視しない。PREPAREDはDB Commitより前に外部正本として永続化される。

### 2.2 Receipt State

- PREPARED: Intentが永続化され、DB Commit前の証拠が存在する。
- DB_COMMITTED: DB Markerが同一TransactionでCommitされ、読み戻し照合済み。
- VERIFIED: 関連Hash・外部正本・Markerの整合性が確認済み。
- ABORTED: DB Commitが存在しないことを確認し、明示的中止Eventを永続化済み。
- QUARANTINED: 証拠欠落・競合・Hash不一致等で自動判定不能。自動復帰禁止。

Stateは単調遷移とし、PREPAREDからABORTEDへ進む場合はDB Markerが存在しないことを確認する。DB_COMMITTED後にABORTEDへ戻してはならない。VERIFIEDは終端状態。QUARANTINEDは隔離状態であり、元Receiptを編集しない。解決操作は新しいRecovery Operationとして記録する。

### 2.3 クラッシュ復旧表

| 停止点 | 再起動後の根拠 | 許可される処理 |
|---|---|---|
| Journal Intent前 | 永続証拠なし | 未実行として扱う。Ordinal未消費 |
| Intent後、Receipt PREPARED前 | Journal Intent | 同一Operation ID / OrdinalでReceipt PREPAREDを作成、またはABORTEDを記録 |
| PREPARED後、DB transaction前 | Journal + PREPARED | 同一Operationを再開、またはMarker不存在確認後ABORTED |
| DB transaction中 | Journal + PREPARED + DB Marker有無 | MarkerのCommit有無を読み戻し、同一Operationで再開 |
| DB Commit後、DB_COMMITTED Event前 | DB Marker + PREPARED | Hash一致を確認してDB_COMMITTED Eventを補完 |
| DB_COMMITTED後、VERIFIED前 | Marker + Journal + Receipt | 全依存正本を検証しVERIFIED、またはQUARANTINED |
| Hash / ID / Ordinal競合 | 不一致証拠 | QUARANTINED。推測修復・別Operationへの付替え禁止 |

同一Operation IDでIntent Hashが異なる再実行は即時QUARANTINED。Ordinalは欠番を許容し再利用しない。Receipt EventはEvent Ordinal単調増加・Hash Chainで保全する。

## 3. DB-RV-04 — Aggregate Request / Attempt / Result Revision

### 3.1 3つの異なる概念

- **Aggregate Request**: 再計算要求の不変記録。Request ID、Request Ordinal、Input Set Hash、Assignment Snapshot Set Hash、Requested At、Reason、Algorithm / Configuration Versionを保持。
- **Aggregate Attempt**: Requestを実行した試行。Attempt ID、Started At、Finished At、Attempt Status、Failure Code / Detail、Worker / Algorithm Versionを保持。再試行ごとに新Attempt ID。
- **Aggregate Result Revision**: 成功したAttemptのみが生成する不変結果。Revision ID、Request ID、Attempt ID、Input Set Hash、Result Hash、Result Payload Reference、Completed Atを保持。

RequestやAttemptの失敗を成功Revisionとして採番しない。失敗したRequest / Attemptも削除・上書きしない。

### 3.2 Pointer定義

- Latest Requested Request: 最後に受理したAggregate Request。
- Latest Successful Revision: 最も新しい成功Result Revision。履歴参照用。
- Current Valid Revision: Latest Requested RequestのInput Set Hashと一致する成功Revision。無い場合NULL。
- Recalculation State:
  - CLEAN: Current Valid RevisionがLatest Requested Requestの入力Hashと一致。
  - DIRTY: 入力が変化したが、まだ新Requestが受理されていない。
  - RUNNING: Latest Requested Requestに実行中Attemptがある。
  - FAILED: Latest Requested Requestの全Attemptが失敗し、成功Resultがない。

### 3.3 状態遷移

1. 入力変更時: Current Valid=NULL、State=DIRTY。Latest Successfulは履歴として維持。
2. Request受理時: Requestを不変保存しLatest Requested Requestを更新。Current Valid=NULL、State=DIRTY。
3. Attempt開始時: Attemptを新規作成しRUNNING。
4. Attempt成功時: Result Revisionを新規作成。Input Set Hashが現在の最新要求・入力と一致する場合に限りLatest Successful / Current Validを更新しCLEAN。
5. Attempt失敗時: Failure情報をAttemptへ不変保存。Requestに未実行/再試行可能Attemptが残る場合は要求中状態を維持し、すべて失敗し再試行を終了した時点でFAILED。Current ValidはNULLのまま。
6. 失敗後の再試行: 同じRequestに新Attemptを追加する。入力条件を変更した再計算は新Requestとする。
7. 遅延した古いRequestの成功結果はResult Revisionとして保存できるが、Latest Requested RequestのInput Set Hashと不一致ならCurrent Validへ昇格させない。

Latest Requested Revisionという曖昧なPointer名は廃止し、Latest Requested Requestへ置換する。

## 4. DB-RV-05 — Artifact Input DAG / 再解析不変性

1. Analysis Artifact / Simulation Artifactは作成後不変。再解析・Algorithm更新・Configuration更新・入力変更は必ず新Artifact IDを発行する。
2. Artifact InputがANALYSIS_ARTIFACT / SIMULATION_ARTIFACTを参照する場合、入力Artifactは参照先が確定済みでHash検証済みの既存Artifactでなければならない。
3. Artifactは自分自身を入力にできない。新Artifactから既存Artifactへの参照のみ許可し、作成時に依存グラフを走査して循環を拒否する。
4. Input Set HashはInput Type / Reference ID / Input Hash / Role / Ordinal / Required / Source Revisionの順序固定Canonical列から生成する。
5. 同じInput Set / Algorithm / Configurationを再実行しても、実行ごとに新Artifact IDを発行する。内容Hashが同じなら同一内容であることを示すが、旧Artifactを上書き・再利用しない。
6. 参照先Artifactが欠落・Hash不一致・未確定の場合、生成を中止し、依存ArtifactをQUARANTINED扱いにする。入力の推測補完は禁止。
7. 削除は禁止。不要化はLifecycle / Superseded参照等の追記で表現する。

## 5. DB-RV-06 — UUIDv5 Canonicalization v2提案

### 5.1 v1の扱い

v0.8.2 §9.3の区切り文字連結形式は、NULL・空文字・区切り文字・エスケープの一意性が証明されていないため、実装採用しない。v1 Nameを生成済みIDの正本として扱う証拠が見つかった場合は互換性を別途審査し、黙って再採番しない。

### 5.2 Canonical Binary Name v2

NameはUTF-8文字列連結ではなく、次のバイナリ文法とする。UUIDv5のNameバイト列へこのバイト列をそのまま渡す。

- Header: ASCII bytes `M4ID` + NUL + ASCII `2`。
- Entity Type: ASCII大文字。2-byte unsigned big-endian length + bytes。
- Field Count: 2-byte unsigned big-endian integer。
- 各Fieldは固定順。Fieldごとに1-byte Type Tag + 4-byte unsigned big-endian payload length + payload。
- NULL: Type Tag `0x00`, length 0。
- UTF-8 string: Type Tag `0x01`, Unicode NFC後のUTF-8 bytes。
- UUID: Type Tag `0x02`, RFC 4122 16-byte network order。
- Integer: Type Tag `0x03`, ASCII canonical decimal。0は`0`、負数は先頭`-`、先頭ゼロ・`+`は禁止。
- Timestamp: Type Tag `0x04`, UTC Unix epoch nanosecondsを符号付き64-bit big-endian整数で表現。入力精度はnanosecond以下を拒否。UTC変換後に符号化。
- Boolean: Type Tag `0x05`, false=`0x00`、true=`0x01`。
- Byte String: Type Tag `0x06`, bytesそのもの。

空文字列はType Tag `0x01` / length 0であり、NULLとは異なる。値中の区切り文字・パーセント・NULはUTF-8 payload内の通常byteであり、エスケープしない。各Fieldの長さと型で境界を決めるため、連結衝突を生じない。Field順・型・Entity TypeをCanonicalization Versionに固定する。

UUIDv5生成はRFC 9562のSHA-1ベースUUIDv5手順を使用し、Namespace 16 bytes + Name bytesを入力とする。候補Namespace `8f4c2d91-6a73-4e5b-9c20-31d7a8b5e642`は**未承認・未採用**。既存Repo全履歴・全ブランチ・全ファイル・Issue/PR・過去ID生成資産での利用有無を調査し、統括承認後に限り採用する。

### 5.3 Entity Field Schema（論理順）

| Entity | Canonical fields (fixed order) |
|---|---|
| DB_RUN | PhysicalRunID(UUID) |
| RUN_SCOPE | PhysicalRunID(UUID), ScopeKey(ASCII string) |
| SESSION | PhysicalRunID(UUID), ScopeKey(ASCII string) |
| OPERATION_EVENT | OperationID(UUID), EventOrdinal(Integer) |
| RECEIPT | OperationID(UUID) |
| RECEIPT_EVENT | ReceiptID(UUID), EventOrdinal(Integer) |
| RAWLOG_REFERENCE | PhysicalRunID(UUID), ScopeKey(ASCII string), LogID(UTF-8 string) |
| SAMPLE_REFERENCE | RawLogReferenceID(UUID), SampleLocator(UTF-8 string) |
| MEASUREMENT_SAMPLE_LINK | MeasurementID(UUID), SampleReferenceID(UUID), Role(UTF-8 string), Ordinal(Integer) |
| ARTIFACT_INPUT | ArtifactID(UUID), InputType(UTF-8 string), InputReferenceID(UUID), Role(UTF-8 string), Ordinal(Integer) |
| AGGREGATE_RESULT_REVISION | DBRunID(UUID), Revision(Integer) |

### 5.4 必須テストベクトルの形式

Namespace承認前に、実UUIDを正解値として固定しない。Canonical byte列のgolden vectorを先に固定し、Namespace承認後にUUID期待値を追加する。各Entityについて最低限、通常値、NULL、空文字、区切り文字、`%`、NUL、Unicode NFC/NFD同値、負数/0/正数、Timestamp epoch/負値/最大精度、UUID byte orderを含める。

Collision pairは必ず異なるCanonical byte列となることを確認する。Unicode NFC/NFDの同値入力は正規化後に同じbyte列となることを確認する。Namespaceが未承認の間はUUIDv5の実装合格を宣言しない。

### 5.5 Canonical byte golden vectors（Namespace非依存）

以下はEntity SchemaとCanonical Binary Name v2のbyte列自体を固定するテストベクトルである。Hexは大文字表記。UUID期待値はNamespace未承認のため未設定。

| Case | 入力 | Expected Name Bytes (hex) |
|---|---|---|
| DB_RUN | PhysicalRunID = 00000000-0000-4000-8000-000000000001 | `4D3449440032000644425F52554E0001020000001000000000000040008000000000000001` |
| RUN_SCOPE | 同UUID + ScopeKey = BATTERY:CH1 | `4D3449440032000952554E5F53434F50450002020000001000000000000040008000000000000001010000000B424154544552593A434831` |
| NULL | TEST_VALUE / field=NULL | `4D3449440032000A544553545F56414C554500010000000000` |
| EMPTY | TEST_VALUE / field=empty UTF-8 string | `4D3449440032000A544553545F56414C554500010100000000` |
| DELIMITER_PERCENT_NUL | TEST_VALUE / field bytes for UTF-8 string `A|B%\0C` | `4D3449440032000A544553545F56414C554500010100000006417C42250043` |
| NFC | TEST_VALUE / field = U+00E9 | `4D3449440032000A544553545F56414C554500010100000002C3A9` |
| NFD input | TEST_VALUE / field = U+0065 U+0301, normalized NFC | `4D3449440032000A544553545F56414C554500010100000002C3A9` |

検証条件:
- NULLとEMPTYのbyte列は異なる。
- `A|B%\0C`は値内の区切り・パーセント・NULを含むが、長さ付きpayloadとして一意に復号できる。
- NFCとNFD入力はNFC正規化後に同一byte列となる。
- 上記hexは実装テストで完全一致を要求する。EntityごとのField Schemaと異なる型Tag / Field Count / Lengthは拒否する。

## 6. DB-RV-07 — 外部正本 / DB Mirrorマトリクス

| Entity / Record | 正本 | DB Mirror | 作成・再生成条件 |
|---|---|---|---|
| Physical Run | Run Manifest | DB Run生成後に任意の検索Mirror | Manifestから復元。ID再発行禁止 |
| RUN_SCOPE | Scope Manifest / Assignment Snapshot | DB Run生成後、Physical Run内の全ScopeをMirror可能 | 外部Scope一覧から再生成 |
| Assignment Snapshot / History | Scope単位の不変ファイル | あり（Mirrorのみ） | Hash Chain検証後に再生成 |
| Measurement | Measurement Envelope | 測定時ASSIGNEDのMeasurementを登録。後日ASSIGNED時は明示的Association Operationで既存Measurement IDを登録可能。ANONYMOUSデータは自動取込しない | Envelopeから再生成。測定時Assignmentを変更しない。遅延登録のOperation ID / Actor Intent / Source Assignment Revisionを記録 |
| Measurement Profile Snapshot | Measurement Envelopeが参照する不変Snapshot | あり（Mirrorのみ） | Snapshot Hash検証後に再生成 |
| RawLog / Sample Reference | RawLog本体 / Reference Manifest | 参照Mirrorのみ | 本文Hash一致を検証して再生成 |
| Analysis / Simulation Artifact | Artifact Envelope / Result Payload | 参照・検索Mirror | DAGと入力Hash検証後に再生成 |
| Operation Journal | Physical Run Journal | Marker / Journal Mirror | Journal正本から再生成 |
| Receipt / Receipt Event | Receipt Envelope / Event Log | あり（Mirrorのみ） | 依存証拠の二段階検証後に再生成 |
| Aggregate Request / Attempt / Result | Aggregate Envelope / Result Payload | Pointer / 検索Mirror | Request/Attempt/ResultのHash検証後に再生成 |

全Anonymous / NONEで一度もASSIGNEDがない場合、Physical Run / RUN_SCOPE / Assignment Snapshot / Measurement Envelope / RawLog / Artifact等は外部正本だけで再構築可能とする。DB Run / Session / DB Mirrorを作らない。後日初回ASSIGNEDでDB Runを生成した後は、必要な全ScopeのManifestとSnapshotをMirrorする。既存Measurementのうち、NONE期間のものは既存Measurement IDを維持した明示的Association OperationでDB Measurement Mirrorへ登録できる。ANONYMOUS期間のものは自動登録せず、明示的な関連付け指示を必要とする。いずれもAssignment-at-Measurementを変更せず、Current Aggregateへ遡及包含しない。

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

V082-001〜030は既存のまま保持する。V082-031〜050は追加案であり、統括承認・試験実装・実行前はPASS扱いしない。

## 12. 未解決・別途証拠が必要な項目

- DB-001〜124の全124 ID個別原文・正式出典・現行有効性・実装テスト対応。範囲履歴は維持し、未回収本文は創作しない。
- V082-001〜050とDB-001〜124のクロスウォーク。
- Issue #35のMotor接続・制御・RawLog契約との正式照合。DB設計でIssue #35を上書きしない。
- Issue #201の匿名運用は旧DB復旧・自動DB取込を許可する根拠ではない。本設計での後日Associationは新DBの将来機能として明示的操作に限定し、旧DB復旧・既存ログの自動再取込とは分離する。
- Batteryの最終測定 / RawLog契約。CH1 / CH2独立Measurement・独立Benchmark・平均化禁止・Pair Analysis別Artifactを維持。Battery実装変更はDB部門の範囲外。
- UUID Namespace既存利用調査と統括承認。Canonical Binary Name v2の実装テストベクトルはNamespace承認後にUUID期待値を付与。
- 全Entityの完全属性表（型・NULL・UNIQUE・CHECK・複合FK）。本書の最低論理制約と物理方式の未確定を分離する。
- Backup / Restore / Bootstrapの実装試験。論理受入条件の定義と実装試験合格を混同しない。

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
