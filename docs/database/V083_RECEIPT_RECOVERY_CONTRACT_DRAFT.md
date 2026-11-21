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


## 12. Crash-point / idempotency / authority再監査（2026-11-21追加）

### 12.1 現行草案で論理的に整合している点

1. Journal Intentを先に永続化し、Receipt Envelope / PREPARED EventをSource Commitより前に記録する順序は、Main draft §2.1の順序と整合する。
2. Source Commit後はABORTEDへ戻さず、同一OperationでDB Mirrorを再開する方針は一貫している。
3. DB MarkerとDB Mirror更新を同一Transactionに含め、Commit結果不明時にMarkerを読み戻す方針は二重適用を避ける方向で整合する。
4. VERIFIED / ABORTEDは終端不変、QUARANTINEDの解除は新Recovery Operationとする境界は、元証拠の書換え防止と整合する。
5. Receipt EnvelopeとReceipt Eventを分離し、Stateを検証済みEvent Chainから導出する考え方は、Envelopeのmutable state化を避けている。

上記は文書内の論理整合の確認であり、実装可能性・電源断耐性・ファイルシステム耐久性・SQLite transaction durabilityの実証ではない。

### 12.2 Crash matrixに追加が必要な未カバー点

| 未カバー点 | 発生し得る状態 | 現行の不足 | 必要な論理受入条件（提案・未承認） |
|---|---|---|---|
| PREPARED Eventの追記途中 | Envelopeは永続化済み、Eventファイル/recordが部分書込み | Envelope後〜PREPARED Event前は扱うが、Event自体の部分書込み・再読込判定がない | Eventは完全なHash/Ordinal単位で検証。部分Eventを有効Eventとして採用せず、同一Event Ordinalを安全に補完できる条件と不可能時の隔離を定義 |
| SOURCE_COMMITTED Eventの追記途中 | Source Commit済み、Eventが部分書込み | Event欠落は補完するが、部分Event・破損Tailの扱いが未定義 | Source Manifestを再検証後、既存Tailを破壊せず同一OperationのEventを補完。Tailの切捨て・上書き可否は物理耐久契約へ |
| DB_COMMITTED Eventの追記途中 | Marker/DB Mirror Commit済み、Eventが部分書込み | Marker一致後の補完はあるが、破損Tailとの競合条件がない | DB MarkerとSource Commitを照合し、Event Chainの有効Tailを確定できる場合だけ同一Receiptを補完。確定不能ならQUARANTINED |
| VERIFIED Eventの追記途中 | 依存検証済み、終端Eventが不完全 | VERIFIED後は不変とあるが、終端Eventの不完全書込み状態が未定義 | VERIFIED Eventの完全性を再検証できない限りVERIFIEDと認定しない。再検証・補完の可否をOrdinal / Hash Chain規則に含める |
| ABORTED / QUARANTINED Eventの追記途中 | Operator判断は行われたがEvent永続化結果が不明 | 明示判断とEvent耐久化の間の結果不明を規定していない | 判断IntentとEvent記録の権威境界を明記。Event永続化を確認できなければ終端確定としない。別Operationによる重複判断を禁止 |
| 同一Operationの並行Recovery | 2つのRecovery worker / operatorが同一Receiptを同時に再開 | Physical Run lockは言及するが、Receipt単位のfencing / stale lock対策がない | 同一Operation / Receiptに対する単一writerとfencing tokenの論理要件を定義。物理方式は保留 |
| Manifest Head更新後の読戻し競合 | 他OperationがHeadを先行更新 | predecessor検証はあるが、CAS相当の競合拒否・再試行条件が未定義 | Expected predecessorと新Headの一意な対応を検証し、別Operationが介在したら上書きせずQUARANTINEDまたは安全な直列再開 |
| DB Commit結果の読戻し可視性 | Commit後に別接続からMarkerが見えない / 遅延読出し | Marker不存在とrollback確認を条件にするが、読戻し一貫性・Isolationの前提が未定義 | 「Marker不存在」を確定できるDB読戻し条件を定義。読出し一貫性を保証できない場合はSOURCE_COMMITTED保留 |
| Receipt Event Ordinal予約 | Event追記中にクラッシュしOrdinalだけ消費 / 競合 | gap検出はあるが、Ordinal予約・消費の正本が未定義 | Event Ordinalの発行主体・消費時点・欠番許容/拒否を定義。再利用禁止と補完可能条件を区別 |
| Intent / Receiptの自己Hash計算 | Hash対象に自己Hash欄や相互参照Hashが含まれる | Canonical payload範囲の完全定義がない | 自己Hash対象から除外するfieldと相互参照Hashの生成順を定義。循環依存がないCanonicalization vectorを提示 |

### 12.3 Main draftとの同期が必要な項目

1. 本書§2の「完全なOperation Plan」にはExpected Receipt Hashを含める提案があるが、Main draft §2.1のIntent項目一覧には明記がない。採用する場合はMainと本書の両方へ同期する。
2. 本書§3のReceipt Envelope属性（Envelope Schema Version / Created At / Expected Source Manifest Head / Plan Hash等）とMain draft §2.1の列挙を項目単位で照合し、Main本文の最低契約へ反映するか、補助資料に委任する範囲を明記する。
3. Main draft §2.1の「Receipt PREPARED Eventを追記・永続化」は、Envelope本体の永続化とEventの永続化を別々の完了条件として記載する必要がある。補助資料のCrash Matrixと同じ粒度にする。
4. Receipt IDのOperation ID決定的導出は、Canonical Namespace未承認のままUUIDv5採用を前提にしてはならない。決定的導出方式・Namespace・互換性の根拠が確定するまで実装規則にしない。
5. Main draft §8のRawLog耐久要件をReceipt一般のファイル耐久要件へ拡張しない。Journal / Receipt / RawLog / Telemetryで正本性・損失許容・durabilityを分類し、Issue #35のMotor RawLog契約と照合する必要がある。

### 12.4 現時点の判定

- 論理順序（Intent → Envelope/PREPARED → Source Commit → DB Marker/Mirror Commit → VERIFIED）は文書上の候補として整合。
- クラッシュ点の列挙は改善済みだが、Event append途中、Event Ordinal消費、並行Recovery / fencing、Manifest Head競合、DB read-after-commit保証が未定義。
- Intent / Receiptの完全Canonical payloadと自己Hash除外規則が未確定。
- Main draftとの項目単位の同期は未完了。
- Receipt IDの決定的導出とUUIDv5 Namespaceは未承認。
- したがってReceipt Recovery Contractは完成扱いにせず、DB-RV-03解消済みとも判定しない。

次の作業は、上記の未カバー点を論理要件・物理耐久契約・未受領の外部仕様に分け、Main draftと補助資料の同期差分を作成することである。実装・DDL・DB生成・Migration・Restore実行は禁止境界を維持する。


## 13. 未解決事項の責任境界と閉鎖順序（2026-11-21追加）

本節は§10 / §12の未解決事項を、論理設計で決める事項と、物理方式・実装証拠がなければ決められない事項に分ける。未決事項を推測で埋めず、論理承認前に必要な判断と、物理設計ゲートへ送る判断を混同しない。

### 13.1 論理設計段階で閉じる必要がある事項

| 項目 | 現在の根拠 | 論理段階の完了条件 | 現在の扱い |
|---|---|---|---|
| Intent完全性 | §2に最低Plan項目、Main §2.1はIntent Payload/Hashのみ | Receipt再構成に必要な全入力・参照・期待Hashを列挙し、Main §2.1と同一契約にする | 未完了。Main同期が必要 |
| Receipt ID導出 | Main / 本書にOperation IDから決定的導出とある | 方式・入力・versioning・衝突/再発行規則を定義し、Namespace未承認のUUIDv5を前提にしない | 未承認 |
| Event identity / Ordinal | Receipt内Ordinal単調増加、gap拒否、再利用禁止の記述あり | Ordinalの権威ある発行主体、消費点、欠番・部分Eventの状態規則を決める | 未完了 |
| Event partial append | §12.2で部分Tailを未定義と確認 | 完全性検証に失敗したEventをStateへ採用しないこと、同一Eventを補完できる条件、補完不能時の隔離条件を論理的に定義 | 未完了 |
| 同一Operation並行実行 | Physical Run lockの記述あり。Receipt単位fencing未定義 | 同一Operation / Receiptの二重writerを禁止し、競合時に先行/後続をどう判定するかを定義 | 未完了 |
| Manifest Head競合 | predecessor検証は記述あり | Expected predecessorから異なるHeadが観測された場合、上書きせず競合として扱う判定規則を定義 | 未完了 |
| DB Commit結果不明 | Marker読戻しの記述あり | Marker不存在を確定できない場合は保留し、確定可能な場合のみ同一Operation再試行とする抽象条件を定義 | 部分。読戻し前提が未定義 |
| Envelope / Event Hash範囲 | Canonical serialization / Hash記述あり | 自己参照除外、相互Hash依存、version、必須/禁止fieldを確定しGolden Vectorを提示 | 未完了 |
| Receipt / Journal Entity境界 | Envelope/Event/Intentの概念分離あり | ID・属性・Authority・Cardinality・Retention・Recovery責務をEntity Inventoryと一致させる | 部分 |

### 13.2 物理設計・実装段階まで保留する事項

以下は論理的な受入条件を先に定める必要があるが、具体的な方式や実証は物理設計・実装・耐久試験なしに確定しない。

- File fsync、親Directory fsync、atomic rename / head switchの具体的保証と対象OS / filesystem。
- 部分書込みTailの検出・切り分け・保存・修復方法。原本の切捨てや上書きは論理許可なしに行わない。
- SQLite transaction isolation / synchronous設定 / WAL運用 / power-loss durabilityと、別接続からのread-after-commit実証。
- Lock lease / stale lock回復 / fencing tokenの実装機構とプロセス・電源断時の競合試験。
- 実際の電源断・プロセスkill・I/O error・DB unavailableを用いたcrash injection試験。

本段階では実装・DDL・DB生成・Migration・Restore実行を行わない。これらの物理方式を仮定して論理要件を合格扱いにしない。

### 13.3 閉鎖順序

1. Main §2.1と本書§2 / §3 / §4 / §6のOperation Plan・Envelope・Event属性を項目単位で同期する。
2. IntentからEnvelopeを再構成する決定性、Receipt ID導出、Hash対象・自己参照除外を論理契約として確定する。
3. Event Ordinal / partial append / same-operation writer / Manifest Head競合の抽象受入条件を確定する。
4. DB read-after-commitが成立しない/証明できない場合の保留条件を明文化する。
5. Entity Inventory 23種のうちJournal / Receipt / Marker / Recovery関連Entity境界と整合させる。
6. 上記を統括審査へ提出。承認後にのみ物理設計の検討を開始する。

**現時点の判定:** DB-RV-03は未解決。論理条件の不足と物理実証の不足を分離できたが、いずれも合格・完了とはしない。
