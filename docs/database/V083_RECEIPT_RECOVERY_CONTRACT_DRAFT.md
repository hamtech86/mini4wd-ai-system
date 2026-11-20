# v0.8.3 Receipt / Journal Recovery Contract 詳細案

- 基準日: 2026-11-21
- 状態: 論理設計補助案・未承認
- 関連: v0.8.3 §2 / §6 / §9、V083_STATE_TRANSITION_MATRIX_DRAFT.md、Issue #201 / #35 / #85 / #86
- 目的: Receipt Eventの意味、Journal Intentの再構成可能性、クラッシュ点ごとの再開・中止・隔離条件を明確化する。
- 本書は物理DB、DDL、実装、DB生成、Migration、Bootstrapを許可しない。

## 1. 用語の分離

| 概念 | 役割 | 不変性 |
|---|---|---|
| Journal Intent | 何を行うOperationかを事前に固定する外部正本 | 追記後不変 |
| Receipt Envelope | Operationの期待証拠・対象・Hashを束ねる外部正本 | 作成後不変 |
| Receipt Event | Receiptの進行・終端判断を記録する追記Event | 追記のみ |
| Source Commit | 外部正本の新Revision / Manifest Headを確定する操作 | Commit後巻戻し禁止 |
| DB Marker | DB Mirrorへの同一Operation適用を証明する記録 | DB transaction内で不変作成 |
| Recovery Operation | 元Operationを編集せず、未解決状態を検証・解決する新Operation | 新ID / 新Ordinal |

Receipt EnvelopeはStateをUPDATEして使い回す mutable rowではない。現在Stateは、Envelopeと検証済みReceipt Event Chainから導出する。DB MirrorのReceiptコピーは外部正本を代替しない。

## 2. Journal Intentの再構成可能性

v0.8.3 §2.1ではIntent永続化後・Receipt作成前のクラッシュ時にReceiptを再作成するとしている。しかし現行列挙のIntent Hash / Intent Payloadだけでは、ReceiptのExpected Source Payload HashesやExpected DB Marker Hashを再構成できない場合がある。

**提案: Journal Intentは、Receipt Envelopeを一意に再構成できる完全なOperation Planを含む。**

最低限のIntent Plan:
- Physical Run ID / Operation ID / Operation Ordinal
- Operation Type / Target Entity Type / Target Entity ID
- Actor / Initiator / Explicit Intent Reference
- Canonicalization Version / Payload Schema Version
- Expected source object IDs / immutable revision IDs
- Expected Source Payload Hashes / planned Manifest Head Hash
- Expected DB Marker Payload Schema / Expected DB Marker Hash
- Receipt ID（Operation IDから決定的導出）
- Operation Plan Hash / Intent Hash
- Created At（参考値。Ordinal順序の代用にしない）

Operation PlanはIntentを追記する前に完全に確定する。Intentを永続化した後は内容を編集しない。ReceiptはIntent Planから決定的に再構成できなければならない。

Receipt作成前のクラッシュ時:
1. Journal Intentが完全・Hash一致で存在するなら、同じOperation ID / Ordinal / Intent HashからReceipt Envelopeを再構成する。
2. 再構成したReceipt EnvelopeのHashがIntentに固定したExpected Receipt Hashと一致することを確認する。
3. 自動的に中止せず、通常は同一OperationをPREPAREDから再開する。
4. ユーザー/Operatorが中止を明示した場合のみ、Source Commit不存在を検証してABORTEDを追記する。
5. Intentが部分書込み・Hash不一致・Ordinal競合で完全に検証できない場合、Ordinalを再利用せずPhysical RunをQUARANTINEDにする。別Operationとして同じOrdinalを再発行しない。

## 3. Receipt Envelope / Eventの最小論理Schema

### 3.1 Receipt Envelope（immutable）

| Attribute | Required | Rule |
|---|---|---|
| Receipt ID | Yes | Operation IDから決定的導出 |
| Physical Run ID | Yes | Journal Intentと一致 |
| Operation ID / Ordinal | Yes | Journal Intentと一致、Ordinal再利用禁止 |
| Intent Hash / Plan Hash | Yes | Journal IntentのHashと一致 |
| Expected Source Payload Hashes | Yes | 対象Revisionごとに固定 |
| Expected Source Manifest Head | Yes | Commit対象Head / predecessorを固定 |
| Expected DB Marker Hash | Yes | DB Mirror transactionの期待Markerを固定 |
| Canonicalization Version | Yes | Hash計算時点のversion固定 |
| Envelope Schema Version | Yes | parse/version validation用 |
| Created At | Yes | 参考時刻。順序決定にはOrdinal使用 |
| Envelope Hash | Yes | Canonical serializationによる自己Hash |

Receipt EnvelopeにCurrent Stateを書き換え可能な属性として持たせない。StateはEvent Chainから導出する。

### 3.2 Receipt Event（append-only）

| Attribute | Required | Rule |
|---|---|---|
| Receipt ID | Yes | Envelopeを参照 |
| Event Ordinal | Yes | Receipt内で単調増加、再利用禁止 |
| Event Type | Yes | PREPARED / SOURCE_COMMITTED / DB_COMMITTED / VERIFIED / ABORTED / QUARANTINED |
| Previous Event Hash | Yes except first | 直前Event Hashと一致 |
| Event Payload | Yes | Event TypeごとのCanonical Schema |
| Event At | Yes | 参考時刻。Ordinal順序が正 |
| Actor / Recovery Operation ID | Conditional | 人手判断・Recovery時は必須 |
| Event Hash | Yes | Canonical Event serializationのHash |

Event TypeとPayloadの許可組合せを固定し、未定義Event Type / 余分なPayload field / 必須field欠落 / Event Ordinal gap / Hash Chain不一致は検証失敗とする。未知Event Typeを無視して後続Eventを受理しない。

## 4. Receipt Event遷移表

| Current State | Event | 次State | 許可条件 |
|---|---|---|---|
| 未作成 | PREPARED | PREPARED | 完全なJournal IntentからEnvelopeを作成し、Source Commit前に永続化 |
| PREPARED | SOURCE_COMMITTED | SOURCE_COMMITTED | Manifest Head / Source Payload Hash / predecessorを読み戻して検証 |
| PREPARED | ABORTED | ABORTED | Source Commit不存在を完全に検証し、明示中止Intentを記録 |
| PREPARED | QUARANTINED | QUARANTINED | Source/Intent/Manifest証拠の不一致または検証不能 |
| SOURCE_COMMITTED | DB_COMMITTED | DB_COMMITTED | DB Markerが同一transactionでcommit済み、読み戻しHash一致 |
| SOURCE_COMMITTED | QUARANTINED | QUARANTINED | Source正本競合、Operation/Marker ID競合、Hash不一致 |
| DB_COMMITTED | VERIFIED | VERIFIED | Journal / Source / Marker / 全依存Hashを再検証 |
| DB_COMMITTED | QUARANTINED | QUARANTINED | 再検証時の証拠不一致 |
| VERIFIED | 任意の遷移Event | 拒否 | 終端・不変 |
| ABORTED | 任意の遷移Event | 拒否 | 終端・不変 |
| QUARANTINED | 元Receipt上の解除Event | 拒否 | 元Receiptは不変。解決は新Recovery Operation |

PREPAREDからSOURCE_COMMITTEDへ直接進む場合、Source Commitが既に発生していた証拠を読み戻して検証する。PREPAREDからABORTEDへ進めるのはSource Commit前に限る。SOURCE_COMMITTED以後はABORTEDを許さない。

## 5. Source Commit不存在の証明

ABORTEDは「Source Commitが見つからなかった」という単純な検索結果では許可しない。

必要な条件:
1. Journal IntentのExpected Source Manifest Head / predecessorを検証できる。
2. 対象Physical RunのManifest / Commit Chainが連続し、対象OperationのSource Commitが存在しないことを検証できる。
3. 対象OperationがSource Commitを開始した形跡（Commit marker、atomic head switch、commit record等）が存在しない。
4. Source正本の一部欠落、Hash不一致、Manifest Head競合、保存先不明などがない。
5. Operator中止の場合は明示中止Intent / Actor / timestampを記録する。

いずれかを満たさない場合、ABORTEDにせず、証拠が単に未到着なら保留、競合・検証不能ならQUARANTINEDとする。保留状態を成功・中止に読み替えない。

## 6. クラッシュ点ごとの再開規則

| Crash point | 正本証拠 | 再起動後の状態 / 動作 |
|---|---|---|
| Operation Plan確定前 | 永続Intentなし | 未実行。Ordinal未消費 |
| Intent書込み中 | 部分/不正Journal可能性 | Journalを検証。完全でなければQUARANTINED。Ordinal再利用なし |
| Intent永続化後、Receipt Envelope前 | 完全Intent | 同一IntentからReceiptを決定的再構成しPREPARED |
| Envelope永続化後、PREPARED Event前 | Envelope + Intent | Envelope Hash検証後、同じReceiptへPREPARED Eventを補完 |
| PREPARED後、Source write前 | Intent + Envelope + PREPARED | 同一Operation再開、または明示中止を検証後ABORTED |
| Source revision書込み中、Manifest Head更新前 | 一時/未参照Revision | Commit未確定を検証。既存正本を上書きせず、同一Operationで再開または安全な中止 |
| Manifest Head更新中 / 結果不明 | Head / Commit Chainが曖昧 | ABORTED禁止。Headを再読込。検証不能ならQUARANTINED |
| Source Commit後、SOURCE_COMMITTED Event前 | Manifest Head / Source Hash | Source Commitを検証し、同一ReceiptにSOURCE_COMMITTED Eventを補完 |
| SOURCE_COMMITTED後、DB transaction前 | Source Commit + Event | 同一OperationでDB Mirror transactionを開始 |
| DB transaction中 | DB Markerの有無 | Transactionを再読込。Markerが一致すればCommit済み、存在しないことを確定できれば同一Operationで再試行 |
| DB Commit結果不明 / DB unavailable | Source Commit + DB状態不明 | SOURCE_COMMITTEDのまま保留。新Operationで二重適用しない。復旧後Markerを確認 |
| DB Commit後、DB_COMMITTED Event前 | Marker + Source Commit | Marker Hash / Source Hashを照合し、同一ReceiptへDB_COMMITTED Eventを補完 |
| DB_COMMITTED後、VERIFIED前 | Journal + Source + Marker + dependencies | 全依存証拠を再検証しVERIFIED、またはQUARANTINED |
| VERIFIED後 | 全証拠 | 不変。変更・巻戻し禁止 |

一時ファイルや未参照Revisionの削除・再利用・上書き規則はファイルシステムの耐久性契約が必要なため、物理設計に持ち越す。ただし外部正本の確定済みRevisionは不変とする。

## 7. DB Marker / Receipt Eventの相互整合

DB MarkerはSource Commit後にのみ作成する。MarkerのCanonical Payloadは少なくとも以下を含む。
- Physical Run ID / Operation ID / Operation Ordinal
- Intent Hash / Receipt ID
- Source Commit Hash / Source Manifest Head
- Expected DB Marker Payload Hash
- Target Entity Type / Target Entity ID
- DB Mirror Schema Version / Canonicalization Version

DB MarkerとMirror更新は同一DB transactionに含める。MarkerのみCommit、MirrorのみCommitの片肺状態を許さない。

DB Commitの成否が不明な場合はMarkerを読み戻す。
- Marker一致: DB_COMMITTED相当。Receipt Event欠落を同一Operationで補完。
- Marker不存在かつDB transaction rollbackを確認: 同一Operationで再試行可能。
- Marker不一致 / 重複 / 同じOperation IDに別Hash: QUARANTINED。
- DB自体が一時利用不可: SOURCE_COMMITTEDのまま保留し、DB利用可能後に検証。新Operationへ置換しない。

## 8. Recovery Operation

1. 元Receipt / Journal / Source Commit / DB Markerを変更しない。
2. Recovery Operationは新しいOperation ID / Ordinal / Intent / Receiptを持つ。
3. Recovery Planに対象元Receipt ID、検出状態、証拠Hash、実施する修復・再検証の範囲、Actor Intentを固定する。
4. 元ReceiptがQUARANTINEDの場合、Recovery Operationの成功は元ReceiptをVERIFIEDへ書き換えることを意味しない。元ReceiptはQUARANTINEDのまま、Recovery結果を別Artifact / Eventで参照する。
5. DB Mirror再構築は外部正本のHash検証後に限る。DB Mirrorを根拠に外部正本を生成・補完しない。
6. Recovery Operationが不成功なら新しいReceiptも未完了 / QUARANTINEDとして保持する。証拠の削除・隠蔽は禁止。

## 9. 追加受入テスト案

| Test ID | 条件 | 期待結果 |
|---|---|---|
| RCP-001 | Intent完全永続化後、Receipt前にクラッシュ | 同じIntentから同一Receipt Envelopeを再構成 |
| RCP-002 | Intentに必要Hash / Plan情報が欠落 | Receipt再構成不可。Ordinal再利用せず隔離 |
| RCP-003 | PREPARED後、Source Commit前に明示中止 | Source Commit不存在を検証後ABORTED |
| RCP-004 | Source Manifest検証不能で中止要求 | ABORTED禁止。保留またはQUARANTINED |
| RCP-005 | Source Commit後、SOURCE_COMMITTED Event前にクラッシュ | Manifest検証後に同一Receipt Event補完 |
| RCP-006 | SOURCE_COMMITTED後、DB利用不可 | 同じReceipt / Operationを保持し、DB利用可能まで保留 |
| RCP-007 | DB Commit後、DB_COMMITTED Event前にクラッシュ | Marker一致を検証し同一Receipt Event補完 |
| RCP-008 | DB transaction結果不明、Marker一致 | Commit済みと判定。二重適用せずEvent補完 |
| RCP-009 | DB transaction結果不明、Markerなし・rollback確認 | 同一Operationで再試行 |
| RCP-010 | 同一Operation IDで別Intent Hash | QUARANTINED。Ordinal / ID再利用なし |
| RCP-011 | VERIFIED Receiptへの追記要求 | 拒否 |
| RCP-012 | QUARANTINED Receiptの直接解除要求 | 拒否。新Recovery Operationを要求 |
| RCP-013 | Receipt Event Ordinal重複 / gap / Hash Chain不一致 | Receipt検証失敗・隔離 |
| RCP-014 | Unknown Event Type | 無視せず検証失敗 |
| RCP-015 | MarkerのみCommit / Mirror未Commit | transaction atomicity違反として検出 |
| RCP-016 | MirrorのみCommit / Marker未Commit | transaction atomicity違反として検出 |

本テストIDは提案ID。V082-001〜053との対応は未確定であり、PASSを意味しない。

## 10. 未解決事項

1. Journal Intentの既存Canonical Schema / Hash Chainがあるか。新フィールドを追加する場合の互換性。
2. Manifest Head / Source Commitの具体的な原子的更新・読み戻し契約。
3. Intent / Receipt / EventのCanonical Binary Name / Payload Hashの完全文法。
4. DB Marker Hashの計算対象（Marker payload自身の自己参照を避ける定義）。
5. DB transaction結果不明時の読み戻し整合性・Isolation / durability条件。
6. Physical Run排他ロックの取得・クラッシュ後のstale lock回復規則。
7. Receipt / Eventの完全Entity属性・PK / UK / FK / CHECK / Retention。
8. Restore Phase A / Bとの全条件照合とV082 crosswalk。

## 11. 結論

IntentがReceiptを決定的に再構成できる完全なOperation Planを保持すること、Receipt EnvelopeとEventを分離すること、ABORTEDをSource Commit不存在の積極的証明に限定すること、DB状態不明時は新Operationへ置換せず同一Operationを保留・再開することを修正候補とする。

本書は未承認の論理補助案である。v0.8.3本文への反映・統括再提出・DDL・DB生成・Migration・実装を許可しない。
