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

初回レビュー時はNONE AssociationとSession関係の境界が未定義だった。2026-11-22の統括決定CC-03によりMeasurement→Session直接関係は不採用となり、NONE AssociationはInstance関連付けEventのみと確定した。

修正方針:
- SR-01のとおり後日Associationを本版から外す場合、Sessionの通常所属条件を「Session生成後に測定・登録され、測定時Assignmentが当該ScopeのASSIGNED状態であるMeasurement」として定義する。
- 将来Associationを再設計する場合も、Measurement→Session直接関係を追加せず、Assignment-at-MeasurementとInstance関連付けEventを分離する。

### SR-03 — DB Run/Session生成とDBファイル生成・Bootstrapの境界
**重大度: BLOCKER / 誤読防止**

該当: §1.1〜1.3、§6、§9。

「DB正常利用可能時の最初の有効ASSIGNED OperationでDB Run / Logical Session identity / DB Session Mirrorを生成する」という記述は、既存の承認済みDB内にMirrorレコードを作る意味である。DB unavailable期間はAnonymous Modeであり、有効ASSIGNED Operation・新規Session生成を行わず、DBファイル、schema、空DB、migration、Bootstrapを自動生成しない。

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
| DB Run | DB正常利用可能時の初回有効ASSIGNEDで生成、生成後保持、再ASSIGNEDで同一IDを使う方針は一貫 | DB record生成とDB file/schema/bootstrapを明確に分離。outage中の初回ASSIGNEDは無効 |
| Session | DB正常利用可能時の初回有効ASSIGNEDで生成し、Assignment変更後も保持 | CC-01に従いLifecycle/Outcome分離。DB unavailable中の新規Session生成は禁止。CC-03によりMeasurementとの直接所属関係なし |
| Assignment | Current AssignmentとAssignment-at-Measurementの分離は妥当 | NONE/ANONYMOUSの既存履歴・プライバシー処理境界を明文化 |
| Current Aggregate | 現在ASSIGNED、測定時ASSIGNED、Instance ID一致という基準は一貫 | Request ID/Algorithm/Configuration/Assignment Snapshotを含む完全Fingerprintで有効性判定 |
| Receipt | Source Commit後ABORTED禁止、同一Operation再開は一貫 | Event遷移・Restore時の未完了状態・ABORTED証拠条件を表形式で完成 |
| Artifact DAG | 不変・循環禁止・Hash検証方針は一貫 | 多態参照の全Entity型・削除/更新規則を完全表へ反映 |

## 4. 次の作業順

1. Issue #201 / #85 / #86との範囲整合を反映する修正方針を確定（後日Association・Bootstrapの現行許可を除外）。
2. Measurement→RUN_SCOPE / Session独立Lifecycle / Assignment / Aggregateの状態遷移表をCC-03に同期。
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
| SR-02 | SUPERSEDED / NOT_ADOPTED | 旧NONE MeasurementのSession membership論点はCC-03で解消。Measurement→Session直接関係なし |
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
| Session / Instance | Issue #35本文には、共通DBのSession ID発行・Measurement→Session直接関係・Assignment Snapshot・遅延Associationの正式データ契約なし | DB側でMotor固有の不足属性・FK・Session semanticsを補完してはならない。共通DB統括決定を待つ |
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
- NONE late associationはInstance関連付けEventのみ。Measurement→Session直接関係なし（CC-03）。ANONYMOUS後日取込禁止。

### 7.3 共通DB側の契約受領状況

| 対象 | 正式根拠 | DB側で確定してよいこと | 未受領・禁止 |
|---|---|---|---|
| Motor | Issue #35 | RawLog v1/v2の境界、センサー意味、推定値とRawLogの分離、Telemetry欠損許容、Device IDの意味 | Motor固有DB schema、Session/Assignment完全契約、Artifact schemaを補完しない |
| Battery | Issue #16 | E2E検証の対象・境界とCH1/CH2独立性の検証要求 | Issue #16を完全データ契約と見なさない。Battery担当へ直接指示・実装変更しない |
| Shared DB | Issue #210 CC-01/CC-02、Issue #201等 | Session Lifecycle / Outcome分離、NONEとANONYMOUSの境界 | CC-03によりMeasurement→Session直接関係は不採用。NONE AssociationはInstance関連付けEventに限定 |

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

### SR-12 — NONE AssociationとSession membershipの境界が未定義（HISTORICAL / SUPERSEDED by CC-03）
**重大度: HIGH / DB-RV-01・02・08**

（2026-11-21時点の履歴。2026-11-22の統括決定CC-03によりSUPERSEDED。）現行規範ではMeasurement→Session直接FK / membership / session_idを設けない。MeasurementはRUN_SCOPEへ直接属し、Sessionは同じRUN_SCOPE配下の独立Lifecycle Entity。NONE AssociationはInstance関連付けEventのみ。ANONYMOUSは後日取込禁止。

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

Issue #35はMotorの現行仕様唯一の正本であり、未記載事項を担当側で復元しない権限境界がある。RawLog v1 / v2は別形式、v2の完全Schemaは別の正式決定を要する。Issue #16はBattery E2E検証タスクであり、完全なBattery DB / RawLog契約ではない。DB部門はRawLog v2、Battery Channel metadata、Capture終端、durability / retentionを推測で補完しない。Issue #201 / #210に従いAnonymous RawLogの後日DB取込は禁止。NONE AssociationはInstance関連付けEventのみ。CC-03によりMeasurement→Session直接関係は不採用。Motor/Batteryの実装変更や担当への直接指示は行わない。


## 11. SR-19 — Entity別の一次根拠・Authority・契約所有者が未完
**重大度: HIGH / DB-RV-01〜08横断 / 統括再審査条件**

Entity Inventory 23種をMain §§1–10および利用可能な正式Issueへ照合し、根拠所在と契約責任境界を整理した。

- Main §§6–9に正本 / Mirror、Measurement Envelope、RawLog保存、Restore手順の論理案はあるが、各Entityの完全Field Schema、NULL / key / retention、Restore実証までは揃っていない。
- Motor Issue #35 / #170はRawLog v1/v2の境界とv2契約の作業範囲を定めるが、DB部門が未記載Fieldやdurabilityを補完する権限はない。
- Battery Issue #16はE2E検証タスクであり、Battery固有の完全DB / RawLog / Capture終端 / durability / retention契約ではない。
- OPERATION_EVENT、Assignment Event、Intent、Receipt Eventの境界は未決定。Analysis / Simulation Artifact、Recovery Operation / Integrity Reportも完全な独立Entity契約は未完。
- 旧A/B/C Session membership案はCC-03によりSUPERSEDED / NOT_ADOPTED。Measurement→Session直接関係を設けない。

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
| DB-RV-01 Session存在条件とAssignment State | CC-01 / CC-03論理判断済み・文書同期 | Main §1 / §14.1（Session生成・保持、MeasurementはRUN_SCOPE直結） | Session Manager実装・権限試験。v0.8.3全体承認とは別 |
| DB-RV-02 DB Run生成後ライフサイクル | DB部門案あり・統括承認待ち | Main §1（DB Run生成・保持・再割当条件） | Run Manager実装・権限試験 |
| DB-RV-03 Receipt PREPARED永続化順序 | DB部門案あり・統括承認待ち | Main §2、Receipt Contract §22（Main優先） | filesystem / SQLite crash・durability・Recovery実証 |
| DB-RV-04 Aggregate要求履歴 / Revision | DB部門案あり・統括承認待ち | Main §3 | Aggregate Manager / Workerの実装・競合・crash受入試験 |
| DB-RV-05 Artifact DAG / 再解析不変性 | DB部門案あり・統括承認待ち | Main §4 | Kind別Payload契約受領と検証器試験。未知Kindはopaque / reject |
| DB-RV-06 UUIDv5 Canonical Input（旧要求） | 旧UUIDv5案を不採用とする変更案・統括承認待ち | Main §5（UUIDv4 / M4W-JCS-1案） | JCS適合試験、Entity別入力・期待Hash vector、Namespace不採用の統括確認 |
| DB-RV-07 外部正本とDB Entity / Mirror境界 | DB部門案あり・統括承認待ち | Main §6、§8 | 機器別Capture / RawLog契約、OS / filesystem durability、Restore実証 |
| DB-RV-08 AssignmentとAggregate対象範囲 | DB部門案あり・統括承認待ち | Main §1、§7 | NONE / ANONYMOUS対象条件とAggregate / Pair Analysisの正式契約照合 |

**番号対応の拘束:** DB-RV-01〜08はIssue #209の元定義を固定して使用する。上表のIDと意味を別の論点へ転用しない。Entity / identity inventoryは横断的な設計資料であり、独立したDB-RV番号ではない。新規の統括差戻し論点はV083-RV-01等の別系列で追跡する。表中の「DB部門案あり」は統括承認・実証完了を意味しない。

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


## 37. DB部門追補自己審査 — CC-02 / DB unavailable / Session membership（HISTORICAL / SUPERSEDED by CC-03, 2026-11-22）

### SR-12 / SR-16 / SR-18の閉鎖
1. Issue #210 CC-02が許可したNONE後日Associationを、既存DB管理Measurementに対する明示的なInstance関連付け履歴として定義した。AssociationはAssignment-at-Measurementを変更せず、Current Aggregateへ算入せず、Session membershipも変更しない。
2. Session membershipはMeasurementを外部Run Manifestへ初回確定記録した時点で同一Physical Run / Scopeの論理Session identityが存在する場合に固定する。DB Mirrorの有無はmembershipの事実を変えない。Session生成前のNONE Measurementは後日の初回ASSIGNED後もSessionへ遡及所属しない。Session生成後のNONE Measurementは登録時点でmembershipを固定する。 採用理由は既存の「Session生成後に登録されたMeasurement集合」という規則の維持と、存在しないSessionへの遡及接続防止。不採用案は、(A)初回ASSIGNED時の過去NONE自動一括追加、(B)Association時のSession membership追加・移動、(C)Session存在中のNONE MeasurementをSession外にする案。A/Bは履歴の遡及変更、Cは既存membership定義との矛盾を理由に不採用。
3. NONE AssociationのEvent Authorityは、Session Entityの存在有無で発行権限を失わないよう、当該Physical Run / Scopeの認証済みDB Session Managerとした。Event RegistryにはNONE_ASSOCIATION_CREATED / NONE_ASSOCIATION_CLOSEDを登録。AssociationOrdinal・Active / Closed・CloseReason・再関連付け順序・Source CommitのEvent集合・DB Marker同一TransactionをMain §14.1.5で定義した。これは論理Authority / 原子性契約であり、実装・権限・crash実証済みを意味しない。

### Issue #201との矛盾修正
4. DB unavailableはIssue #201のAnonymous Modeとして扱う。障害期間中に有効なASSIGNED Assignment Operationは成立せず、Capture / Measurement / RawLogのAssignment-at-MeasurementはANONYMOUS（InstanceID=NULL）とする。障害期間中にLogical Session identity / DB Run / DB Session Mirrorを新規生成しない。障害期間Capture / Measurementの復旧後Bootstrap / DB取込 / Measurement Mirror化 / Associationは禁止する。障害開始前から存在するLogical Session identity / Lifecycleは外部正本上の履歴として保持する。障害前Source Commit済みでDB Run / Session Mirrorのみ未確定の場合は、Recovery AuthorityがReceipt / Manifest / Expected ID / DB状態を再検証し同一IDでMirrorを再構築できる。障害期間Measurementは依然ANONYMOUSであり、取込・Measurement Mirror化しない。
5. 障害前から存在するDB Run / Session identity / Session Mirrorは削除しない。障害前に有効AssignmentのManifest Source Commitまで検証済みでSession Mirrorのみ未確定の場合は、Recovery Authorityが同一IDでMirrorを再構築できる。障害期間中のCaptureは既存Logical Session identityが存在する場合に限り外部Manifest membershipへ記録できるが、Assignment-at-MeasurementはANONYMOUSであり、DB Session Mirror membershipへ追加せず、復旧後も遡及追加しない。
6. 同一Physical Run内で障害中に初回ASSIGNEDを試みても、有効なAssignment Operationは成立せず、Logical Session identity / DB Runは生成しない。CaptureはAssignment-at-Measurement=ANONYMOUSとして外部正本のみで保持し、復旧後にそのRunを遡及DB管理へ変換しない。DB管理を開始する場合は新しいPhysical Runから開始する。障害前に有効AssignmentのManifest Source Commitまで検証済みでDB Run / Session Mirrorのみ未確定の場合は、Recovery Authorityが同一IDでMirrorを再構築できる。ただし障害中CaptureをDB Session Mirror membershipへ追加・遡及追加しない。

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

### RawLog durability責務の最終照合
7. Main §8をDB側External Evidence Storageの共通byte-object永続化条件に限定した。Device / Capture Ownerが所有するCapture開始・終端、RawLog Schema / framing、Channel境界、Measurement Outcome、機器固有Retention / Loss契約をDB側で創作しない。
8. Storage read-back / fsync成功はCapture正常完了やMeasurement COMPLETEの証拠ではない。Capture境界未受領時はopaque fragmentとして保全し、完全RawLog / Aggregate入力を主張しない。

本追補は設計全体の承認・実装移行許可ではない。

## 38. V083-RV-01〜03 自己審査更新（2026-11-21）

- **V083-RV-01:** Issue #209のDB-RV-01〜08の元意味を4つの補助資料へ復元し、Entity / identityを独立DB-RV番号として扱う誤りを除去。文書上は修正済み、統括再審査待ち。
- **V083-RV-02:** Logical Session IDはDB正常利用可能時の初回有効ASSIGNED Operationで一度だけ発行し、外部Manifestへ先行記録。DB Session Mirrorは同じIDを使う。障害前に有効AssignmentのManifest Source Commitが検証済みでDB Session Mirrorのみ未確定なら、Recovery Authorityが同一IDでMirrorを再構築できる。DB unavailable期間に新規Sessionを生成せず、Bootstrap時発行もしない。
- **V083-RV-03:** DB unavailableはIssue #201のAnonymous Mode。障害期間CaptureのAssignment-at-MeasurementはANONYMOUS（InstanceID=NULL）。障害中の初回ASSIGNED試行は有効Operationではなく、DB Run / Logical Session identity / Mirrorを生成しない。障害期間データは復旧後も取込・Measurement Mirror化・Associationしない。障害前Source Commit済みで未確定のRun / Session Mirror再構築は同一IDのRecovery処理として分離する。
- 障害前から存在するDB Run / Session identity / Mirrorは履歴として保持する。障害期間Captureは既存Logical Sessionがある場合でも外部正本のみで保全し、DB Mirror membershipへ遡及追加しない。
- 検証は文書間の読み戻し・文字列照合に限定。DB unavailable実機試験、Run Manager実装、Manifest/Assignment authorityの実証は未実施。統括承認・実装許可を意味しない。

## 39. V083-RV-04 / 05 自己審査更新（2026-11-21）

- **V083-RV-04:** Main §1.4.5 / §14.1.5 / §14.4.14でNONE_ASSOCIATION_CREATED / NONE_ASSOCIATION_CLOSED、Record / Event identity、CREATED / CLOSED Payload、Active / Closed、CloseReason、REASSIGNの同一Operation内Close→Create、Source Commit、DB Marker同一Transaction、fail-closed条件、Event Authorityを定義。State Transition Matrix SES-030〜032と照合済み。仕様文書上は補完済み案、実装・権限・crash実証は未実施。
- **V083-RV-05:** Main §8.1はDB側External Evidence Storageによる引渡し済みbyte objectの永続化に限定。Motor / Battery担当がCapture / RawLog / Schema / Outcome / Channel / Retention / Loss契約を所有する。fsync / read-back / Atomic Rename等は共通ストレージ受入条件であり、機器固有契約ではない。契約未受領byteはopaque保存のみ。Issue #35 / #170 / #16をDB側で拡張しない。
- OS / filesystem別のdurability、SQLite crash / restore、Association Eventの実装・権限・atomicity試験は未実施。統括承認・実装許可を意味しない。

## 40. MAJOR項目の自己審査状態（2026-11-21）

- **Measurement→Session relation:** CC-03により直接FK / membership / session_idを不採用。MeasurementはRUN_SCOPEへ直接属し、Sessionは同一RUN_SCOPE配下の独立Lifecycle Entity。文書同期対象。
- **Aggregate Outcome:** Current AggregateをOutcome=COMPLETEに限定する理由をMain §14.2.3へ追記。COMPLETEは正式Capture契約が正常終端と必須Sample完了を証明した場合のみ。契約未受領時は推定せず除外。
- **UUIDv4 / M4W-JCS-1:** Decimal negative-zero記述の矛盾を解消し、JCS期待Canonical bytes / SHA-256 vector 13件と拒否ケース10件をCanonical Audit §19に追加。二つの独立JCS実装の照合・CSPRNG実証は未実施。Entity TypeごとのIssuer Authority mappingも未完成であり、未登録EntityのID発行経路は未実装・未許可。
- **DB-001〜124:** Evidence Ledgerで全IDの範囲履歴と個別根拠の強さを分離。REFERENCE_ONLY_NOT_EXECUTABLEは過去要求の撤回・無効化を意味しない。DB-001〜056は会話由来短縮定義、DB-057〜124は個別原文未回収。
- **V082:** 001〜030はv0.8.2定義、031〜053はv0.8.3追加案。実装 / fixture / 実行ログは未回収。NO_MAPPINGと網羅未証明を維持。
- **Entity Inventory:** 未受領Fieldは創作せず、Envelope / OwnerReference / PayloadReference / PayloadHash等の既知部分のみ検証。未知Payloadはopaque / reject。完全Field Schemaは未完成。
- **Receipt Recovery:** §§1〜21を旧調査時点の履歴と明示し、Main §14.4 / 本書§22を現行規範とした。物理耐久性・Crash / Restore / fencingは未実証。
- これらはDB部門自己審査であり、統括の承認・BLOCKER解除・実装許可を意味しない。


## 39. 統括決定CC-03 — Measurement / Session直接関係の不採用（2026-11-22）

**DECISION_STATUS: DECIDED / DOCUMENT_STATUS: REFLECTED（本Self Review）**

- MeasurementはRUN_SCOPEへ直接属する。Sessionは同じRUN_SCOPE配下の独立Lifecycle Entity。
- Measurement→Session直接FK / membership / session_id / 所属Ordinalは設けない。
- 測定時Assignment Snapshot / Revision / State / InstanceIDはMeasurement側に不変保持する。
- RUN_SCOPEを介した派生View / Queryによる同一Scope内の併記は可能だが、永続所属ではない。
- NONE AssociationはInstance関連付け履歴のみであり、Session relationを変更しない。
- 旧A/B/C案、Session membership OPEN/TBD、統括確認待ちの記述は履歴としてのみ保持し、SUPERSEDED / NOT_ADOPTEDとする。

v0.8.3全体承認、物理設計、DDL、DB生成、Migration、Restore実行、実装、PR作成・merge、main反映は未許可。

## 41. 統括裁定 GL-01〜03 — 自己審査状態同期（2026-11-22）

**正本根拠:** Issue #207 comment #7079475903。GL-01〜03のDECISION_STATUSはDECIDED。以下は文書同期・実装・検証・承認を分離した自己審査記録であり、v0.8.3全体承認ではない。

### GL-01 UUIDv4 Issuer Authority

- UUID-bearing Entity Type別の単一Issuer Role mapをMain §5.1 / Entity Inventory §37.1と同期する。
- 実Principal / Service / Scope / 発行・失効・監査証拠がAuthority Registryに登録される前は発行禁止。
- UUIDv5 / Namespace / Canonical Binary Name v2は現行方式に不採用。旧記述は履歴としてのみ保持し、OPENや承認待ちへ戻さない。
- DB Session MirrorはLogicalSessionIDを再利用し、ReceiptIDはOperationIDから導出せず独立UUIDv4とする。

### GL-02 Minimum Entity / Envelope / Event Schema

- 23概念すべてを独立SQL Table / UUIDへ展開しない。現行運用の共通Identity・Authority・Reference・Lifecycle・Integrity境界を最小Schemaとする。
- 外部正本Envelope: EntityType / SchemaVersion / EntityID / CreatedAtUTC必須。Root以外はOwnerReference、外部正本ObjectはPayloadReference / PayloadHash必須。
- Ownerの完全Field Schema未受領Payloadはopaque保存のみ。意味解析・Field補完・Aggregate入力禁止。
- Event schemaとAuthorityはEvent Registry / Owner Authorityに従い、Writer GrantはOperation Journalから独立したAuthority Chainとする。

### GL-03 Current Aggregate Outcome

- COMPLETE、正式Capture正常終端、必須Sample完全性、Envelope / Assignment / Scope / RawLog・Sample Reference / Hash検証、測定時ASSIGNEDかつ現在同一Instance、Scope / Owner条件をすべて満たすMeasurementのみCurrent Aggregate対象。
- 契約未受領・証拠不足はUNKNOWN / opaqueとして除外。ANONYMOUS / NONE / STOP / ERROR / CANCEL / INCOMPLETE / UNKNOWNも除外。
- Session Lifecycleとは独立。Battery CH1 / CH2は平均・合算せず独立Aggregate。Pair Analysisは別Artifact。

### GL-04 — Battery field mapping Self Review（2026-11-23）

- RUN_SCOPE参照はMeasurement Envelopeの `PhysicalRunID` + `ScopeKey`。独立RunScopeIDは設けない。
- RawLog Object: `RawLogObjectID` + `ContentHashSHA256`。RawLog Reference: `RawLogReferenceID` + `RawLogObjectID` + `RawLogObjectContentHash`。Measurement Envelopeは `RawLogReferenceID` を参照する。
- Sample Reference: `SampleReferenceID` + `RawLogReferenceID` + `SampleLocator`。Measurement Sample Link: `MeasurementID` + `SampleReferenceID` + `Role` + `Ordinal`。参照鎖は Measurement → RawLog Reference → RawLog Object、および Measurement → Measurement Sample Link → Sample Reference → RawLog Reference → RawLog Object。
- Object Hashは全RawLog byteのSHA-256。`RawLogObjectContentHash` と Objectの `ContentHashSHA256` の完全一致を要求。
- legacy SQLite schemaに不足Fieldがあることを理由に推定列追加・列名解釈を行わない。登録拒否 / UNKNOWN opaque / Aggregate除外。
- 未確定のSampleLocator grammar、Role / Ordinal domain、cardinality、Device固有Sample semanticsは未解決のまま明示。今回の論理mappingで実装・検証済みとはしない。
- これはGL-04のDB側Field mapping回答であり、Motor側Capture契約受領、Batteryの全Capture契約受領、v0.8.3全体承認を意味しない。

### 5軸状態

| Gate | DECISION | DOCUMENT | IMPLEMENTATION | VERIFICATION | APPROVAL |
|---|---|---|---|---|---|
| GL-01 | DECIDED | REFLECTED | NOT_STARTED（Principal / Service登録未実施） | NOT_RUN | PENDING |
| GL-02 | DECIDED | REFLECTED | NOT_STARTED | NOT_RUN | PENDING |
| GL-03 | DECIDED | REFLECTED | NOT_STARTED | BLOCKED for contract-missing data | PENDING |
| GL-04 | DECIDED（DB mapping / non-inference boundary） | PARTIAL（DB mapping reflected; full device Capture contract incomplete） | NOT_APPLICABLE before complete contract | NOT_RUN | PENDING |

**残る作業:** Entity Inventory / Audit / Self Reviewの旧候補記述を現行決定と区別して明示すること、Authority Registryの実Principal登録、Motor / Battery正式Capture契約の受領、実装後の独立適合・実証。これらはGL-01〜03の決定自体をOPENへ戻す理由ではない。