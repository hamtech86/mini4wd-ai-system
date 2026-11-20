# v0.8.3 状態遷移・集約判定マトリクス（検証用ドラフト）

- 基準日: 2026-11-21
- 対象: v0.8.3 remediation draft
- 状態: 検証用補助資料・未承認
- 目的: Assignment / DB Run / Session / Measurement / Aggregate / Receiptの状態組合せを列挙し、本文の曖昧さを検出する。
- 本書は新たな仕様承認ではない。Issue #201の現行範囲を越える後日Association・Bootstrapは含めない。

## 1. 前提と範囲境界

1. Physical Run IDは外部正本上の識別子。DB Run IDとは別ID。
2. DB Runは、利用承認済みで既に存在するDBが正常利用可能な場合に限り、Physical Run内で最初の確定ASSIGNED Operationに伴うMirror recordとして作成する。
3. この作成規則はDB file / schema / empty DB / migration / Bootstrapの生成許可ではない。
4. SessionはScopeごとに最大1件。最初の確定ASSIGNED Operationで生成し、以後NONE / ANONYMOUS / 別Instanceへの遷移でも履歴IDを保持する。
5. ANONYMOUS期間のMeasurement / RawLogは外部正本に保全し、現行設計では後日DB取込・Mirror化・Instance再紐付けを禁止する。NONE期間は別扱いとし、DB利用可能時に取得され外部正本とDB管理下のMeasurement記録が既に存在する場合に限り、後日の明示Association Operationを許容する。自動取込は禁止し、Assignment-at-MeasurementはNONEのまま保持し、Current Aggregateへ自動算入しない。
6. MeasurementのAssignment-at-Measurementは開始確定時の不変Snapshotであり、Current Assignmentの変更で更新しない。

## 2. Assignment / DB Run / Session状態遷移

| 遷移 | DB Run | 対象Scope Session | Measurement保存・登録 | Current Aggregate |
|---|---|---|---|---|
| 初期 → NONE | なし | なし | 外部正本のみ | 対象外 |
| 初期 → ANONYMOUS | なし | なし | 外部正本のみ | 対象外 |
| NONE → ASSIGNED(A) | なければ作成 | なければ作成 | 以後のASSIGNED測定をMirror登録 | A測定のみ候補 |
| ANONYMOUS → ASSIGNED(A) | なければ作成 | なければ作成 | 以後のASSIGNED測定をMirror登録。過去ANONYMOUSデータは取込禁止 | A測定のみ候補 |
| ASSIGNED(A) → ASSIGNED(A) | 保持 | 保持 | 測定時Revisionを固定 | A測定のみ候補 |
| ASSIGNED(A) → ASSIGNED(B) | 保持 | 保持 | 新規測定はB。A測定の帰属は不変 | B測定のみ候補 |
| ASSIGNED(A) → NONE | 保持 | 保持・非アクティブ | NONE期間の新規測定はAssignment=NONEを固定。既にDB管理下にあるMeasurementのみ後日明示Association対象になり得る。自動Mirror生成・RawLog取込は禁止 | 対象外 |
| ASSIGNED(A) → ANONYMOUS | 保持 | 保持・非アクティブ | ANONYMOUS期間は外部正本のみ。後日DB取込・Mirror化・Instance再紐付け禁止 | 対象外 |
| 過去ASSIGNEDあり NONE → ASSIGNED(A) | 同一IDを保持 | 同一IDを保持 | 新規A測定をMirror登録。NONE期間の既存DB管理Measurementは明示Associationのみ可。測定時Assignment=NONEを維持 | A測定のみ候補。NONE由来は対象外 |
| 過去ASSIGNEDあり ANONYMOUS → ASSIGNED(A) | 同一IDを保持 | 同一IDを保持 | 新規A測定のみMirror登録。過去ANONYMOUSデータは後日取込・Mirror化・再紐付け禁止 | A測定のみ候補 |

補足:
- Physical Run内で別Scopeが後日初めてASSIGNEDになった場合、DB Runは既存IDを使い、そのScopeだけSessionを新規生成する。
- 一つのPhysical Run内で全ScopeがNONE / ANONYMOUSになっても、既に生成済みDB Run / Sessionを削除しない。
- Sessionが存在することは現在ASSIGNEDであることを意味しない。
- Assignmentの変更は既存Measurement / RawLog / Artifactの削除・書換えを行わない。
- NONEの後日Associationは、既存DB管理Measurementに対する明示操作に限定し、実行主体・時刻・変更前後・理由を監査履歴へ残す。Assignment-at-MeasurementはNONEのまま不変。
- ANONYMOUSは現行設計範囲で後日DB取込・Mirror化・Instance再紐付けを禁止する。将来拡張には別設計と統括承認を要する。
- Anonymous化・消去要求はAssignment遷移とは別の明示的プライバシー処理。通常のAssignment Operationで履歴を消去しない。

## 3. MeasurementのDB登録・Current Aggregate判定

| Measurement開始時 | Measurement時Instance | 現在Assignment | 現在Instance | DB Mirror | Current Aggregate |
|---|---|---|---|---|---|
| ASSIGNED | A | ASSIGNED | A | 登録 | 対象候補 |
| ASSIGNED | A | ASSIGNED | B | 登録 | 対象外 |
| ASSIGNED | A | NONE | NULL | 履歴Mirror保持 | 対象外 |
| ASSIGNED | A | ANONYMOUS | NULL | 履歴Mirror保持 | 対象外 |
| NONE | NULL | ASSIGNED | A | 既存DB管理Measurementに限り明示Association可。新規取込・自動Mirror生成禁止 | 対象外 |
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
| Intent永続化後・Receipt Envelope作成前 | Journal Intent / Intent Hash | PREPARED、または中止時ABORTED | 同一Operationから決定的Receipt Envelopeを再構成。ABORTEDならEnvelope作成後にABORTED Eventを追記 |
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

## 6. 未確定・未完了のまま残す事項

- Session Statusの具体的導出規則（Measurement Statusの組合せ、STOP / ERROR / CANCEL / INCOMPLETEの優先順位）。
- DB Run / Session生成時のOperation境界と、既存DB利用不可時の外部正本のみの扱いの詳細。
- Receipt Eventの実際のEvent Type / Payload / Hash Chain Canonical Schema。
- RawLog種別ごとのdurability / loss tolerance。Issue #35との照合が必要。
- Canonical Binary Name v2の全Entity Field Schemaと完全なbyte vectors。
- 全Entityの属性・型・NULL・キー・複合FK・多態参照・削除/更新規則。
- DB-001〜124の個別原文・V082 crosswalk。
- Motor正式DB要件の照合。
- Battery最終測定/RawLog契約の統括経由照合。

**結論:** 本マトリクスは状態組合せの検査台帳であり、v0.8.3の修正完了・統括承認・実装許可を意味しない。
