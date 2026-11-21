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

初回レビュー時の「Measurement集合からSession Statusを導出する」旧案は、Issue #210の統括決定により不採用。Session Lifecycle（NOT_CREATED / OPEN / CLOSED / QUARANTINED）とMeasurement Outcome（COMPLETE / STOP / ERROR / CANCEL / INCOMPLETE / UNKNOWN）を完全分離し、Outcome集合・混在・件数からLifecycleを導出しない。CLOSEDはRun管理側の明示Close Operationと外部正本・依存参照の検証が成立した場合に限る。詳細はMain draft §1.4、`V083_SESSION_LIFECYCLE_OUTCOME_DRAFT.md`、State Transition Matrixを参照。

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


## 7. Motor / Battery正式契約の再照合（2026-11-21）

### 7.1 Motor — Issue #35（唯一の現行仕様正本）

参照: [Issue #35](https://github.com/hamtech86/mini4wd-ai-system/issues/35)

Issue #35本文を読み、DB側の契約と境界を次のとおり再確認した。

| 領域 | Issue #35で確認できた正本契約 | DB設計への影響 / 未確定 |
|---|---|---|
| RawLog v1 | 歴史的実測資料として原本保全。改変・削除・自動変換・推測変換・再分類しない | DB側でv1を新スキーマへ自動変換しない |
| RawLog v2 | 現行測定目的・現行HW/配線/FWから独立設計。v1列/全項目継承義務なし。JSONL等の具体保存形式・必須任意fieldはIssue #170で定義し統括承認 | DB側は未承認のv2 schemaを推測しない。DB Measurement / RawLog Referenceが参照する正式schema version・identityは未受領 |
| 取得値 | A0巻線電流、A1独立ブラシ観測、A4/A5電圧、A2/A3参考値。A0/A1平均禁止、A2/A3を制御・判定に使用禁止 | Measurement Sample / Profile Snapshotにセンサー意味を混同したfieldを設けない。正式なv2 field listは未受領 |
| RawLogとAnalysis | 個体推定に生ログ使用。推定値をRawLogへ混入しない。Analysisは別途算出・推定 | Artifact InputがRawLog/Sample/Algorithmをどう参照するかはDB論理候補にあるが、Motor側正式Artifact contractはIssue #35本文にない |
| 欠損・耐久性 | 初期段階のTelemetry/RawLog欠損は頻度・範囲を記録したうえで許容可能。全サンプル完全保存を安全要件として目的化しない | DB草案§8の全RawLog一律fsync/hash/atomic durability要求は適用範囲の分類が必要。全種類へ一律適用しない |
| Session / Instance | Issue #35本文には、共通DBのSession ID発行・Session membership・Assignment Snapshot・遅延Associationの正式データ契約なし | DB側でMotor固有の不足属性・FK・Session semanticsを補完してはならない。共通DB統括決定を待つ |
| Device identity | INFOのIDはFW内部識別文字列であり、物理デバイス固有IDでもMotor Instance IDでもない | Device IDをMotor Instance IDやDB Entity IDへ流用しない |

### 7.2 Battery — Issue #16（E2E検証タスクであり完全データ契約ではない）

参照: [Issue #16](https://github.com/hamtech86/mini4wd-ai-system/issues/16)

Issue #16で確認できるのは、main統合済みと記述された旧Battery Database + Benchmark Analysisに対するE2E検証タスクである。5A DATA取り込み、CH1/CH2独立Session、Measurement保存、Feature Extraction、Benchmark Result保存、mAh/Wh/電圧降下の妥当性、Measurement不変性を検証対象としている。一方、同IssueはArduino FW変更なし、内部抵抗算出なし、評価スコア基準確定なし、STARTALLのCH1/CH2合算なしと境界を定める。

このIssueだけから、以下を新DBの正式契約として確定することはできない。

- Battery Model / Instance / Profileの完全属性・identity・Family制約。
- CH1/CH2の共通Run配下Scope表現、Session生成・閉鎖条件、Assignment Snapshot semantics。
- Measurement OutcomeとSession Lifecycleの関係（現在はCC-01が優先）。
- RawLog v2 schema、Sample Locator、Channel metadata、Capture終端イベント。
- Benchmark Feature / Resultの完全schema、Algorithm/Configuration version、Artifact provenance。
- NONE late associationのSession membership、ANONYMOUSの後日取込禁止に関する例外の有無（現行CC-02に例外なし）。

### 7.3 共通DB側の契約受領状況

| 対象 | 正式根拠 | DB側で確定してよいこと | 未受領・禁止 |
|---|---|---|---|
| Motor | Issue #35 | RawLog v1/v2の境界、センサー意味、推定値とRawLogの分離、Telemetry欠損許容、Device IDの意味 | Motor固有DB schema、Session/Assignment完全契約、Artifact schemaを補完しない |
| Battery | Issue #16 | E2E検証の対象・境界とCH1/CH2独立性の検証要求 | Issue #16を完全データ契約と見なさない。Battery担当へ直接指示・実装変更しない |
| Shared DB | Issue #210 CC-01/CC-02、Issue #201等 | Session Lifecycle / Outcome分離、NONEとANONYMOUSの境界 | NONE Session membershipの統括決定がない限り関連付け規則を確定しない |

**結論:** Motorの正本契約はDB側で上書きしない。Batteryの現存IssueはE2E taskにとどまり、新DBの完全データ契約としては不足する。両者の不足をDB部門が推測で埋めず、統括経由で正式契約を受領する必要がある。これは契約照合であり、Motor/Battery実装の変更指示ではない。


## 8. DB-001〜124 Evidence Disposition Overlay（2026-11-21）

Evidence Ledger §12の未回収ID処理方針を、本自己検証記録にも適用する。

### 8.1 既知の来歴と未回収範囲

- DB-001〜056: 2026-11-18のv0.2レビューで扱った従来56項目。個別短縮定義は過去会話から再回収済み。原本文書・正式承認・番号付きテスト実物は未回収。
- DB-057〜078: 2026-11-19「新DB設計書 v0.2」で追加された範囲として会話履歴上確認。個別本文・原本・承認・テスト実物は未回収。
- DB-079〜109: 統括の維持・保全指示履歴を確認。個々の試験実物の存在証明とは区別する。
- DB-110〜124: 統括の追加指示履歴を確認。個々の要件・テスト完成の証明とは区別する。
- DB-125〜154: 正式番号として扱う根拠がなく、既存試験扱いを撤回済み。既存IDとして追加しない。
- DB-155〜176: 提案番号は撤回済み。再利用せず、残存内容があればIDなし候補メモに限る。

### 8.2 未回収項目の運用

DB-001〜124は履歴をEvidence Ledgerに保持し、個別原文・承認・テスト実物が未回収の項目を次の状態で凍結する。

- Content Status = NOT_RECOVERED
- Approval Status = NOT_VERIFIED
- Test Artifact Status = NOT_VERIFIED
- Operational Disposition = REFERENCE_ONLY_NOT_EXECUTABLE

これらを現行受入のPASS/FAIL対象にせず、欠けた要求本文・期待結果を推測で補完しない。旧IDを新規テストへ転用せず、旧IDとのTraceabilityは直接証拠がある場合だけ記録する。新規テストは承認済み仕様を根拠に独立IDとして提案し、統括承認後に採番する。

NOT_CREATED_CONFIRMED / RETIRED_NOT_CREATEDへの変更は、個別成果物が作成されなかったことを直接示す証拠がある場合に限る。検索0件は不存在証明ではない。

### 8.3 証拠探索の終了条件

既知の保存先・会話履歴・Issue/PR・Libraryを探索しても個別証拠が得られない場合、同一範囲の反復探索は終了し、参照専用・実行不可として凍結する。新しい保存先情報、具体的な出典、一次資料が提示された場合に限り再開する。

### 8.4 審査への影響

このOverlayは証拠管理上の処理であり、旧要件の正式承認・廃止、V082 crosswalkの完了、現行受入条件の変更、v0.8.3承認を意味しない。SR-10の未解決事項のうち、旧ID来歴の証拠管理と未回収時の暫定処理は本Overlayで整理したが、個別原文・正式性・V082対応・実装トレーサビリティは未解決のまま残す。物理設計・DDL・DB生成・Migration・Restore実行・実装・PR・main反映の禁止を維持する。


## 9. 2026-11-21 DB-RV横断照合の追加所見

### SR-12 — NONE AssociationとSession membershipの境界が未定義
**重大度: HIGH / DB-RV-01・02・08**

Issue #210 CC-02はNONE期間の既存DB管理Measurementについて明示Associationを許容する一方、Session membershipの条件・関連付け先Sessionの適格性は決めていない。Main §1.2(6)の「Session生成後にDBへ登録されたMeasurement集合」と、NONE Associationの関係が未定義。Session生成前のNONE Measurementと、Session生成後のNONE Measurementを分け、membership / audit-only / exclusionのどれかを統括判断対象として明確化する。ANONYMOUSは後日取込・membership追加とも禁止。

### SR-13 — Aggregate Request FingerprintがMainと補助Matrixで不一致
**重大度: HIGH / DB-RV-04**

Main §3.2 / §3.3はCurrent Validの主条件をInput Set Hash一致としている。一方State Matrix §5.1はRequest ID、Scope / DB Run、Input Set Hash、Assignment Snapshot Set Hash、Algorithm / Configuration Version、Measurement / Profile / Policy Revision、Aggregate Definition Versionを含むFingerprintを要求する。Mainへ同期する前にFingerprintの完全Field集合・順序・Hash対象と、Latest Successfulの順序、Retry Closedの証拠を決定する必要がある。

### SR-14 — Artifact / SimulationのEntity境界とPolymorphic Inputが未完成
**重大度: HIGH / DB-RV-05**

Main §4はDAG不変性・循環拒否・Input Set Hashの骨格を定義するが、Entity InventoryではAnalysis Artifact / Simulation Artifactの共通性、Artifact Inputの全InputType・参照Entity型・Role / Ordinal / NULL / uniqueness、IDとPayload Hashの区別が未定義。一般的なpolymorphic FK方式を推測採用しない。

### SR-15 — Canonical Identity Schemaの対象範囲不足
**重大度: BLOCKER / DB-RV-06**

Main §5.3の11 Schema rowsはEntity Inventory 23種の全体を覆わない。直接対応10種、未定義13種、OPERATION_EVENTのInventory対応未確定。29 Expected Hexの構造検査29/29通過はbyte syntaxの検査であり、Entity domain / UUIDv5 / Namespace / 2実装一致を証明しない。23 EntityのIdentity分類・完全Field Schema・boundary vectorsが閉じるまでCanonicalization完了としない。

### SR-16 — External Source / DB Mirror / RestoreのEntity単位契約が未完成
**重大度: HIGH / DB-RV-07**

外部正本優先・DB Mirror再生成の基本方針はあるが、Entityごとの完全なAuthority、Restore Phase A/B証拠、Mirror再生成可能性、RawLog durabilityの種別境界が未完了。Issue #35のTelemetry欠損許容を無視して全RawLogへ一律完全耐久性を要求しない。Motor/Battery正式契約を統括経由で受領してから照合する。

### SR-17 — DB-001〜124 / V082のトレーサビリティ未確定
**重大度: BLOCKER / 統括再提出条件**

DB-001〜056は会話由来短縮定義のみ、DB-057〜124は個別本文未回収。V082-001〜053は全件未対応付けで、確定対応・部分対応・重複・未カバー確定は各0。これは試験が存在しない・要件がないという意味ではない。原文未回収IDは参照専用・実行不可で凍結し、DB-032等の旧期待値はCC-02との競合を明示する。DB-007のNONE Session意味は原文確認まで未決定。


## 10. Motor / Battery / Anonymous正式契約の照合結果（2026-11-21）

### SR-18 — Device-specific Data ContractをDB側で補完できない
**重大度: HIGH / DB-RV-07・08・統括再提出条件**

Issue #35はMotorの現行仕様唯一の正本であり、未記載事項を担当側で復元しない権限境界がある。RawLog v1 / v2は別形式、v2の完全Schemaは別の正式決定を要する。Issue #16はBattery E2E検証タスクであり、完全なBattery DB / RawLog契約ではない。DB部門はRawLog v2、Battery Channel metadata、Capture終端、durability / retentionを推測で補完しない。Issue #201 / #210に従いAnonymous RawLogの後日DB取込は禁止、NONE Associationは限定許容だがSession membershipは未決定。Motor/Batteryの実装変更や担当への直接指示は行わない。


## 11. SR-19 — Entity別の一次根拠・Authority・契約所有者が未完
**重大度: HIGH / DB-RV-01〜08横断 / 統括再審査条件**

Entity Inventory 23種をMain §§1–10および利用可能な正式Issueへ照合し、根拠所在と契約責任境界を整理した。

- Main §§6–9に正本 / Mirror、Measurement Envelope、RawLog保存、Restore手順の論理案はあるが、各Entityの完全Field Schema、NULL / key / retention、Restore実証までは揃っていない。
- Motor Issue #35 / #170はRawLog v1/v2の境界とv2契約の作業範囲を定めるが、DB部門が未記載Fieldやdurabilityを補完する権限はない。
- Battery Issue #16はE2E検証タスクであり、Battery固有の完全DB / RawLog / Capture終端 / durability / retention契約ではない。
- OPERATION_EVENT、Assignment Event、Intent、Receipt Eventの境界は未決定。Analysis / Simulation Artifact、Recovery Operation / Integrity Reportも完全な独立Entity契約は未完。
- NONE Session membershipはIssue #210で未決定のため、A/B/Cいずれも採用仕様として扱わない。

**対応:** Entity Inventory §10とCross-document Audit §32に根拠・Authorityマップを追加。未回収項目は未定義として維持し、DB部門による推測補完を禁止する。

**残件:** 各契約所有者から正式なField Schema / lifecycle / retention / Restore evidenceを受領すること。UUIDv5 Namespace・Canonicalization、DDL、物理設計、DB生成、Migration、Restore実行、実装、PR、main反映の承認境界は変更なし。


## 12. SR-20 — Aggregate Request Fingerprint / Retry終端 / Pointer順序がMainで未完
**重大度: HIGH / DB-RV-04 / 統括再審査条件**

Main §3とState Matrix §5の読み合わせで、Current Valid判定がInput Set Hash中心かRequest Fingerprint全体か、Latest Successfulの順序、Retry Closedの証拠と権限、Pointerの同時更新・再構築が未同期と確認した。

**対応:** Entity Inventory §11とCross-document Audit §33へ、Fingerprint identityとRequest identityの分離、未決定の代替案、最低限維持できる不変条件を記録した。

**決定待ち:** Request IDをFingerprintに含めるか、Full fingerprint fieldsを保存するか、Attempt / Result順序キー、Retry Closed Event / authority、Pointer concurrency。Main §3は未変更。State Matrix候補を承認仕様に昇格させていない。


## 13. SR-21 — RawLog durability要求のEntity別実行契約が不足
**重大度: HIGH / DB-RV-07・08 / 統括再審査条件**

Main §8にRawLogのfsync / read-back hash / Atomic Rename / Journal completion / PENDING_RECOVERY条件がある一方、RawLog ID authority、Expected Hash byte scope、Path grammar、Temp ownership、completion Event schema、Recovery authority、retention / loss toleranceは未定義。

Motor Issue #35 / #170はv1/v2形式境界とv2契約の作業範囲を定めるが、Main §8の全Filesystem durability保証が確定した証拠はない。Battery Issue #16もBattery RawLog durability契約ではない。

**対応:** Entity Inventory §12とCross-document Audit §34に論理・物理・機器別・Restoreの4受入ゲートを分離して記録。FS durabilityを実証済みと扱わず、Batteryへ同一方式を推測適用しない。

**残件:** RawLog Object / Referenceの完全Identity・Hash・Path・Retention、機器別契約、OS/filesystem実証、Recovery authority。Main §8は未変更。

## SR-22 — v0.8.3論理Decision Baselineの全項目確定
**判定: 設計選択の未決定は解消 / 実装・証拠Gateは未完**

Main §14を追加し、UUIDv4 / M4W-JCS-1、Run/Session/Assignment、NONE/ANONYMOUS、Outcome/Close、Operation/Receipt/Writer/Recovery、Aggregate/Artifact、RawLog/Restore、Entity境界、Legacy IDの取扱いを採用・不採用・対象外・fail-closedへ確定した。

特にUUIDv5 / Canonical Binary Name v2、Receipt ID deterministic derivation、Expected Receipt Hash、Expected DB Marker Hashをv0.8.3から除外した。未知のField / Schema / Device contractはopaque保全のみとし、意味解析・Aggregate入力を禁止する。

**Recovery Authority:** Bootstrap登録済みPROJECT_RECOVERY_ADMINのみ。v0.8.3では元証拠不変・QUARANTINED解除禁止。

**残存Gate:** Motor/Battery正式契約の回収、Run Manager Close契約、対象OS/filesystem durability実証、SQLite transaction / crash recovery実証、論理受入試験実行、統括最終審査。これらを設計未決定と呼ばず、未実証 / 未承認として明示する。

### SR-22 補足 — Battery 5A DATAの保存範囲
Battery Issue #16に基づき、5A DATA原本byte・共通Measurement Envelope・CH1 / CH2独立保存は許可。未知RawLog Payloadはopaque保全のみとし、Feature Extraction / Benchmark再計算 / mAh・Wh・電圧降下の妥当性判定は正式契約受領まで禁止。
### SR-22 補足 — Aggregate Attemptの終端
Request StateとAttempt StateをMain §3.2で固定。Retry ClosedはFAILED Attemptあり・RUNNINGなしの場合のみ。Attempt CANCELLEDとRequest Cancelledを分離。結果不明crashはWorker fencing proof前にAggregate OwnerをQUARANTINEDとし、更新を停止。

## 36. Supersession Register — 旧OPEN / TBD記述の最終処置（2026-11-21）

**規範優先順位:** COMMON_DB_LOGICAL_DESIGN_v0.8.3_REMEDIATION_DRAFT.md §14（DB-RV-04は§3、DB-RV-05は§4、DB-RV-06は§5、RawLog durabilityの論理条件は§8）が現行Decision Authority。本書の§1〜§34にあるOPEN / TBD / candidate / decision pendingは調査時点の履歴であり、現行設計判断としては適用しない。矛盾時はMainの該当条項を優先する。

| 論点 / DB-RV | 最終状態 | 決定根拠 | 残るもの（設計未決定ではない） |
|---|---|---|---|
| DB-RV-01 Entity / identity | 決定済み | Main §§5.1, 5.3, 14.3 | 23概念の完全SQL列定義は本論理版対象外。契約未受領Payloadはopaque |
| DB-RV-02 Run / Session / Assignment / NONE | 決定済み | Main §14.1–14.3 | Run Manager / Session Managerの実装・権限試験 |
| DB-RV-03 Journal / Receipt / Recovery | 決定済み | Main §14.4、Receipt Contract §22 | filesystem append/fsync、Epoch fencing、SQLite crash/recoveryの実証 |
| DB-RV-04 Aggregate | 決定済み | Main §§3.1–3.3, 14.5 | Aggregate Manager/Worker実装と競合・crash受入試験 |
| DB-RV-05 Artifact DAG | 決定済み | Main §§4, 14.3, 14.5 | Kind別Payload契約受領と検証器試験。未知Kindはopaque / reject |
| DB-RV-06 ID / Hash / Canonicalization | 決定済み | Main §§5.1–5.3, 14.3 | UUIDv4 / JCS conformance試験。UUIDv5 / CBN v2は不採用 |
| DB-RV-07 RawLog / Restore | 論理境界決定済み | Main §§8, 14.6–14.8 | 機器別RawLog契約、OS/filesystem durability、Restore実証 |
| DB-RV-08 Cross-evidence / durability | fail-closed決定済み | Main §§8–9, 14.4, 14.7–14.8 | 対象環境でのSQLite / filesystem / crash試験 |

### 36.1 過去の未決定記述の置換規則
1. NONE Session membershipのA/B/C案は不採用。Main §14.1(4)–(7)のScope単位・Session存在条件・DB availability・ANONYMOUS禁止境界を採用。
2. UUIDv5 / Canonical Binary Name v2 / Namespace案は不採用。UUIDv4とM4W-JCS-1を採用。
3. Receipt ID deterministic derivation / Expected Receipt Hash / Expected DB Marker Hashは不採用。Main §14.4およびReceipt Contract §22の順序を採用。
4. Writer / Recovery / Event Type AuthorityはMain §14.4のAuthority Registry / EventType別発行権限に固定。物理fencing方式は指定せず、証明不能な実装を受入不可とする。
5. Aggregate Fingerprint / Retry / Result / PointerはMain §§3.1–3.3および§14.5に固定。旧選択肢は採用しない。
6. Artifact InputType / Link Role / Ordinal / RequiredはMain §14.5に固定。発行元ContractにないRoleや未知InputTypeは拒否。
7. RawLog完全Field Schema、機器固有Capture終端、Retention / loss toleranceはDB部門が創作しない。v0.8.3ではopaque保存とfail-closedのみを許可し、正式契約受領後の改訂事項とする。
8. 未回収DB-001〜124 / V082番号はREFERENCE_ONLY_NOT_EXECUTABLE。推測MappingはNO_MAPPING。存在しないと断定せず、根拠が届いた場合だけ再審査。

### 36.2 完了判定の分離
- **設計選択:** 本表によりOPEN / TBDを閉じた。
- **契約証拠:** Motor / Battery / Run Managerからの正式Schema・Lifecycle・Capture終端・Close authorityは未受領のものがある。未受領項目は本版の適用対象外またはopaque/fail-closedであり、他部門仕様を推測しない。
- **実証:** UUID/JCS、filesystem、SQLite、crash recovery、Restore、Concurrencyの受入試験は未実施。
- **承認:** v0.8.3はDraft。統括最終承認・実装許可・DDL/DB生成/Migration/Restore実行/PR/main反映を意味しない。


## 37. DB部門追補自己審査 — CC-02 / DB unavailable / Session membership（2026-11-21）

### SR-12 / SR-16 / SR-18の閉鎖
1. Issue #210 CC-02が許可したNONE後日Associationを、既存DB管理Measurementに対する明示的なInstance関連付け履歴として定義した。AssociationはAssignment-at-Measurementを変更せず、Current Aggregateへ算入せず、Session membershipも変更しない。
2. Session membershipはMeasurement Mirror初回登録時点で同一Physical Run / ScopeのSessionが存在する場合に固定する。Session生成前のNONE Measurementは後日の初回ASSIGNED後もSessionへ遡及所属しない。Session生成後のNONE Measurementは登録時点でmembershipを固定する。
3. NONE AssociationのEvent Authorityは、Session Entityの存在有無で発行権限を失わないよう、当該Physical Run / Scopeの認証済みDB Session Managerとした。これはEvent発行Authorityの論理定義であり、実装・権限実証済みを意味しない。

### Issue #201との矛盾修正
4. DB unavailableはIssue #201のAnonymous Modeとして扱う。障害期間中に取得されたCapture / Measurement / RawLogはAssignment-at-MeasurementがASSIGNEDであっても外部正本のみとし、復旧後のBootstrap / DB取込 / Mirror化 / Associationを禁止する。
5. 障害前から存在するDB Run / Sessionは削除しない。障害期間中のCaptureは既存Sessionへ追加しない。
6. 同一Physical Run内で障害中に初回ASSIGNEDとなった場合、復旧後にそのRunを遡及してDB管理へ変換しない。同一Run内のDB管理再開契約は本版で定義せず、新しいPhysical RunからDB管理を開始する。障害前にDB Run / Sessionが存在した場合はIdentityを保持するが、障害中Captureを既存Sessionへ追加しない。

### 文書同期
- Main v0.8.3 §1.1–1.4 / §6 / §14.1 / §14.4.17
- Session Lifecycle §§1 / 4 / 5 / 6 / 7
- State Transition Matrix §§1 / 2 / 3
- Entity Inventory §§13.2–13.3
- Cross-document Consistency Audit §37

### 実施状態
- 論理文書修正: 実施
- DB-001〜124原文回収 / V082 Crosswalk完全照合: 未完了（未回収は未回収のまま維持）
- Motor / Battery正式Capture・RawLog契約受領: 未完了
- UUIDv4 / M4W-JCS-1 conformance test vectorsの実行: 未実施
- Filesystem / SQLite / crash / Restore実証: 未実施・禁止境界内
- 統括最終審査: 未実施

本追補は設計全体の承認・実装移行許可ではない。