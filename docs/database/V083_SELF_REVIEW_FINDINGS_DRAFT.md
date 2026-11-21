# v0.8.3 自己検証レビュー記録（初回）

- 基準日: 2026-11-21
- 対象: `docs/database/COMMON_DB_LOGICAL_DESIGN_v0.8.3_REMEDIATION_DRAFT.md`
- Branch: `docs/db-logical-design-v0.8.3-remediation-20261120`
- 対象Blob（レビュー開始時）: `73255a791e3f0c8e469d6f2e32c069c7c1c20aba`
- 判定: **自己検証未完了。統括再提出不可**
- 更新注記: 本書の「初回」所見は作成時点の履歴。2026-11-21 Issue #210決定によりSR-01 / SR-02 / SR-09の一部または全部は下記Decision Overlayで解決・置換され、未解決課題としてそのまま再掲しない。
- 本書は論理レビュー記録であり、仕様承認・実装許可ではない。

## 1. 上位指示の再確認

### Issue #209 — 統括審査
- State: OPEN
- 判定: ORANGE — 条件付き差戻し・最終承認保留
- 現在のコメント数: 0。追加の統括判断・承認は確認できない。
- 物理設計、DDL、DB生成、Migration、実装、実装PRは禁止継続。

### Issue #201 — Anonymous / DB unavailable
- State: CLOSED（統括指示・Phase 2の範囲を記録）
- DBファイル新規生成、空DB暗黙生成、migration、初期化、テストデータ投入、旧DB復旧・移行は禁止。
- fail-closed、DB不存在時の暗黙DB生成禁止を維持。
- ANONYMOUS期間のRawLog / Measurementは現行範囲で後日DB取込・Mirror化・Instance再紐付け禁止。NONEとは区別する。
- NONE期間については、DB利用可能時に取得され、外部正本およびDB管理下のMeasurement記録が既に存在する場合に限り、後日の明示Associationを論理設計対象としてよい。自動取込・新規Mirror生成は不可。測定時Assignment=NONEを保持し、監査履歴を残す。

### Issue #85 / #86 — DB安全化
- 運用DBの選定・切替・書込み・migration・初期化は別途承認が必要。
- 通常起動からschema作成やmigrationを呼ばない。
- Migrationは明示管理操作からのみ。ただしこれは本設計にBootstrap実行権限を与えるものではない。

### Issue #35 — 現行仕様正本
- Motor接続・制御・RawLog契約の正本はIssue #35。本設計で上書きしない。
- Issue #35のリスク方針では、初期段階の全RawLog/Evidence完全保存を一律必須とせず、Telemetry欠損を許容し頻度・範囲を記録する方針がある。
- よってv0.8.3 §8のFile fsync / Hash再読込 / Atomic Rename / Directory fsyncを、全RawLogに一律必須化するには、RawLog種別・正本性・欠損許容方針との整合根拠が必要。

## 2. 検出事項

### SR-01 — 後日AssociationがIssue #201の現行範囲を越えている
**重大度: BLOCKER / 範囲・承認不整合**

該当: §1.2(6)、§1.3、§6 Measurement行・後段説明、§12。

初回レビュー時の草案はNONE / ANONYMOUSを一括して後日Association対象に含めていた。Issue #210（CC-02）はこの扱いを分離し、ANONYMOUSは後日取込・Mirror化・再紐付けを禁止、NONEは既存DB管理Measurementに限る明示Associationのみを論理設計対象として許容した。

修正方針:
1. ANONYMOUS期間のRawLog / Measurementは外部正本として保全し、現行範囲で後日DB取込・Mirror化・Instance再紐付けを禁止する。将来変更は別設計と統括の明示承認を要する。
2. NONE期間は、DB利用可能時に取得され、外部正本およびDB管理下のMeasurement記録が既に存在する場合に限り、明示Associationを論理設計対象としてよい。自動取込・新規Mirror生成は不可。
3. NONE AssociationではAssignment-at-Measurement=NONEを不変とし、Actor・時刻・変更前後・理由を監査履歴に記録する。関連付けだけでCurrent Aggregateへ算入しない。

### SR-02 — Session Measurement集合の時点定義がAssociation案と衝突
**重大度: BLOCKER（SR-01と連動）**

該当: §1.2(6)、§1.3、§1.4。

初回レビュー時は、Session membershipと後日Associationの境界が未定義だった。Issue #210 CC-02によりNONEの明示Associationが限定許容されたため、既存DB管理MeasurementのSession membership条件・関連付け先Sessionの適格性は別途論理定義が必要。

修正方針:
- SR-01のとおり後日Associationを本版から外す場合、Sessionの通常所属条件を「Session生成後に測定・登録され、測定時Assignmentが当該ScopeのASSIGNED状態であるMeasurement」として定義する。
- 将来Associationを再設計する際は、Session membershipとAssignment-at-Measurementを別の関係として定義する。

### SR-03 — DB Run/Session生成とDBファイル生成・Bootstrapの境界
**重大度: BLOCKER / 誤読防止**

該当: §1.1〜1.3、§6、§9。

「最初のASSIGNED OperationでDB Run/Sessionを生成」という記述は、既存の承認済みDB内にMirrorレコードを作る意味であることを明確にする必要がある。DBファイル、schema、空DB、migration、Bootstrapを自動生成する意味に読めてはならない。

また§9の「新規DBへの明示管理操作」は、Issue #201の現行禁止境界に対して、実行可能な許可と誤認される余地がある。

修正方針:
- DB Run / Session生成は、既に存在し、明示設定され、schema検証済みで、利用が承認されたDBが利用可能な場合のMirror record作成に限定する。
- DB file creation / schema creation / migration / bootstrap / initializationは本版の対象外かつ未許可と明記する。
- Bootstrapは将来の別承認対象とし、§9の復元手順がDB新規作成を許可するように読めないようにする。

### SR-04 — RawLog durability要件の一律適用
**重大度: HIGH / Issue #35との契約照合待ち**

該当: §8、§2.1、§6。

§8はすべてのRawLogについてFile fsync、Hash reread、Atomic Rename、Directory fsync、最終Hash検証を保存完了条件としている。一方、Issue #35は初期段階のTelemetry/RawLog完全保存を一律要求せず、欠損を許容して記録するリスク方針を持つ。

修正方針:
- RawLogを、測定の正本となる確定ファイル、Telemetry capture、診断用ログ等に分類し、各々の耐久性・欠損許容を定義する。
- 全RawLogへ一律に完全耐障害保証を課さない。
- 必須保証の根拠・費用・失敗時挙動をIssue #35の現行契約と照合し、未確定項目は未確定として残す。

### SR-05 — Receiptの状態・クラッシュ回復に残る明確化事項
**重大度: HIGH**

該当: §2.1〜2.3、§9。

1. Receipt本体のPREPARED状態とReceipt Event PREPAREDの関係を、Envelope/State/Eventの区別として明示する。
2. Intent永続化後・Receipt作成前のクラッシュ時にABORTEDを記録するなら、Receipt Envelopeをどのように決定的に作成し、ABORTED Eventをどこへ永続化するかを定義する。
3. ABORTEDはSource Commitが存在しないことを検証した場合に限る。Source Manifest/Headの検証不能時はABORTEDではなくQUARANTINEDとする。
4. Restore時にPREPARED / SOURCE_COMMITTED / DB_COMMITTEDが残っていた場合、通常接続前にどのRecovery Operationで再開・隔離するかを定義する。未完了ReceiptをVERIFIED/ABORTEDへ推測で確定しない。
5. Receipt Eventの許可遷移を表形式にし、PREPARED→ABORTED、PREPARED→SOURCE_COMMITTED→DB_COMMITTED→VERIFIED、各段階からQUARANTINEDへの条件を網羅する。

### SR-06 — Aggregate Current Validの識別条件が弱い
**重大度: HIGH**

該当: §3.1〜3.3。

Current Valid判定がInput Set Hash中心だが、RequestにはAssignment Snapshot Set Hash、Algorithm Version、Configuration Versionも含まれる。入力値が同じでもAlgorithm/ConfigurationまたはAssignment Snapshotが異なる要求を、Input Set Hashだけで同一視してはならない。また遅延した旧Requestの成功結果が最新Requestと同じInput Set Hashを持つ場合の昇格条件が不明。

修正方針:
- Current Validは少なくともLatest Requested Request IDへの一致を要求する。
- Request FingerprintにInput Set Hash、Assignment Snapshot Set Hash、Algorithm Version、Configuration Version、必要なScope/Policy Revisionを含める。
- Latest Successful Revisionの順序（Request Ordinal、Revision Ordinal、完了時刻のどれを基準とするか）を定義する。
- Retryを終了してFAILEDへ確定する条件と、再試行受付を閉じる操作/状態を定義する。

### SR-07 — Canonical Binary Name v2の文法・テスト範囲が未完成
**重大度: HIGH**

該当: §5.2〜5.5。

提示された7件のbyte vectorは初期例として有用だが、全EntityのGolden Vectorではない。Entity Type/Fieldの最大長、未定義Tag、Field Count不一致、整数の範囲、Timestampのsigned 64-bit nanosecond範囲、ASCII/UTF-8入力の不正値、Field Schema Versionの扱いが未定義。Namespace既存利用調査と統括承認も未完了。

修正方針:
- Canonical Nameの完全な文法、入力拒否条件、上限値、Version互換規則を定義する。
- Entityごとに通常値・NULL・空・境界・衝突ペアを含むbyte vectorを揃える。
- Namespace調査・承認前はUUID期待値を確定せず、UUIDv5合格を宣言しない。

### SR-08 — Entity完全属性・制約表が未完成
**重大度: HIGH**

該当: §10、§12。

現状は最低契約にとどまり、全Entity属性、型、NULL、PK/UK、CHECK、FK、複合FK、多態参照、削除/更新規則が揃っていない。「正値等」もRevision 0を許すEntityとOrdinal 1開始のEntityが混在し得るため曖昧。

修正方針:
- 全Entityについて属性・型・NULL・キー・参照先・一意性・範囲・削除/更新規則を一覧化する。
- Revision/Ordinalの開始値と単調増加条件をEntityごとに明示する。
- 物理実装方式へ持ち越す事項と、論理設計段階で確定する事項を分離する。

### SR-09 — Session Status導出式と状態遷移が未定義（旧所見・CC-01で解決）
**状態: SUPERSEDED / Issue #210 CC-01**

初回レビュー時の「Measurement集合からSession Statusを導出する」旧案は、Issue #210の統括決定により不採用。Session Lifecycle（NOT_CREATED / OPEN / CLOSED / QUARANTINED）とMeasurement Outcome（COMPLETE / STOP / ERROR / CANCEL / INCOMPLETE / UNKNOWN）を完全分離し、Outcome集合・混在・件数からLifecycleを導出しない。CLOSEDはRun管理側の明示Close Operationと外部正本・依存参照の検証が成立した場合に限る。詳細はMain draft §1.4.1、`V083_SESSION_LIFECYCLE_OUTCOME_DRAFT.md`、State Transition Matrixを参照。

### SR-10 — DB-001〜124 / V082 crosswalkは証拠回収未完了
**重大度: BLOCKER / 統括再提出条件**

既存の124行台帳とV082-001〜053の53行クロスウォークは枠組みとして作成済みだが、DB-001〜124個別原文は未回収が多く、対応付けも全件未対応付け。重複なし・未カバー確定を意味しない。個別原文・出典・正式性・現行性を回収できた項目からのみ更新する。

### SR-11 — Motor / Battery契約照合は未完了
**重大度: HIGH / 統括再提出条件**

- Motor: Issue #35を唯一の現行契約として維持。DB側の耐久性・RawLog・Session・Artifact規定が現行契約を上書きしないよう照合する。
- Battery: DB部門はBattery実装変更・Battery担当への直接連絡を行わない。CH1/CH2独立性等のBattery論点は統括経由の担当範囲とする。DB側では最終測定/RawLog契約の受領・照合状態のみを記録する。

## 3. 状態遷移の初回検査結果

| 対象 | 確認結果 | 次に必要な作業 |
|---|---|---|
| DB Run | 初回ASSIGNEDで生成、生成後保持、再ASSIGNEDで同一IDを使う方針は一貫 | DB record生成とDB file/schema/bootstrapを明確に分離 |
| Session | 初回ASSIGNEDで生成し、Assignment変更後も保持 | CC-01に従いLifecycle/Outcome分離。NONE Association時の既存Session membership条件を別途定義 |
| Assignment | Current AssignmentとAssignment-at-Measurementの分離は妥当 | NONE/ANONYMOUSの既存履歴・プライバシー処理境界を明文化 |
| Current Aggregate | 現在ASSIGNED、測定時ASSIGNED、Instance ID一致という基準は一貫 | Request ID/Algorithm/Configuration/Assignment Snapshotを含む完全Fingerprintで有効性判定 |
| Receipt | Source Commit後ABORTED禁止、同一Operation再開は一貫 | Event遷移・Restore時の未完了状態・ABORTED証拠条件を表形式で完成 |
| Artifact DAG | 不変・循環禁止・Hash検証方針は一貫 | 多態参照の全Entity型・削除/更新規則を完全表へ反映 |

## 4. 次の作業順

1. Issue #201 / #85 / #86との範囲整合を反映する修正方針を確定（後日Association・Bootstrapの現行許可を除外）。
2. Session membership / Assignment / Aggregateの状態遷移表を完成。
3. Receipt Envelope/Event状態遷移・クラッシュ・Restore回復表を完成。
4. Aggregate Request Fingerprint / Pointer / Retry終端規則を完成。
5. Issue #35とRawLog耐久性の分類・Motor契約照合。
6. Canonical Binary Name v2の完全文法・全Entity byte vectors・Namespace調査。
7. Entity完全属性・制約表。
8. DB-001〜124の一次資料探索とV082 crosswalk更新。
9. 全項目の自己検証後にIssue #209へ再提出。統括承認前に物理設計・実装へ進まない。

## 5. 変更・実施状況

- 本レビューはGitHub Issue / 設計文書の読み取り照合。
- main、v0.8.2、運用DB、DBファイル、DDL、Migration、実装コードへの変更なし。
- 実装テスト・DB生成・Restore実行・物理試験は未実施。
- 統括承認なし。ユーザー作業なし。


## 6. Decision Overlay — Issue #210（2026-11-21）

| 初回所見 | 現在の扱い | 決定・残作業 |
|---|---|---|
| SR-01 | 部分解決 | CC-02でANONYMOUS後日取込禁止、NONEの既存DB管理Measurementに限る明示Associationを分離。資料同期の残りを監査 |
| SR-02 | 要再定義 | NONE Association対象MeasurementのSession membership条件が残る。ANONYMOUSは後付け所属禁止 |
| SR-09 | 解決・旧案廃止 | CC-01によりSession LifecycleとMeasurement Outcomeを完全分離。OutcomeからLifecycleを導出しない |

このDecision Overlayは初回レビューの履歴を消去せず、現行規範判断を上書き表示する。CC-01 / CC-02以外の未解決事項、v0.8.3全体の未承認状態、物理設計・実装禁止を変更しない。
