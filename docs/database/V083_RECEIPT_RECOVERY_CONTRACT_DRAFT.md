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


## 14. Main §2.1 項目単位照合と同期差分案（2026-11-21）

### 14.1 照合範囲・判定方法

Main draft §2.1「正規順序」および同節直後の補足文を、Receipt Recovery Contract §§2〜4、§6、§7と項目単位で照合した。ここでの「一致」は両文書に同じ論理要件が明記されていることを指し、実装・耐久性の実証を意味しない。「部分」は関連要素があるが再構成・検証に必要な定義が欠ける状態、「未記載」はMain §2.1に規定がない状態である。

### 14.2 Traceability Matrix

| Main §2.1の現行記述 | Receipt補助契約の対応箇所 | 判定 | 差分・扱い |
|---|---|---|---|
| 1. Physical Run単位の排他ロック、Journalと直近Ordinal検証 | §2 Operation Plan / §6 lock・Ordinal論点 | 部分 | Receipt補助契約はPhysical Run排他を前提にするが、lockのauthority、stale lock、fencing、Ordinal発行主体・消費点は未確定。物理方式は保留し、論理上の単一writer要件を別途閉じる必要がある。 |
| 2. Operation ID / Ordinal / Intent Payload / Intent Hashを確定 | §2 最低限Intent Plan、§3.1 Envelope | 部分 | Mainの4項目に加え、Receipt再構成に必要なOperation Type、Target Entity Type/ID、Actor/Initiator、Explicit Intent Reference、Canonicalization / Payload Schema Version、Expected source object/revision、Manifest predecessor/head等が補助案に列挙される。Plan完全性と各fieldのauthorityは未確定。 |
| 3. Journal Intentを追記・永続化し、完了時にOrdinal消費 | §2 Operation Plan確定・Intent immutable、§6 crash matrix | 部分 | MainはOrdinal消費点をIntent永続化完了時とする。補助案はIntent書込み中の部分状態・検証不能時の隔離を追加するが、Ordinalの発行主体・予約・消費の一意な規則は未確定。 |
| 4. Receipt PREPARED作成。Receipt IDをOperation IDから決定的導出。Operation ID / Ordinal / Intent Hash / Expected Source Payload Hashes / Expected DB Marker Hash / Target Entity ID / Canonicalization Version | §§2, 3.1 | 部分 | 共通項目はある。補助案はPhysical Run ID、Plan Hash、Expected Source Manifest Head、Envelope Schema Version、Created At、Envelope Hash等を追加。Receipt IDの導出アルゴリズム・入力・version・衝突/再発行規則は両文書とも未定義。UUIDv5を採用済みと解釈しない。 |
| 5. Receipt本体・親Directory永続化、PREPARED Event追記・永続化 | §§3.1, 3.2, 4, 6 | 部分 | 補助案はEnvelopeとEventを分離しStateをEvent Chainから導出する。Mainの「Receipt本体」がEnvelopeのみか、Eventを含む格納単位かは明示されていない。PREPARED Eventの部分書込み、Ordinal消費、同一Event補完条件は未確定。 |
| 6. Sourceの不変Revision書込み、File fsync/Hash検証、Manifest/Head原子的更新 | §§3.1, 4, 5, 6 | 部分 | 補助案はExpected Source Manifest Head / predecessorとSource Commit検証を要求する。Expected predecessorとHeadの競合拒否・CAS相当条件は未定義。fsync・atomic updateのOS/filesystem保証は物理設計へ留保。 |
| 7. Source Revision / Manifest Hashを読戻し、Expected Source Payload Hashesと照合しSOURCE_COMMITTED Event | §§3.1, 3.2, 4, 6 | 部分 | Event Chainの完全性・部分Tail・Ordinal・Hash Chainの補完条件が不足。SOURCE_COMMITTED Event欠落の補完方針はあるが、破損Tailを含む場合の受入条件は未確定。 |
| 8. DB Mirror変更とOperation Markerを同一TransactionでCommit。MarkerにOperation ID / Ordinal / Intent Hash / Receipt ID / Source Commit Hash / DB Commit Payload Hash | §7 | 部分 | 補助案のMarker項目はPhysical Run ID、Source Manifest Head、Expected DB Marker Payload Hash、Target Entity Type/ID、DB Mirror Schema Version等を含む。MainのDB Commit Payload Hashと補助案のExpected DB Marker Payload Hashの意味・Hash対象が同一か未定義。 |
| 9. Commit結果を読戻し、MarkerとJournal / Receipt / Source Commit Hashを照合 | §§6, 7 | 部分 | Marker一致/不一致/不存在時の方向性はあるが、「不存在かつrollback確認」のDB読戻し一貫性・Isolation前提は未定義。読戻し確定不能時はSOURCE_COMMITTEDのまま保留する扱いを維持。 |
| 10. DB_COMMITTED Event追記・永続化 | §§3.2, 4, 6, 7 | 部分 | Marker照合後に同一ReceiptへEvent補完する方針は一致。Event部分書込み・Ordinal消費・有効Tail判定は未確定。 |
| 11. Journal / Marker / Receipt / 関連外部正本再検証 | §§4, 6, 7 | 部分 | 補助案は全依存Hash検証を要求するが、依存集合の閉包・列挙authority・Hash自己参照除外が未定義。 |
| 12. VERIFIED Event追記・永続化 | §§3.2, 4, 6 | 部分 | VERIFIEDを終端不変とする点は一致。VERIFIED Event自体の部分書込み時にVERIFIEDを認定しない原則はあるが、同一Ordinalでの補完可否・Event Tail確定規則は未確定。 |
| 13. 全永続化・照合成功後に排他ロック解放 | §6 lock / Recovery論点 | 部分 | ロック解放の前提は一致するが、クラッシュ後のstale lock、fencing、同一Operation/Receiptへの二重Recovery writer防止は未定義。 |
| Main §2.1に明示なし | §3.1 Envelope Schema / §3.2 Event Schema | 未記載 | Envelope Schema Version、Envelope Hash、Event Ordinal、Previous Event Hash、Event Payload、Event At、Actor / Recovery Operation IDの条件、Event HashがMain §2.1に現れない。補助契約だけでMainの規範的欠落が解消したとは扱わない。 |
| Main §2.1に明示なし | §5 Source Commit不存在の証明 | 未記載 | ABORTEDを許可する積極的証拠条件、Operator中止Intent、保留とQUARANTINEDの境界がMain §2.1には記載されていない。Main §2.2/§2.3との同期も要確認。 |

### 14.3 同期差分の分類

**文書間で方向性が一致している項目**
- Journal IntentをReceiptより先に永続化する。
- Receipt PREPAREDはSource Commit / DB Commitより前に存在する。
- Source Commit後はABORTEDへ戻さず、同一OperationでDB Mirrorを再開する。
- DB MarkerとDB Mirror変更は同一Transactionとする。
- VERIFIED / ABORTEDは終端不変、QUARANTINEDの解決は新Recovery Operationとする。

**Main §2.1へ追記候補だが、内容確定前に決定が必要な項目**
- Operation Planの完全field listと、Intent永続化前の検証条件。
- Receipt EnvelopeとReceipt Eventの別個の証拠境界、およびMainの「Receipt本体」の意味。
- Receipt ID導出規則（UUIDv5を前提にしない）。
- Envelope / Event / MarkerのHash対象、自己Hash除外、相互参照Hash生成順。
- Event Ordinalの発行authority・消費点・gap・partial append・補完条件。
- Manifest predecessor / Headの競合条件。
- DB Marker不存在を確定できない場合の保留規則。
- ABORTEDの積極的不存在証明と明示中止Intent。

**この段階でMain §2.1へ転記してはならない項目**
- 未承認のReceipt IDアルゴリズムやNamespace。
- 未定義のHash計算範囲・自己参照除外。
- 未確定のEvent Ordinal予約/補完方式。
- 未確定のManifest競合時の自動回復方式。
- fsync / atomic rename / SQLite Isolation等の物理保証。

### 14.4 変更提案の結論

現時点ではMain §2.1を編集しない。理由は、補助契約がMainより詳細な項目を提案している一方、その一部はauthority・Hash範囲・Ordinal・競合条件が未決定であり、Mainへそのまま転記すると未承認事項を規範化するためである。

次の論理設計作業は、14.3の未決定項目を個別に閉じ、Main §2.1・§2.2・§2.3と補助契約を同時に改訂できる変更表を作成すること。物理耐久性・filesystem / SQLiteの実証は論理受入条件の確定後に別工程とする。

**状態:** Main §2.1との項目照合は完了。同期差分は可視化したが、DB-RV-03は未解決。Main本文への反映・承認・実装許可を意味しない。


## 15. Main §2.1〜§2.3 同期に向けた論理決定台帳（2026-11-21）

本節は、Main §2.1の正規順序、§2.2のReceipt State、§2.3のクラッシュ復旧表を補助契約と同時に改訂するための決定台帳である。ここで「論理規則案」とした内容は、現行本文から導ける安全側の提案であり、Main本文へ反映済み・統括承認済みとは扱わない。物理方式は決めない。

### 15.1 Main §2.1〜§2.3 の同期変更表

| Main箇所 | 現行記述・不足 | 補助契約との関係 | 同期に必要な論理規則 | 状態 |
|---|---|---|---|---|
| §2.1 1〜3 | 排他ロック、Ordinal確定、Intent永続化完了時の消費 | §§2, 6 | Physical Run単位の単一有効Writer、Ordinal発行Authority、Intentの完全性検証、部分Tail時の非再利用・隔離を定義する。ロック方式・fencing実装は物理保留 | OPEN |
| §2.1 2〜4 | Intent列挙だけではReceipt全項目を再構成できない可能性 | §§2, 3.1 | Intent PlanをReceipt Envelope再構成に必要な完全な不変入力とし、Plan Hash / Intent Hash / Expected Receipt Hashの相互関係を定義する | PARTIAL |
| §2.1 4〜5 | Envelope永続化とPREPARED Eventの間のクラッシュ | §§3.1, 3.2, 4, 6 | Envelopeが存在しEventが未記録の場合、Envelope HashとIntentを検証して同じReceiptへPREPAREDを補完。Event部分書込み時は後続Eventを追加しない | PARTIAL |
| §2.1 6〜7 | Manifest Head更新・predecessor競合・Source Commit Eventの境界が抽象的 | §§4, 6 | Source CommitはExpected predecessorと現Headが一致する場合のみ確定。結果不明時は再読込し、確定不能・競合は保留またはQUARANTINED | OPEN |
| §2.1 8〜9 | DB Marker Hash / DB Commit Payload Hashの同一性が不明 | §7 | Expected Marker Payload Hashと実Marker Payload Hashを同一Canonical Payload範囲で比較する。DB transaction commitの成否不明時はSOURCE_COMMITTEDのまま保留 | OPEN |
| §2.1 10〜12 | Receipt EventのOrdinal、部分書込み、Hash Chainの補完規則が不足 | §§3.2, 4, 6 | Event Chainの連続性・単一Writer・Tail検証を定義。部分/不正Tailの後ろへ追記せず、証拠保全して隔離 | OPEN |
| §2.1 11 | 「全依存正本」の集合を誰が確定するか不明 | §§3.2, 7 | Intent Planで固定された対象・依存参照の閉包を検証対象とし、後から依存を暗黙追加しない | OPEN |
| §2.2 | PREPARED / SOURCE_COMMITTED / DB_COMMITTED等の状態定義はあるが、未着・部分Eventの状態が不足 | §§3.2, 4, 5 | 状態は完全に検証できるEvent Chainからのみ導出。Event未着は状態進行とみなさず、検証不能は保留または隔離 | PARTIAL |
| §2.3 | Intent後〜PREPARED前、DB transaction中、Hash/Ordinal競合の復旧条件が粗い | §6 | Crash pointをEnvelope作成前後、Event追記中、Manifest更新中、DB commit結果不明に分解し、各点で同一Operation再開・保留・QUARANTINEDの条件を揃える | PARTIAL |
| §2.1 / §2.2 | Receipt IDの決定的導出、Envelope/Event/Intent/Marker Hashの自己参照除外が未確定 | §§2, 3, 7 | ID導出入力・Version・再現性とHash対象Field/Canonical Schemaを確定する。Namespaceは統括承認まで未採用 | OPEN |

### 15.2 現行資料から導ける安全側の論理規則案

以下は物理実装を指定せず、復旧時に推測で成功・中止・Ordinal再利用を行わないための候補規則である。Mainへの規範反映前に、統括の承認対象として明示する。

1. **単一Writer:** 同一Physical RunのOperation Journal / Manifest Head / Receipt Event Chainは、論理上同時に1つの有効Writerだけが更新できる。複数Writerを検出した場合は新規更新を停止しQUARANTINEDとする。排他の具体方式・stale lock・fencingは物理設計へ保留。
2. **Ordinal非再利用:** Operation OrdinalはPhysical Run内で単調増加し、欠番を許容するが再利用しない（Main §2.3の現行規則を維持）。Receipt Event OrdinalはReceipt内で単調増加し、既存Schemaの「gapは検証失敗」を維持して連続Chainとする。両Ordinalの発行Authority・消費点は別々に定義する。完全なIntent/Eventが検証できない部分Tailがある場合、Tailを黙って切り捨てたり、そのOrdinalの後ろへ追記したりせず、証拠を保全してQUARANTINEDとする。
3. **Event補完:** Envelopeが完全・Hash一致で存在しPREPARED Eventだけが欠落している場合に限り、同一ReceiptへのEvent補完候補とする。Event書込み結果が不明な場合はChainを再読込し、完全なEventとして検証できれば既存Eventとして扱い、不正Tailなら追記せず隔離する。
4. **Manifest競合:** Source Commit前にExpected predecessorと現在Headが一致しない場合はCommitを拒否する。Head更新結果が不明なら再読込し、当該OperationのExpected Head / Commit Hashと一致する場合のみSource Commit済みと認定する。別OperationのHead、欠落、Hash不一致は自動上書きせず隔離する。
5. **DB Marker不確実性:** DB unavailableまたはCommit結果不明の間はSOURCE_COMMITTEDのまま保留する。Markerの単純な検索0件だけでRollback済みと断定しない。DBの一貫した読戻しで不存在とRollbackを確定できる場合に限り同一Operationの再試行候補とする。読戻し保証・Isolation条件は物理設計で実証する。
6. **依存閉包:** VERIFIED判定ではIntent Planに固定されたSource Revision、Manifest、DB Marker、Receipt、Journalおよび明示された依存参照を対象とする。依存集合のauthorityと列挙形式が確定するまではVERIFIEDへ進めない。
7. **Hash自己参照:** Intent Hash / Plan Hash / Envelope Hash / Event Hash / Marker Hashは、自身のHash値Fieldを入力対象から除外する必要がある。ただし、除外対象の全Field、Canonical serialization、Hash algorithm、Schema Versionは未確定であり、本節では具体値を採用しない。
8. **Receipt ID:** 決定的再構成が必要だが、導出方式・入力・Namespaceは未確定。UUIDv5候補Namespaceを使用したり、既存IDを推測再採番したりしない。

### 15.3 決定権・保留区分

| 項目 | 論理段階で必要な決定 | 物理段階へ保留する事項 |
|---|---|---|
| Writer / Ordinal | Authority、単一Writer要件、予約/消費点、欠番・部分Tailの状態 | Lock API、lease、fencing token、filesystem lock |
| Receipt Event | Event順序、Ordinal、部分Eventの扱い、補完条件 | append/fsync、atomic file operation、Tail修復実装 |
| Manifest | predecessor照合、Head競合時の拒否・隔離条件 | atomic rename / CAS実装、Directory fsync保証 |
| DB Marker | Marker PayloadとMirrorの一体性、Commit不確実時の保留規則 | SQLite Isolation / WAL / synchronous / read-after-commit実証 |
| Hash / ID | Hash対象・除外Field・Version、Receipt IDの決定的入力 | Namespace採用後の実装性能・耐久試験 |
| Recovery | 同一Operation再開条件、QUARANTINEDへの移行、Recovery Operationの権限 | Crash injection、電源断・I/O error試験 |

### 15.4 現時点の結論

- Main §2.1〜§2.3の同期変更表は作成したが、Main本文は未変更。
- 15.2は安全側の論理規則案であり、未承認事項を確定仕様へ昇格させない。
- DB-RV-03はOPEN。Receipt ID、Hash範囲、Ordinal Authority、Manifest競合、DB Marker不存在の確定条件が閉じていない。
- fsync / atomic rename / SQLite durability / crash injectionは物理設計・実装工程であり、論理文書の記述だけでPASSにしない。
- v0.8.2 ORANGE / v0.8.3未承認。UUIDv5 Namespace未承認・未採用。DDL / DB生成 / Migration / Restore実行 / 実装 / PR / main反映は禁止継続。


## 16. Hash / ID依存関係監査 — 循環・未定義参照候補（2026-11-21）

### 16.1 確認した一次記述
- §2 Intent PlanはOperation Plan Hash / Intent Hashを列挙する。
- §2 Receipt再構成手順は、Intentに固定したExpected Receipt Hashとの一致を要求するが、最低限Intent PlanのField一覧にはExpected Receipt Hashが列挙されていない。
- §3.1 EnvelopeはIntent Hash / Plan Hashを保持し、Envelope HashをCanonical serializationの自己Hashとする。
- §3.2 EventはPrevious Event HashとEvent Hashを保持する。
- §7 DB MarkerはIntent Hash / Receipt ID / Source Commit Hash等を保持し、Expected DB Marker Payload HashもCanonical PayloadのFieldとして列挙する。
- Main §2.1はExpected DB Marker HashをReceiptへ固定し、Marker側にはDB Commit Payload Hashを保持すると記述する。両Hashの同一性・対象範囲は定義されていない。

### 16.2 循環依存・欠落の可能性

| ID | 依存候補 | 問題 | 現時点の判定 |
|---|---|---|---|
| H-01 | Operation Plan Hash → Plan全体 → Operation Plan Hash | 自身を含むHash計算なら自己参照 | Hash対象Fieldの除外規則未定義 |
| H-02 | Intent Hash → Intent Payload / Plan Hash → Intent Hash | Plan HashとIntent Hashの包含・生成順が未定義 | 相互依存の可能性 |
| H-03 | Expected Receipt Hash → Intent Plan → Intent Hash / Plan Hash → Receipt Envelope Hash | IntentにExpected Receipt Hashを固定し、EnvelopeにIntent/Plan Hashを含める場合に循環し得る。Expected Receipt Hash自体もPlan Field一覧に欠落 | Field欠落と循環可能性を確認 |
| H-04 | Expected DB Marker Hash → Intent Plan / Receipt → DB Marker Payload → Expected DB Marker Payload Hash | Marker自身のHashをMarker Payloadに含める場合に自己参照。Expected DB Marker HashとDB Commit Payload Hashの関係も不明 | Hash対象・除外規則未定義 |
| H-05 | Envelope Hash → Envelope全体 → Envelope Hash | 自己HashFieldの除外が必要だが具体規則なし | 自己参照除外未定義 |
| H-06 | Event Hash → Event Payload / Previous Event Hash → Event Hash | 自身のHashField除外、Canonical Event Schema、最初のEventのPrevious Hash表現が未定義 | 連鎖の計算規則未完成 |
| H-07 | Source Commit Hash / Manifest Head Hash → Source Commit対象 | ManifestにReceipt/Expected Hashを含める場合の依存順序が未定義 | Manifest payload境界未確定 |

### 16.3 Hash依存グラフを閉じるために必要な定義

1. 各Hashの対象となるCanonical Payloadを、Field単位で列挙する。
2. Hash自身、後段でしか決まらない値、別Hashを含めるかを明示し、Hash生成順を有向非循環グラフとして提示する。
3. Operation Plan Hash / Intent Hash / Expected Receipt Hash / Envelope Hashの役割と包含関係を分離する。
4. Expected Receipt Hashが必要ならIntent Planの正式Fieldとして定義する。不要なら再構成手順から削除する。どちらも現時点では選択しない。
5. Expected DB Marker Hash / Expected DB Marker Payload Hash / DB Commit Payload Hashの同一性・包含関係を決める。名称の類似だけで同一扱いしない。
6. Event HashはPrevious Event Hashを含むか、Event Hash自身を除外するか、初回EventのPrevious Hashをどう表すかを固定する。
7. Canonicalization Version / Envelope Schema Version / Event Schema Version / Marker Schema Versionのどれが各Hashに適用されるかを定義する。
8. Receipt IDの決定的導出はHash依存グラフと分離して定義し、未承認Namespaceを前提にしない。

### 16.4 結論
現行資料だけではHash依存グラフが非循環であることを証明できない。これは実装不具合の確定ではなく、仕様のHash入力・除外・生成順が未定義であることを示す。Hash関数・Namespace・Field順を推測で補完しない。DB-RV-03はOPENを維持する。
