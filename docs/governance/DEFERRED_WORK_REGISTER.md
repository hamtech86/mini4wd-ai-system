# 共通保留・後続対応台帳 v0.1（提案）

- 作成日: 2026-11-22
- 状態: 提案 / 未承認
- 管理範囲: アクティブ部門（Motor / Battery / DB）および統括直轄の横断管理事項。共通UI / RawLog / Python制御 / 310 / 将来機能は独立したアクティブ部門ではなく、該当する3部門または統括が管理する。
- ガバナンス親: [Issue #212](https://github.com/hamtech86/mini4wd-ai-system/issues/212)
- 全担当共通ルール: [Issue #77](https://github.com/hamtech86/mini4wd-ai-system/issues/77)
- 依存関係・旧PR整合監査: [Issue #214](https://github.com/hamtech86/mini4wd-ai-system/issues/214)

> この台帳は、設計審査を不必要に停止させず、実装後検証・実機検証・他部門指摘・外部依存・根拠回収作業を一元追跡するための管理案である。ここへの登録・移管は、仕様の承認、実装許可、実機作業許可、PRの受入またはマージを意味しない。

## 1. 運用目的と基本原則

設計成果物の完成度を審査する作業と、実装後・実機・運用段階で行う検証作業を分離する。各部門からの不整合指摘や新規発見事項も同じ受付・分類手順に載せる。

- 保留事項が存在することだけを理由に、設計PRをDraftのまま維持しない。
- 保留事項を別台帳へ移したことだけを理由に、設計上の矛盾・必須仕様欠落・安全上の未決定を解決済みにしない。
- 設計審査を止める場合は、影響する設計範囲、具体的な矛盾・欠落、安全上の理由、解除条件を記録する。無関係な領域まで一律に停止しない。
- 他部門の指摘は必ず受付登録する。受付しただけで設計PRを自動的にDraftへ戻したり、審査を自動停止したりしない。
- 根拠のない推測で仕様を補完しない。確認できない事項は「不明」「根拠未回収」とする。
- GitHubのOPEN/CLOSED、Draft/Ready/Merged、CI greenだけでACCEPTEDにしない。Issue #212の状態モデルと完了ゲートに従う。
- 正本・権限・依存関係はIssue #212およびIssue #77に従う。本台帳は仕様正本ではなく、タスクの所在と状態を管理する。
- PR merge、ソフトウェアテスト成功、実機検証、設計承認は別々の事実として記録する。

## 2. 登録分類と設計審査への影響

| 分類 | 内容 | 原則的な扱い |
|---|---|---|
| A — DESIGN_BLOCKER | 論理矛盾、必須仕様欠落、責務境界の衝突、安全上の未決定 | 該当する設計範囲の審査を停止。台帳へ移して隠さず、設計PR/正本側にも残す |
| B — IMPLEMENTATION_VERIFICATION | ビルド、単体/統合テスト、メモリ・性能・パッケージ検証など | 原則として設計審査を停止しない。実装受入ゲートで管理 |
| C — CROSS_DEPARTMENT_FINDING | 他部門からの不整合・契約差異・影響指摘 | 受付後、根拠を確認しA/B/D/E等へ再分類。自動的な審査停止は禁止 |
| D — EXTERNAL_DEPENDENCY | 実機、測定器、部品情報、現場条件、ユーザー判断などが必要 | 条件・担当・必要な許可・再開条件を明記して保留 |
| E — EVIDENCE_RECOVERY | Issue/PR/commit/blob/旧設計書/テスト記録から根拠を探す作業 | 検索対象と回収見込みを具体化。根拠がなければ推測で埋めず終了判断を求める |

Cは受付時の発見元分類であり、最終分類は問題の実体に合わせる。複数分類が必要な場合は主分類と副分類を明記する。

### 設計審査を停止する判定

次のいずれかが証拠付きで成立する場合に限り、影響範囲を限定してAとする。

1. 審査対象の必須仕様が欠落し、受入条件を定義できない。
2. 同じ対象・同じ条件で正本同士が矛盾し、統括判断なしに選択できない。
3. 安全性・データ保全・権限境界に関する未決定が、設計の妥当性そのものを左右する。
4. 未解決事項を残したまま審査すると、後から設計の意味・責務・受入条件を変更せざるを得ないことが具体的に示される。

上記に該当しない実機測定、実装試験、外部設備待ち、将来機能確認は原則B/Dとして後続管理する。判断に迷う場合は、担当が独断で設計を止めず、統括判断待ちとして記録する。

## 3. 根拠回収可能性の必須評価

すべての未解決項目に、以下のいずれかを付ける。

- **RECOVERABLE**: repo、Issue、PR、Git履歴、成果物などに具体的な回収先があり、現時点で回収可能性が高い。
- **CONDITIONALLY_RECOVERABLE**: 他部門、ユーザー、実機、測定器、部品情報、外部記録などの提供・実施条件が満たされれば回収可能。
- **NO_CURRENT_BASIS**: 現時点で回収元・回収方法の根拠が確認できない。推測で埋めず、統括へ「仕様決定」「代替試験」「対象外化」「終了」等の扱い判断を求める。

RECOVERABLEの場合は具体的なファイル/Issue/PR/commit等を記す。CONDITIONALLY_RECOVERABLEの場合は必要な主体・物品・条件を記す。NO_CURRENT_BASISの場合は、検索した範囲と確認日を記し、単なる未調査と区別する。

## 4. 台帳エントリの必須フィールド

各項目は最低限、次を記録する。

- ID / タイトル / 主分類・副分類 / 発見元部門 / 登録日
- 事実として確認した内容（推測と分離）
- 根拠リンク、参照した正本、該当SHA（コード/PRの場合）
- 影響範囲（部門、機能、設計PR、実装PR、Issue）
- 設計審査への影響: STOP / NO_STOP / SCOPE_LIMITED / PENDING_RULING と理由
- 根拠回収可能性: RECOVERABLE / CONDITIONALLY_RECOVERABLE / NO_CURRENT_BASIS
- 回収先・必要な依存・担当（未定ならUNASSIGNED）
- 完了条件・再開条件・必要な承認
- 状態: INTAKE / TRIAGE / READY / IN_PROGRESS / BLOCKED / REVIEW / ACCEPTED / SUPERSEDED / NOT_ADOPTED
- 最終判断者・判断日・正本への反映先

「未解決」の一語だけで放置しない。担当・次の行動・回収見込みのいずれも設定できない場合は、その理由と統括への判断依頼を明記する。

## 5. 受付から完了まで

1. **INTAKE**: 部門から指摘を受領。原文、発見元、日時、根拠を保全する。
2. **TRIAGE**: 事実/仮説を分離し、影響範囲、分類、審査停止要否、回収可能性を判定する。
3. **READY**: 正本、担当、依存、受入条件、完了条件が特定された。
4. **IN_PROGRESS / BLOCKED**: 調査・検証・外部依存を進め、阻害理由と次の行動を更新する。
5. **REVIEW**: exact SHA、証拠、受入条件との照合結果を提出する。
6. **ACCEPTED**: 受入権限者が証拠に基づき明示承認した。
7. **SUPERSEDED / NOT_ADOPTED**: 置換先または不採用理由と、履歴・固有成果物の扱いを明記する。

親Issue/PRを閉じる際は、未完了項目の移管先・切り離し理由を記録し、Issue #212の完了ゲートに従う。

## 6. 設計PR・保留台帳の相互参照ルール

- 設計PRは、設計の論理的完成度と審査対象範囲を扱う。
- 本台帳は、実装後検証、実機検証、他部門指摘、外部依存、根拠回収などの後続作業を扱う。
- 設計PRから移す項目は、台帳IDと移管理由を設計PR本文に残す。単に記述を削除しない。
- A — DESIGN_BLOCKERは設計PR側にも残し、台帳は追跡・依存管理の補助とする。Aを本台帳へ移しただけで審査を続行しない。
- B/D/Eは、設計の意味・受入条件を変えない限り、設計PRの審査を止めない。
- 他部門から新しい指摘が出た場合は、本台帳に登録して影響評価する。既存の設計PRを再Draft化するのは、Aに該当する根拠が確認された場合に限る。
- 受入後に新しいA相当の事実が発見された場合は、既存審査を黙って書き換えず、新しい是正Issue/PRを作成し、影響範囲と再審査の要否を統括判断する。

## 7. 初期登録項目（2026-11-22時点）

以下は既存記録から確認できる候補の初期登録であり、完了・承認・実機合格を意味しない。新しい根拠が得られた場合は状態を更新する。

| ID | 対象 | 主分類 | 設計審査への影響 | 根拠回収可能性 | 現状 / 次の行動 |
|---|---|---|---|---|---|
| DFR-310-01 | 実MCUの型番/マーキング/Signature確認、Fuse/BOD条件 | D — EXTERNAL_DEPENDENCY | NO_STOP（物理適合性ゲート） | CONDITIONALLY_RECOVERABLE | PR #183/#184の設計値は存在するが、実搭載MCU・Fuseの現物証拠は未確認。対象基板と安全な確認手順・許可が必要 |
| DFR-310-02 | 電源過渡、Supervisor/Hold-up、EEPROM電源断耐性 | D — EXTERNAL_DEPENDENCY | NO_STOP（物理資格確認ゲート） | CONDITIONALLY_RECOVERABLE | 設計上の依存条件はPR #183/#184に記録。実電源条件・部品・測定器・試験承認が必要 |
| DFR-310-03 | ADC基準電圧・精度・誤判定余裕の確認 | D — EXTERNAL_DEPENDENCY | NO_STOP（測定適合性ゲート） | CONDITIONALLY_RECOVERABLE | ADC許容誤差・実装センサー/基準情報の一部が未確定。実装部品情報と測定設備が必要 |
| DFR-310-04 | Worst-case nested call chain / ISRを含むStack上限・Reserve証明 | B — IMPLEMENTATION_VERIFICATION | NO_STOP（実装適合性ゲート） | RECOVERABLE | PR #198の関数別stack reportは存在するが、最悪ネスト/ISR合算の証明は未完。静的解析・呼出し経路・必要ならwatermarkの証拠を回収する |
| DFR-310-05 | 物理STOP後の実電流停止・電力段故障時の挙動 | D — EXTERNAL_DEPENDENCY | NO_STOP（物理安全資格ゲート。試験許可は別途必須） | CONDITIONALLY_RECOVERABLE | ソフトウェアSTOPテストは存在するが物理遮断の証拠ではない。実機・電流計測・安全計画・明示許可が必要 |
| DFR-310-06 | Evidence bundle manifestの完全性・fixture/validator | B — IMPLEMENTATION_VERIFICATION | NO_STOP（証拠パッケージ受入ゲート） | RECOVERABLE | PR #198のbundle実装とsidecar hash-linkは確認済み。byte length/completeness state不足とfixture/validator確認を継続 |
| DFR-GOV-01 | 旧PR/積層PR/旧診断要求の正本・採用先整合 | E — EVIDENCE_RECOVERY | SCOPE_LIMITED（該当PR/Issueの状態判断に限定） | RECOVERABLE | Issue #214を正本の監査台帳として継続。各項目のexact SHA・採用先・固有差分を確認し、推測でcloseしない |
| DFR-XDEPT-01 | 他部門からの指摘・契約不整合の横断受付 | C — CROSS_DEPARTMENT_FINDING | PENDING_RULING（各指摘の根拠確認後に個別判定） | RECOVERABLE | 新規受付枠。Motor/Battery/DB/UI/RawLog等の指摘を原文・証拠付きで登録し、A/B/D/E等へ分類する |

### 310-4/310-5との境界

- PR #183は310-4設計成果物の審査・受入候補であり、本台帳の存在だけでReady化・承認・マージを意味しない。
- PR #184は安全証拠と未実施/未確認状態の保全先である。NOT RUN/NOT CONFIRMEDをPASSに読み替えない。
- HARDWARE_CURRENT_LIMIT_CONFIRMED=false を維持する。
- 本台帳は実機通電、Motor駆動、EEPROM/Fuse操作、物理STOP試験、310測定を許可しない。
- 設計上の決定事項と実装後検証待ちを混同しない。実装後検証待ちは、それだけで設計未決定を意味しない。

## 8. 部門からの新規登録テンプレート

新しい指摘は以下の形式で追加する。根拠が未提示の場合も受付はできるが、根拠未提示と明記し、事実として扱わない。

~~~markdown
### DFR-<AREA>-<NN> — <タイトル>
- 登録日:
- 発見元部門 / 報告者:
- 原文の指摘:
- 確認済み事実:
- 仮説・未確認事項:
- 根拠リンク / ファイル / SHA:
- 影響範囲:
- 主分類 / 副分類:
- 設計審査への影響: STOP / NO_STOP / SCOPE_LIMITED / PENDING_RULING
- 判定理由:
- 根拠回収可能性: RECOVERABLE / CONDITIONALLY_RECOVERABLE / NO_CURRENT_BASIS
- 具体的な回収先 / 必要条件:
- 担当:
- 依存先:
- 完了条件:
- 状態:
- 次の具体的行動:
- 承認・判断待ち:
- 正本への反映先:
~~~

## 9. 初回運用時の作業

1. 本台帳PRを統括レビューし、分類・状態・権限境界を確定する。
2. Issue #77へ本台帳への参照と共通受付ルールを追加する。
3. Issue #212へ本台帳を全体ガバナンスの後続管理先として登録する。
4. 各部門司令塔に、既存の未解決事項を「設計阻害 / 実装検証 / 他部門指摘 / 外部依存 / 根拠回収」に分けて提出するよう依頼する。
5. 重複項目は既存Issueを正本としてリンクし、同じ課題の二重管理を作らない。
6. アクティブ3部門と統括直轄の初回棚卸しが完了するまで「全残件を集約済み」とは宣言しない。

## 10. 権限境界

本台帳および本PRは、保留事項の分類・記録・追跡のためのもの。以下を許可しない。

- 設計承認、仕様変更、正本の置換
- DB DDL、DB生成、Migration、旧DB復旧
- Motor/Battery制御やファームウェアの実装変更
- PRの自動マージ、設計PRの自動Ready化/Close
- 実機通電、Motor駆動、EEPROM/Fuse操作、物理測定
- HARDWARE_CURRENT_LIMIT_CONFIRMED の変更

これらは既存の各承認ゲートと統括の明示判断を別途必要とする。


## 11. 初回棚卸し候補（アクティブ3部門＋統括直轄、未判定・重複登録しない）

2026-11-22に既存OPEN Issueを検索し、以下を初回確認対象として抽出した。これは各Issueの現行判定を変更するものではなく、各Issueを本台帳へ複製するものでもない。正本は引き続き各リンク先とし、担当部門から証拠・状態・移管可否を受け取ってから台帳IDを割り当てる。

| 部門 | 既存正本/タスクIssue | 現時点で確認できる内容 | 初回依頼 |
|---|---|---|---|
| Battery / DB横断 | [#208](https://github.com/hamtech86/mini4wd-ai-system/issues/208) | Battery CH1/CH2の独立性方針と、解析関数・既存テストの平均化期待値の不整合が報告されている。 | Battery担当が現行正本との照合、影響範囲、修正方針、テスト状態を報告。DB設計は未承認のため、#208の指摘だけでDB正本を承認しない |
| DB | [#207](https://github.com/hamtech86/mini4wd-ai-system/issues/207), [#211](https://github.com/hamtech86/mini4wd-ai-system/issues/211), [#210](https://github.com/hamtech86/mini4wd-ai-system/issues/210) | v0.8.3はORANGE条件付き差戻し・未承認。CC-01/CC-02の限定判断は有効だが、設計全体承認ではない。 | DB担当が#211のBLOCKER/MAJORごとに根拠回収可能性、未回収の正式契約、統括判断待ち、次の具体的行動を分けて報告。設計阻害事項はDB審査側に残し、本台帳へ移して隠さない |
| Motor / 計測 | [#172](https://github.com/hamtech86/mini4wd-ai-system/issues/172), [#174](https://github.com/hamtech86/mini4wd-ai-system/issues/174), [#158](https://github.com/hamtech86/mini4wd-ai-system/issues/158) | PWM 0〜30段階測定・巻線抵抗測定への統合に関する既存タスクが存在する。 | Motor担当が設計確定事項、ソフトウェア検証、実機依存、必要なユーザー作業を区分し、各Issueの受入条件と現在状態を報告 |
| Motor安全 / 実装境界 | [#161](https://github.com/hamtech86/mini4wd-ai-system/issues/161) | 巻線抵抗測定の状態機械とI/O Adapter契約に、独立ハードウェア電流制限の証拠がない場合のfail-closed境界が記録されている。 | Motor担当がソフトウェア上の未完了と実機許可待ちを分離し、ハードウェア電流制限の確認根拠・未確認範囲を報告 |
| Motor / DB境界（RawLog・通信） | [#170](https://github.com/hamtech86/mini4wd-ai-system/issues/170), [#35](https://github.com/hamtech86/mini4wd-ai-system/issues/35) | #170の機器側Capture・通信・解析入力はMotor責任範囲。DB側の保存参照・耐久性はDB責任範囲。#35はMotor領域の接続・制御・RawLog契約正本。 | Motorは機器側契約、DBはDB参照・保存境界を担当し、部門間矛盾は統括が調整する。独立RawLog部門は設けない |
| 統括直轄（共通診断レポート横断） | [#205](https://github.com/hamtech86/mini4wd-ai-system/issues/205), [#150](https://github.com/hamtech86/mini4wd-ai-system/issues/150), [#214](https://github.com/hamtech86/mini4wd-ai-system/issues/214), [PR #206](https://github.com/hamtech86/mini4wd-ai-system/pull/206) | Motor/Battery共通機能。PR #206はCI 5/5成功だがDraft/未merge、実PC GUI・実GitHub upload・実環境retryはNOT RUN。旧#150/#151要件の一部scope dispositionも未決。 | 統括が旧要件の継承・変更・廃止を明示判断する。Motor/Batteryのログ意味・RawLog選択境界は各部門が支援。独立UI/RawLog部門は設けない |

| Main UI / 旧P1〜P4トレーサビリティ | [#80](https://github.com/hamtech86/mini4wd-ai-system/issues/80), [#84](https://github.com/hamtech86/mini4wd-ai-system/issues/84), [#93](https://github.com/hamtech86/mini4wd-ai-system/issues/93), [PR #92](https://github.com/hamtech86/mini4wd-ai-system/pull/92) | 現行Main UI外部設計v1.2が正本。PR #92はMERGED、#93 CLOSED。P1〜P3の旧PR変更は#92へ統合済み。mainの`ui_benchmark_presets.py` / `app/main.py` と`test_ui_benchmark_presets.py`（STD-T/Full-T非対応テスト）もSTD-I/Full-Iのみを確認。#80本文とPR #92本文の旧4レシピ/High-side Current記述は現行mainではない。 | 旧要求を再実装しない。#84の旧証跡は#212/#217へ整理し、CIと実機確認を区別。独立UI/統合検証部門は設けない |
| RawLog Library / 既存ログ救出 | [#25](https://github.com/hamtech86/mini4wd-ai-system/issues/25), [#101](https://github.com/hamtech86/mini4wd-ai-system/issues/101) | mainの`data/motor_logs/`では`MOTOR-000001_SOURCE.md`のみ確認。README/indexはmain・code search・path commit historyで見つからない。Bash/ローカル未回収ログはユーザーPCに依存。 | README/indexの元ファイル回収はNO_CURRENT_BASIS。推測で復元しない。#25は今後受領するログの原文不変保全、#101はローカル原本が存在する場合のみCONDITIONALLY_RECOVERABLEとして管理 |
| 310設計・安全証拠・旧PR依存 | [#214](https://github.com/hamtech86/mini4wd-ai-system/issues/214), [PR #183](https://github.com/hamtech86/mini4wd-ai-system/pull/183), [PR #184](https://github.com/hamtech86/mini4wd-ai-system/pull/184), [PR #188](https://github.com/hamtech86/mini4wd-ai-system/pull/188), [PR #215](https://github.com/hamtech86/mini4wd-ai-system/pull/215) | #215 MERGED。#183 OPEN/DRAFT、exact-head CI 2/2 successだがdesign acceptance未付与。#184はphysical evidence ledgerでNOT RUNを保持。#188は実装再merge不要、#183正本受入待ち。 | 統括直轄。repo証拠はRECOVERABLE、stack/ADC/physical qualificationはCONDITIONALLY_RECOVERABLE。既に同期済みSHA・#215文書保全を再残件化しない |
| 共通診断レポート旧新要件 | [#150](https://github.com/hamtech86/mini4wd-ai-system/issues/150), [#151](https://github.com/hamtech86/mini4wd-ai-system/issues/151), [#205](https://github.com/hamtech86/mini4wd-ai-system/issues/205), [#214](https://github.com/hamtech86/mini4wd-ai-system/issues/214), [PR #206](https://github.com/hamtech86/mini4wd-ai-system/pull/206) | #206 exact-head CI 5/5 successだがDraft/未merge、GUI/live upload/retry NOT RUN。旧保存先・env token・physical observation・history completenessのscope disposition未決。 | 統括直轄のMotor/Battery横断。旧要求を自動で継承/廃止しない。#214でscope判断後にPR受入可否を決める |

### 初回棚卸しの完了条件

- 各部門が既存OPENタスクの正本・状態・根拠・受入条件・依存先を確認した。
- 各残件についてRECOVERABLE / CONDITIONALLY_RECOVERABLE / NO_CURRENT_BASISのいずれかと具体的な根拠を記録した。
- 設計阻害事項は該当する設計Issue/PRに残り、後続検証事項のみ台帳IDで相互参照された。
- 既存Issueを重複管理せず、正本Issueの更新が必要な場合は担当部門が正本側を更新した。
- 未回答・未確認の部門を明示し、全部門完了と誤表示しない。


## 12. 2026-11-22 DB部門報告の回収・残件再分類（統括追補 / 提案）

参照: [Issue #207](https://github.com/hamtech86/mini4wd-ai-system/issues/207) のDB部門コメント、[Issue #211](https://github.com/hamtech86/mini4wd-ai-system/issues/211) のORANGE再審査、DB作業ブランチ `db/v0.8.3-followup-remediation-20261121`。本節はIssue #217への提出を待たず既存のDB報告から証拠を回収した暫定整理であり、統括承認・BLOCKER解除ではない。

### 12.1 既存報告で回収できた修正案

| 対象 | 報告された処置 | 根拠回収可能性 | 現在の扱い |
|---|---|---|---|
| V083-RV-01 DB-RV番号 | Issue #209の元定義へ復元し、監査資料等を同期 | RECOVERABLE | 文書修正案あり。新HEADで統括再審査が必要 |
| V083-RV-02 Session identity / DB Mirror | Logical Session IDとDB Mirrorを区別し、障害前Source Commit済みidentityのみ同一IDでMirror再構築する境界を追補 | RECOVERABLE | 文書修正案あり。Recovery実証は未実施 |
| V083-RV-03 DB unavailable / Anonymous | 障害中の初回ASSIGNEDを不成立とし、障害期間Measurementの後日取込を禁止。障害前Source Commit済みidentityのMirror Recoveryとは分離 | RECOVERABLE | Issue #201との文書整合案あり。統括再審査が必要 |
| V083-RV-04 NONE Association履歴 | CREATED/CLOSED Event、Record/Event identity、Close→Create順序、Quarantine条件を定義 | RECOVERABLE | 論理案あり。実装・Transaction atomicity・crash試験は未実施 |
| V083-RV-05 RawLog durability責務 | DB側の不変byte保存と、Motor/Battery側Capture/RawLog契約の責務を分離 | RECOVERABLE | 論理案あり。OS/filesystem durability実証と機器正式契約は別途 |
 
報告された最終修正HEADは `29df60c462e93bd106c54f9a448eec14231c6f05`（base: `f093fcf7a64e8951b5b86fe1c4837ed656355df1`、93 commits ahead / 0 behind）。PR作成・main反映は報告されていない。したがって「修正済み案の存在」は確認できるが、「統括BLOCKER解消」「設計承認」「main正本反映」とは扱わない。

### 12.2 DB部門報告で明示された残件

| 残件 | 分類 | 根拠回収可能性 | 次の具体的行動 / 完了条件 |
|---|---|---|---|
| NONE MeasurementとSessionの関係 | SUPERSEDED / DECIDED（CC-03） | RECOVERABLE（決定根拠: Issue #210 comment 7076202503） | Measurementは常にRUN_SCOPEへ直接所属。Sessionは独立Lifecycle Entity。同一RUN_SCOPE配下の派生View以外に永続membership / Measurement→Session FKを設けない。再審議しない |
| UUIDv4 issuer authority mapping | MAJOR — 設計補完事項（Issue #211の分類を維持） | CONDITIONALLY_RECOVERABLE | Entityごとの責任Owner/Issuer authorityの正式提示が必要。23 Entity Inventoryと照合し、未割当Entityの発行可否を明記 |
| Entity 23概念中13件の完全Schema欠落 | MAJOR — 設計補完事項（Issue #211の分類を維持。必須Entityの範囲を個別判定） | CONDITIONALLY_RECOVERABLE | Motor/Battery正式契約・各Entity OwnerのField Schemaを受領。Opaque扱いで設計を進めるEntityは検証可能範囲と禁止処理を明記 |
| 旧DB-001〜124個別追跡・原本回収・全件Crosswalk | SUPERSEDED / NOT_TRACKED_BY_USER_DIRECTION | 該当なし（ユーザーが個別追跡・原本回収・全件Crosswalkの終了を明示） | この作業は終了済み。台帳から再開しない。別の新しい具体的根拠が提示された場合も、同一作業の再開ではなく統括判断を先に行う |
| UUID/JCS conformanceの独立実装照合 | B — IMPLEMENTATION_VERIFICATION | RECOVERABLE（vector/期待値はrepo内に存在） | 2つの独立実装で一致確認し、未実行はNOT RUNのまま記録 |
| Backup/Restore/Filesystem/SQLite crash試験 | B — IMPLEMENTATION_VERIFICATION | CONDITIONALLY_RECOVERABLE | 実装段階で対象OS/filesystem/SQLite条件とfixtureを確定して実行。現時点で実施許可・PASS扱いしない |
| Motor/Battery正式Capture・RawLog契約 | D — EXTERNAL_DEPENDENCY | CONDITIONALLY_RECOVERABLE | Motor/Battery責任者から正式契約を受領。Issue #35はMotor領域の契約正本、Issue #16はBattery E2E検証Issueであり、いずれも不足契約をDBが推定補完しない |

**重要な区別:** DB部門報告によりV083-RV-01〜05の「文書修正案」は回収できた。一方、NONE Session membership、UUID Issuer authority、完全Entity Schema、Motor/Battery正式契約は残る。設計案の修正を統括判断・正式契約・実証試験の完了に読み替えない。

### 12.3 初回全部門棚卸しの回答状況

2026-11-22時点のユーザー確認により、アクティブ部門はMotor / Battery / DBの3部門のみ。3部門の今回の棚卸し回答は受領済み（USER_CONFIRMED_RESPONDED）。既存Issueの担当名や過去のチャット役割は、独立したアクティブ部門の存在を意味しない。RawLog/通信、共通UI、統合検証等は、Motor / Battery / DBの責任境界または統括直轄へ再分類する。未確認の横断事項は統括が既存証拠をread-backし、部門へ同じ棚卸しを再依頼しない。

本追補はPR #216の提案文書に対する監査追記であり、PR #216の承認・マージ、DB設計承認、実装、物理試験を意味しない。


## 13. 全体整理完了までの審査保留・再浮上防止ゲート（2026-11-22 統括指示）

### 13.1 審査実施タイミング
PR #216および各部門の残件について、**全部門の棚卸し・既存解決記録との照合・正本反映状況の整理が完了するまで、統括による新運用の正式審査を開始しない。**

現段階は審査ではなく、全体整理・証拠回収・重複再発防止の準備段階とする。途中で一部部門の回答が揃っても、全体整理完了とは扱わない。未回答・回収不能項目が残る場合は、その事実と探索範囲・判断待ちを明示し、ユーザー/統括の明示判断なしに完了扱いしない。

### 13.2 解決済み事項の再浮上防止
各残件には一意のRegister IDを付与し、以下を必須記録とする。
- 正本Issue / PR / 文書パスと該当節
- 解決・決定内容と根拠（Issueコメント、レビュー、Commit SHA、Blob SHA、CI run等）
- 対象ブランチと適用HEAD / main反映有無
- 解決状態（PROPOSED / DECIDED / IMPLEMENTED / VERIFIED / ACCEPTED / SUPERSEDED等。意味を混同しない）
- 適用範囲・非適用範囲・残る条件
- 再オープン条件（新しい反証、対象変更、依存仕様変更、根拠欠落の発見等）

### 13.3 再浮上時の処理
既存項目と同一または実質同一の指摘が再浮上した場合、**新規残件として再登録する前に**次の照合を行う。
1. Register ID / Canonical Issueを特定する。
2. 過去の解決・決定記録とその根拠を確認する。
3. 正本・対象ブランチ・現在HEADへの反映有無を確認する。
4. 新しい証拠があるか、単なる未同期・参照漏れ・古い資料の残存かを判定する。
5. 既存項目を再開するか、下位資料を同期するか、重複指摘として閉じるかを記録する。

単に古い文書やコメントに旧状態が残っているだけで、現行正本の解決を取り消してはならない。一方、修正案がDraftブランチに存在するだけの場合や、正式決定・承認・main反映が必要な場合は、解決済みと誤認してはならない。

### 13.4 全体整理完了の判定条件
- 対象範囲はアクティブ3部門（Motor / Battery / DB）と統括直轄の横断管理事項に限定し、未確認範囲を明示する（未回答・根拠未回収はそのまま記録）。
- 全残件にRegister IDまたは既存Canonical Issueを対応付け、重複を識別する。
- 既存解決済み事項は解決根拠・正本・HEAD・反映状況を再確認し、再浮上項目を既存IDへ統合する。
- 各未解決事項に分類、回収可能性、影響範囲、担当、依存、次の行動、完了条件、審査停止要否がある。
- 回収不能・未回答・外部依存は、探索済み範囲と未取得根拠を明記し、解決済みへ偽装しない。
- 全体整理の差分報告をIssue #217へ提出し、ユーザーが全体整理完了を確認した後に限り、新運用による統括審査へ進む。

**このゲートは審査の延期であり、既存の設計承認・実装許可・安全条件を変更しない。**


## 14. 2026-11-22 統括裁定追補 — 診断レポートScope / DB Gate L

### 14.1 共通診断レポート SD-01〜04
正本: [Issue #214 comment 7079414069](https://github.com/hamtech86/mini4wd-ai-system/issues/214#issuecomment-7079414069)。対象は#150/#151旧要件と#205/#206共通診断レポートのScope Disposition。

| ID | Decision | 適用・非適用 | 5軸の現在状態 |
|---|---|---|---|
| SD-01 保存先 | diagnostic-reports/{battery|motor}/{run_id}へ置換 | verification/runsは新規保存先として廃止。既存証跡は不変保持 | DECIDED / REFLECTED（#214/#206コメント） / #206現行実装 / 実環境試験NOT RUN / #206承認PENDING |
| SD-02 Token | masked dialog-only / session-only | MINI4WD_GITHUB_TOKEN環境変数と独立SET TOKEN UIは継承しない。tokenは永続化しない | DECIDED / REFLECTED（#214/#206コメント） / #206現行実装 / 実環境試験NOT RUN / #206承認PENDING |
| SD-03 Physical observation | 共通診断レポートから分離 | Motor physical-verification将来拡張。過去証跡へ後付けしない。#206受入条件外 | DECIDED / REFLECTED / NOT_APPLICABLE（#206共通機能） / NOT_RUN / PENDING |
| SD-04 Full controller/sequence history | 共通診断レポートの必須要件から除外 | ui_eventsは診断スナップショット。完全監査履歴と表現しない | DECIDED / REFLECTED / #206現行実装 / 実環境試験NOT RUN / #206承認PENDING |

#205は共有診断レポート仕様正本、PR #206は唯一の実装候補。PR #206はOPEN/DRAFT/UNMERGED。exact-head CI 5/5 SUCCESSは既存記録を維持するが、target-PC GUI / live upload / 実環境API・network retryはNOT RUN。Scope裁定は実装受入・merge許可ではない。

### 14.2 DB Gate L GL-01〜04
正本: [Issue #207 comment 7079475903](https://github.com/hamtech86/mini4wd-ai-system/issues/207#issuecomment-7079475903)。DB draft branch HEADとして報告された値は `c05e451a7a51ef69729ef677731823bb5430845c`。main反映・DDL・DB生成・Migration・Restore・実装は未実施。

| ID | Decision / scope | 回収可能性 | 5軸の現在状態 |
|---|---|---|---|
| GL-01 UUIDv4 Issuer Authority | Entity Typeごとの単一Issuer Role mapを採用。未登録Roleからの発行禁止。composite/derived identityはUUIDを発行しない | RECOVERABLE（Main §5.1〜5.3にIdentity方式あり） | DECIDED / PARTIAL（Authority Registry map同期待ち） / NOT_STARTED / NOT_RUN / PENDING |
| GL-02 Minimum Schema | 現行運用の共通Envelope・Identity・Authority・Reference・Event境界に限定。23概念すべてを独立Table/UUID化しない。外部Owner未定義Payloadはopaque | RECOVERABLE（Main §14.3 / Event Registry） | DECIDED / PARTIAL（Entity Inventoryの旧UUIDv5記述等の同期待ち） / NOT_STARTED / NOT_RUN / PENDING |
| GL-03 Current Aggregate Outcome | COMPLETE Measurement Outcomeのみ。Capture Ownerの正常終端証拠・必須Sample・Hash/Assignment条件が不足する対象はUNKNOWN/opaqueとして除外。Session Lifecycleとは独立。CH1/CH2平均化禁止 | RECOVERABLE（論理条件）＋Capture適用はCONDITIONALLY_RECOVERABLE | DECIDED / PARTIAL（Capture契約との相互参照待ち） / NOT_STARTED / BLOCKED（契約未受領対象は算入不可） / PENDING |
| GL-04 Motor/Battery Capture Contract | DBは機器固有Capture開始/終端/必須Sample/Outcome/Channel意味を推測補完しない。各Device Ownerの正式契約が必要 | CONDITIONALLY_RECOVERABLE（Motor #35/#170、Battery #16/specは部分根拠。完全契約未受領） | DECIDED（非推測・責任境界） / PARTIAL / NOT_APPLICABLE（受領前） / NOT_RUN / PENDING |

GL-01 Issuer Roleの役割分担は、Run Manager / Assignment Manager / Capture Identity Authority / Profile Authority / Evidence Storage Authority / Operation Authority / Receipt Authority / Artifact Authority / Aggregate Authority / Recovery Authority。実際のPrincipal・Service・Registry登録、乱数源、scope、発行/失効記録は別途必要。DB部門はMain §5.1〜5.3とEntity InventoryのUUIDv4表記を同期する。旧UUIDv5 / Namespace候補を現行未決定事項として再登録しない。

GL-04の限定提出依頼はMotor Issue #35 comment 7079482192、Battery Issue #16 comment 7079482810。全体棚卸しの再依頼ではなく、Capture start/end、COMPLETE条件、必須Sample、RawLog Schema/byte boundary、ID/Hash参照、timestamp、partial/loss/retryの不足契約だけを求める。Motor #170 comment 7079483316にも責任境界を通知済み。

### 14.3 既決定事項の再浮上防止
- CC-03（Issue #210 comment 7076202503）はDECIDED / REFLECTED。MeasurementはRUN_SCOPEへ直接所属し、Sessionは独立Lifecycle Entity。Measurement→Session membership / FKを再OPENしない。
- DB-001〜124の個別追跡・原本回収・全件Crosswalkはユーザー指示により終了済み。再開しない。
- Issue #211はORANGE / 条件付き差戻し、v0.8.3は未承認。GL-01〜03の決定と文書同期・実証・統括承認を混同しない。
- M4W-JCS-1独立実装適合、Filesystem durability、SQLite crash、Backup/Restoreは後続実証Gateであり、未実施をPASSにしない一方、論理決定を未決定へ戻す理由にも使わない。


## 15. 2026-11-23 read-back update — DB GL-01〜03 / GL-04 field mapping / Battery CH1-CH2

本節は2026-11-23の部門追補を提案台帳へ反映する。PR #216は引き続き未承認・未mergeであり、本追補は正式審査・仕様承認・実装受入を意味しない。

### 15.1 DB Gate L — GL-01〜03 document reflection

正本: [Issue #207 comment 7079913094](https://github.com/hamtech86/mini4wd-ai-system/issues/207#issuecomment-7079913094)

- Branch: `db/v0.8.3-followup-remediation-20261121`
- Reported exact HEAD: `5bc0bc530bbbd614454da86093df70ecf086ce9f`
- GL-01 / GL-02 / GL-03: DECISION=DECIDED / DOCUMENT=REFLECTED。
- IMPLEMENTATIONは未着手。VERIFICATIONは未実施、またはCapture契約不足データについてBLOCKED。APPROVAL=PENDING。
- この文書同期をv0.8.3全体承認、DDL、DB生成、Migration、Restore、実装、PR作成/merge、main反映へ拡張しない。
- 旧DB-001〜124の個別追跡・原本回収・全件Crosswalkは終了済みであり、再開しない。

### 15.2 GL-04 — Battery field mapping照会

正本: [Issue #207 comment 7080826716](https://github.com/hamtech86/mini4wd-ai-system/issues/207#issuecomment-7080826716)

現行v0.8.3修正案のread-backで確認できる論理上の候補:
- RUN_SCOPE identity: `(PhysicalRunID, ScopeKey)`。
- Measurement Envelope §7: `Measurement ID / Physical Run ID / Scope Key`、`RawLog Reference / Sample Reference`、`Canonicalization Version / Envelope Hash`。
- Measurement Sample Link: `(MeasurementID, SampleReferenceID, Role, Ordinal)`。
- 共通Envelope: `EntityType / SchemaVersion / EntityID / OwnerReference / CreatedAtUTC / PayloadReference / PayloadHash`。
- RawLog Object、RawLog Reference、Sample Referenceは別概念として保持する。

ただし、Measurement EnvelopeからRUN_SCOPEへの明示Referenceの形、RawLog ReferenceからRawLog Object ID / Object Hashへの結び付け、Sample Referenceの完全な参照方向は、Battery向け回答としてDB部門がIssue #207で明示する必要がある。現行legacy SQLite schemaにScope Key / RawLog Object ID / hash linkがない場合はUNKNOWN/opaque、Aggregate除外、登録fail-closedを維持し、Battery側からschemaを変更しない。

状態: Decision（非推測・責任境界）=DECIDED / Document=PARTIAL / Implementation=NOT_APPLICABLE pending contract / Verification=NOT_RUN / Approval=PENDING。回収可能性=CONDITIONALLY_RECOVERABLE。DB部門への限定field-mapping回答依頼はIssue #207の2026-11-23追補を参照。

### 15.3 Battery CH1 / CH2 independent analysis

正本: [Issue #208](https://github.com/hamtech86/mini4wd-ai-system/issues/208) / [Draft PR #218](https://github.com/hamtech86/mini4wd-ai-system/pull/218)

- Branch: `fix/battery-ch1-ch2-independent-analysis-20261122`
- Base main: `6d075213d4bdf8f5382805daeec4945e2a6c1146`
- Reported current PR head: `c802451864405fc6a029cb5948d5d99b6a9afc27`
- Explicit CH argument per analysis call; selected-channel-only voltage/current/power/capacity/energy; cross-channel averaging, sum, and fallback removed.
- Scope Key is not inferred from column names or Session notes. Missing/contradictory Scope identity is UNKNOWN and fail-closed. Existing average results are not overwritten; analysis version is `battery-benchmark-v2`.
- Raw Measurement / RawLog, DB schema, firmware, control, and hardware are unchanged.
- CI reported: Break-in and Battery Tests #1922 SUCCESS (all jobs); DB Path Safety Phase 2 #651 SUCCESS.
- Status: DECISION=DECIDED / DOCUMENT=REFLECTED / IMPLEMENTATION=COMPLETE on PR branch / VERIFICATION=PASS for reported exact-head CI only / APPROVAL=PENDING. PR #218 remains OPEN/DRAFT/UNMERGED.
- Out-of-range numeric bounds remain undefined / NOT RUN because authoritative limits are unavailable. Real 5A E2E and physical discharge remain NOT RUN under Issue #16, with separate authorization required.
- Recovery: implementation/test evidence RECOVERABLE; historical rows whose CH identity is not explicit CONDITIONALLY_RECOVERABLE.

This item is B — IMPLEMENTATION_VERIFICATION and does not stop DB logical-design review. PR #218 acceptance/merge is not inferred from CI.

### 15.4 Governance status

- Issue #217 remains the cross-department inventory source.
- PR #216 remains OPEN / unapproved / unmerged. This proposal update does not start its formal review.
- Issue #211 remains ORANGE; v0.8.3 remains unapproved.
- PR #183 remains without DESIGN ACCEPTANCE; PR #188 remains pending #183 canonical disposition; PR #184 remains a separate physical safety evidence ledger. Physical PASS=0 and `HARDWARE_CURRENT_LIMIT_CONFIRMED=false`.


## 16. 2026-11-23 follow-up — GL-04 mapping read-back / PR #218 exact-HEAD CI review

### 16.1 DB GL-04 field mapping

Source: [DB department response, Issue #207 comment 7101200440](https://github.com/hamtech86/mini4wd-ai-system/issues/207#issuecomment-7101200440)

- Branch: `db/v0.8.3-followup-remediation-20261121`
- Exact HEAD: `3dc6419c15f63f9b6a870c28414b0ea70edeff17`
- Four existing database draft documents were fetched at this exact HEAD; each returned a content blob and the updated mapping was read back.
- RUN_SCOPE identity is `(PhysicalRunID, ScopeKey)`; Measurement Envelope's PhysicalRunID + ScopeKey is the direct reference. No independent RunScopeID.
- RawLog Object: `RawLogObjectID + ContentHashSHA256`.
- RawLog Reference: `RawLogReferenceID + RawLogObjectID + RawLogObjectContentHash`; referenced object hash must exactly match.
- Measurement Envelope references `RawLogReferenceID`.
- Sample Reference: `SampleReferenceID + RawLogReferenceID + SampleLocator`.
- Measurement Sample Link: `(MeasurementID, SampleReferenceID, Role, Ordinal)`.
- Reference chains are explicitly defined: Measurement → RawLog Reference → RawLog Object; and Measurement → Measurement Sample Link → Sample Reference → RawLog Reference → RawLog Object.
- Legacy SQLite missing Scope / Reference / Hash / Sample Link fields remains fail-closed: no inference, registration reject or UNKNOWN/opaque quarantine, no Current Aggregate inclusion.

Remaining Owner contract gaps: SampleLocator grammar, Role/Ordinal domain and cardinality, multiplicities, device-specific Sample semantics. Motor Issue #35 has no formal response to the limited Capture Contract inquiry in the checked comments. Battery Issue #16 has a partial answer, not a complete contract: Capture start/end events, required COMPLETE sample set, byte-preservation/hash linkage, timestamp ordering, duplicate/partial/retry semantics, and Outcome mapping remain incomplete.

Status: DB-side field mapping DOCUMENT=REFLECTED; complete Motor/Battery Capture contract DOCUMENT=PARTIAL / VERIFICATION=NOT_RUN / APPROVAL=PENDING. This does not reopen GL-01〜03 and does not authorize DB implementation or v0.8.3 approval.

Sources: [Issue #207 mapping response](https://github.com/hamtech86/mini4wd-ai-system/issues/207#issuecomment-7101200440), [Issue #207 structural read-back](https://github.com/hamtech86/mini4wd-ai-system/issues/207#issuecomment-7102618343).

### 16.2 Battery CH1/CH2 PR #218

Source: [Issue #208 review comment](https://github.com/hamtech86/mini4wd-ai-system/issues/208#issuecomment-7102617485)

- PR #218 remains OPEN / DRAFT / UNMERGED.
- Branch: `fix/battery-ch1-ch2-independent-analysis-20261122`
- Base main: `6d075213d4bdf8f5382805daeec4945e2a6c1146`
- Exact HEAD: `c802451864405fc6a029cb5948d5d99b6a9afc27`
- Exact-HEAD PR-triggered workflows: Break-in and Battery Tests run `45034408753` SUCCESS; DB Path Safety Phase 2 run `45034408728` SUCCESS.
- Confirmed: explicit channel required; only selected-channel values are analyzed; cross-channel averaging/summing/fallback removed; UI requires persisted Scope Key and fails closed if absent/ambiguous; no DB schema, RawLog, firmware, control or hardware changes; old averaged results are not overwritten.
- CI is not physical 5A E2E, physical discharge, or out-of-range qualification.
- Additional B — IMPLEMENTATION_VERIFICATION question: current code excludes selected-channel voltage/current values of exactly 0.0 as inactive/missing. Battery Owner must clarify whether zero on the selected channel is always an inactive sentinel or may be a valid measured value, and identify the authoritative field/event that distinguishes them. Until answered, preserve this as an explicit limitation; do not infer numeric range semantics.
- 5-axis: DECISION=CH independence/no averaging DECIDED; DOCUMENT=PARTIAL (Capture semantics); IMPLEMENTATION=COMPLETE on PR branch; VERIFICATION=PASS for exact-HEAD CI only; APPROVAL=PENDING.
- This B item does not reopen design decisions and is not a DB logical-design blocker. No PR acceptance, Ready transition, or merge was performed.

### 16.3 Current governance disposition

- Issue #211 remains ORANGE; v0.8.3 remains unapproved.
- PR #216 remains OPEN / unmerged. This ledger update is on the proposal branch only and does not commence formal review.
- PR #183 remains OPEN/DRAFT without DESIGN ACCEPTANCE; PR #188 remains blocked pending canonical design disposition; PR #184 remains the separate physical evidence ledger.
- Physical PASS=0 and `HARDWARE_CURRENT_LIMIT_CONFIRMED=false`.


## 17. 2026-11-23 310-4 PR #183 design read-back

Source: [PR #183 review comment](https://github.com/hamtech86/mini4wd-ai-system/pull/183#issuecomment-7102649787)

- PR #183 remains OPEN / DRAFT / UNMERGED; exact HEAD `20af72abb6d0fa84b6f2bf31746860d99394d10f`.
- Four artifact blobs at exact HEAD: design `228d60381db61fd75baa7b4ba314e0f246925f29`; decision register `e9268ba413dbc018026f9526dd7915fb5f7a9729`; acceptance tests `65423d102152125c939429e7e1eb87a539ad3085`; final review `d2259baac7c12af2af5aeb30cb884aa132815f05`.
- Exact-HEAD workflows: Break-in and Battery Tests `44974065949` SUCCESS; DB Path Safety Phase 2 `44974065932` SUCCESS. These are CI only.
- Read-back confirms: protocol-v2 / EEPROM logical design adoption and #215 canonical companion; 8,000ms T18 ceiling removed as acceptance gate; 1-second channel half-open loss window implemented in #198; static SRAM .data 146B + .bss 747B = 893B against 900B limit; software STOP-priority evidence exists; physical STOP is not proven; RawLog Evidence companion logical mapping exists but byte-length/completeness fixture/validator remains.
- Remaining items classified as B — IMPLEMENTATION_VERIFICATION: worst-case stack bound/high-water; Evidence companion byte length/completeness fixture. D — EXTERNAL_DEPENDENCY / physical or measurement evidence: ADC reference/accuracy; physical MCU marking/fuse/BOD/power/EEPROM interruption; physical STOP/current cutoff.
- No new A — DESIGN_BLOCKER was identified in this read-back. This is not formal DESIGN ACCEPTANCE.
- A stale row remains in the Decision Register: channel loss window still described as “window width/granularity undefined,” despite the later 2026-11-22 addendum recording the implemented 1-second window. PR #183 author was asked to synchronize the original row to resolved status, not merely rely on a later superseding note.
- Formal DESIGN ACCEPTANCE remains PENDING. No Ready transition, merge, implementation, hardware action or 310-5 transition was authorized. `HARDWARE_CURRENT_LIMIT_CONFIRMED=false`.



## 18. 2026-11-23 follow-up — Owner Capture gaps / 310-4 stale-row status

### 18.1 Battery selected-channel zero semantics

Source: [統括 read-back, Issue #208 comment 7102617485](https://github.com/hamtech86/mini4wd-ai-system/issues/208#issuecomment-7102617485)

- Re-fetched all Issue #208 comments after the request. No Battery Owner response was present after the 2026-11-23 question.
- Question remains narrow: whether selected-channel voltage/current exactly 0.0 is always an inactive sentinel, may be a valid measured sample, or needs another authoritative Field/Event to distinguish the cases.
- Do not infer numeric semantics. Keep current implementation limitation explicit; do not convert this into a new CH-independence design question or a DB logical-design blocker.
- Classification: B — IMPLEMENTATION_VERIFICATION; recovery: CONDITIONALLY_RECOVERABLE (requires Battery Owner's authoritative Capture semantics or explicit limitation); status DOCUMENT=PARTIAL / VERIFICATION=NOT_RUN for zero semantics / APPROVAL=PENDING. PR #218 remains OPEN/DRAFT/UNMERGED at c802451864405fc6a029cb5948d5d99b6a9afc27; its two exact-head CI workflows remain SUCCESS. No acceptance or merge.

### 18.2 Motor GL-04 Capture Contract

Source: [統括 limited inquiry, Issue #35 comment 7079482192](https://github.com/hamtech86/mini4wd-ai-system/issues/35#issuecomment-7079482192)

- Re-fetched Issue #35 comments. No Motor Owner response to the limited GL-04 Capture Contract inquiry was present.
- Missing contract remains: explicit Capture start/normal end and STOP/ERROR/CANCEL/interruption/loss events; COMPLETE required Record/Sample set and duplicate/order handling; RawLog v2 framing/byte boundaries/ID/hash targets; timestamp basis/precision/wrap/order; A0/A1/A4/A5 semantics and Scope mapping; partial/loss/save/retry evidence semantics.
- This is not a request to repeat the whole department inventory. Existing A0/A1 separation and other established decisions remain unchanged.
- Classification: GL-04 Owner dependency / CONDITIONALLY_RECOVERABLE; requires Motor Owner's formal Issue #35 source update. Until received, DB retains opaque/UNKNOWN treatment and does not infer COMPLETE or Aggregate eligibility. Does not reopen GL-01〜03 or stop unrelated logical design work.

### 18.3 PR #183 Decision Register stale row

Source: [統括 read-back, PR #183 comment 7102649787](https://github.com/hamtech86/mini4wd-ai-system/pull/183#issuecomment-7102649787)

- Re-fetched PR #183 metadata, discussion, changed-file list, and the Decision Register at exact HEAD 20af72abb6d0fa84b6f2bf31746860d99394d10f.
- The Decision Register still contains the row “チャンネル別・期間別損失 ... window幅・粒度は未定”. A later row records the PR #198 implementation (WINDOW_US=1,000,000; channel-specific 1-second half-open window), so the older row is stale and must be synchronized in place.
- No author correction was present in the checked PR discussion. This remains a documentation synchronization task, not a new design decision and not grounds to reopen the resolved loss-window item.
- PR #183 remains OPEN/DRAFT/UNMERGED; formal DESIGN ACCEPTANCE remains PENDING. The already-recovered exact-head CI results are unchanged; no acceptance, Ready transition, merge, or hardware action.

### 18.4 Governance disposition

- DB GL-04 field mapping remains DOCUMENT=REFLECTED; complete Motor/Battery Owner Capture Contract remains PARTIAL.
- PR #216 remains a proposal branch / OPEN / unmerged; this section is a ledger proposal update only, not formal review or approval.
- PR #183 stale-row correction, PR #218 0.0 semantics, and Motor #35 contract response remain independently tracked. Do not merge these into a single blocker or reopen resolved decisions.
- Issue #211 remains ORANGE; DB v0.8.3 remains unapproved; PR #188 remains blocked pending #183 canonical disposition; PR #184 remains the separate physical evidence ledger. Physical PASS=0 and HARDWARE_CURRENT_LIMIT_CONFIRMED=false.


## 19. 2026-11-23 DB Logical Residual Register / GL-04 circular inquiry closure

Source: [統括裁定 Issue #217 comment 7103027852](https://github.com/hamtech86/mini4wd-ai-system/issues/217#issuecomment-7103027852), [統括指示 Issue #207 comment 7103140455](https://github.com/hamtech86/mini4wd-ai-system/issues/207#issuecomment-7103140455), [DB部門 Residual Register Issue #207 comment 7103330423](https://github.com/hamtech86/mini4wd-ai-system/issues/207#issuecomment-7103330423).

### 19.1 Closed: DB field mapping / cross-department inquiry
- RUN_SCOPE identity = (PhysicalRunID, ScopeKey); Measurement Envelope's same two fields directly reference it; no independent RunScopeID.
- RawLog Object = RawLogObjectID + ContentHashSHA256; RawLog Reference = RawLogReferenceID + RawLogObjectID + RawLogObjectContentHash, with exact object-hash equality.
- Measurement Envelope → RawLogReferenceID; Sample Reference = SampleReferenceID + RawLogReferenceID + SampleLocator; Measurement Sample Link = (MeasurementID, SampleReferenceID, Role, Ordinal).
- Legacy schema missing required fields: no inferred registration; reject or quarantine as UNKNOWN/opaque; exclude from Current Aggregate.
- This field mapping is confirmed in the v0.8.3 Draft. Battery/Motor must not be asked again to clarify the same DB mapping. The GL-04 cross-department circular inquiry is closed; Owner Capture contract gaps remain separate.

### 19.2 DB Owner logical residuals — proposal submitted for central decision

At DB Draft exact HEAD `7d8716158ff058f0df05cd77ac1d862aa1af5886`, the four documents were reconciled against existing Main rules. The previous blanket statement that all Role / Ordinal rules were undefined was too broad: Main §14.5.4 already defines their generic policy.

- **DB-LR-01 SampleLocator:** Main §14.6.4 only allows interpretation by the issuing Owner Schema; undefined Locator remains opaque and no time/channel/sample ordinal is inferred. A universal grammar, empty-value rule, and maximum length have NO_CURRENT_BASIS. DB proposal: Owner-Schema-defined opaque UTF-8 value, exact preservation without trim/case-fold/Unicode normalization, parser only for known SchemaVersion. Empty / max length await central decision.
- **DB-LR-02 Role:** Main §14.5.4 already requires non-NULL Role, permits only values defined by the Measurement Type's formal Owner Contract, and rejects unknown Role. There is no DB-global vocabulary; the exact values remain Owner Contract data. Status: DECIDED in Main / supplementary inventory synchronization required.
- **DB-LR-03 Ordinal:** Main §14.5.4 already defines 1-based contiguous Ordinal, unique and non-reusable within (MeasurementID, Role). Status: DECIDED in Main / supplementary inventory synchronization required.
- **DB-LR-04 cardinality:** Link composite identity and Required=true semantics exist, but complete Measurement↔RawLogReference / Measurement↔SampleLink multiplicity, sharing rules, and complete FK/UNIQUE behavior have NO_CURRENT_BASIS. DB proposal for central decision: each Link references exactly one Measurement and one SampleReference; Measurement has 0..N Links; each SampleReference belongs to exactly one RawLogReference; one RawLogReference may have 0..N SampleReferences. Because the Envelope currently names singular `RawLogReferenceID`, recommend 0..1 RawLogReference per Measurement and require all its linked SampleReferences to resolve to that same reference. If multi-RawLog-per-Measurement is required, a separate field-shape decision is needed. Sharing of a RawLogReference across Measurements and SampleReference reuse across Links remain undecided.

Detailed proposed wording, five-axis states, evidence, and decision questions are in [DB Draft Main §7.2 at exact HEAD](https://github.com/hamtech86/mini4wd-ai-system/blob/db/v0.8.3-followup-remediation-20261121/docs/database/COMMON_DB_LOGICAL_DESIGN_v0.8.3_REMEDIATION_DRAFT.md#L248-L340) and [Issue #207 comment with DB Logical Residual Register](https://github.com/hamtech86/mini4wd-ai-system/issues/207#issuecomment-7103330423) (updated proposal report to follow).

### 19.2.1 Five-axis status / recovery classification

| ID | DECISION | DOCUMENT | IMPLEMENTATION | VERIFICATION | APPROVAL | Recovery |
|---|---|---|---|---|---|---|
| DB-LR-01 | OPEN (proposal awaiting decision) | PARTIAL | NOT_STARTED | NOT_RUN | PENDING | NO_CURRENT_BASIS for a universal grammar; DB can propose Owner-Schema delegation |
| DB-LR-02 | DECIDED (Owner Contract token policy) | PARTIAL (Main rule exists; inventory sync) | NOT_STARTED | NOT_RUN | PENDING | RECOVERABLE from Main §14.5.4 |
| DB-LR-03 | DECIDED (1-based contiguous per Measurement+Role) | PARTIAL (Main rule exists; inventory sync) | NOT_STARTED | NOT_RUN | PENDING | RECOVERABLE from Main §14.5.4 |
| DB-LR-04 | OPEN (multiplicity proposal awaiting decision) | PARTIAL | NOT_STARTED | NOT_RUN | PENDING | NO_CURRENT_BASIS for full multiplicity; logical proposal submitted |

The proposed definitions are not decisions or implementation authorization. Owner-specific Sample meaning, required sample set, and Capture semantics remain with Motor / Battery Owners. Until central decision and formal Owner contracts, unknown data remains opaque, cannot become COMPLETE, and is excluded from Current Aggregate.

### 19.3 Owner Capture semantics remain external
- Motor Capture events, required samples, RawLog framing/bytes, timestamps/sequences, partial/loss/retry semantics belong to Motor Owner / Issue #35.
- Battery Capture and channel/ADC/zero validity semantics belong to Battery Owner / Issue #16 and the external firmware source.
- DB does not define device-specific meaning. Missing/undefined Owner contract remains UNKNOWN/opaque; no COMPLETE classification or Current Aggregate inclusion.
- Do not restart DB↔Motor/Battery mapping questions. Do not reopen GL-01〜03 decisions.

### 19.4 Governance status
- DB v0.8.3 remains unapproved; Issue #211 remains ORANGE.
- PR #216 remains proposal-only, OPEN/unmerged, and not formally reviewed or approved.
- No DDL, DB generation, Migration, Restore, schema change, implementation PR, merge/main update, or hardware operation.
- This entry is a proposal-ledger synchronization only and does not grant acceptance or implementation authority.


### 19.5 2026-11-24 統括決定 CC-04 / Owner Evidence Matrix read-back（旧提案状態を置換）

Sources: [CC-04 Issue #210 comment #7129872294](https://github.com/hamtech86/mini4wd-ai-system/issues/210#issuecomment-7129872294), [統括指示 Issue #207 comment #7129889629](https://github.com/hamtech86/mini4wd-ai-system/issues/207#issuecomment-7129889629), [横断再審査 Issue #211 comment #7129906998](https://github.com/hamtech86/mini4wd-ai-system/issues/211#issuecomment-7129906998).

This section supersedes the pending/proposed decision values in §19.2 and §19.2.1. Earlier proposal history is retained for audit; it is not current status.

- DB-LR-01 SampleLocator: **DECIDED** — no DB-global grammar; Owner Schema + exact SchemaVersion owns interpretation; opaque UTF-8 lossless preservation; zero-length string invalid; no common logical max length; explicit implementation limit with reject/quarantine; no trim, normalization, truncation, or inferred semantics.
- DB-LR-02 Role: **DECIDED** by Main §14.5.4 — non-NULL; only formal Measurement Type Owner Contract tokens; unknown Role rejected; no DB-global vocabulary.
- DB-LR-03 Ordinal: **DECIDED** by Main §14.5.4 — 1-based contiguous, unique, non-reusable within (MeasurementID, Role).
- DB-LR-04 cardinality: **DECIDED** — Measurement→RawLogReference 0..1; if Sample Links exist, exactly one RawLogReference is required; Measurement→Sample Link 0..N; each Link exactly one Measurement + one SampleReference; each SampleReference exactly one RawLogReference; RawLogReference at most one Measurement; SampleReference at most one Link; no implicit sharing; Required Role/Ordinal set is Owner Contract-defined.

| ID | DECISION | DOCUMENT | IMPLEMENTATION | VERIFICATION | APPROVAL | Recovery |
|---|---|---|---|---|---|---|
| DB-LR-01 | DECIDED | REFLECTED after CC-04 sync | NOT_STARTED | NOT_RUN | PENDING | NO_CURRENT_BASIS for a universal grammar; owner-schema delegation is now decided |
| DB-LR-02 | DECIDED | REFLECTED | NOT_STARTED | NOT_RUN | PENDING | RECOVERABLE from Main §14.5.4 |
| DB-LR-03 | DECIDED | REFLECTED | NOT_STARTED | NOT_RUN | PENDING | RECOVERABLE from Main §14.5.4 |
| DB-LR-04 | DECIDED | REFLECTED after CC-04 sync | NOT_STARTED | NOT_RUN | PENDING | Proposal is now decided; implementation evidence remains future work |

### 19.6 Owner Capture evidence received — contract remains partial
- Motor Issue #35 comment #7120818752 (M-01〜M-09 Evidence Matrix): RECEIVED; Motor evidence organization task is complete. No repeated evidence-matrix request. M-04 normative SPEC source remains PARTIAL unless formally identified; CODE/tests are implementation evidence.
- Battery Issue #16 comment #7105933799 (seven-domain Evidence Matrix): RECEIVED; Battery evidence report is accepted for this inventory. PR #218 remains a separate OPEN/DRAFT/UNMERGED implementation review; CI PASS does not equal merge or physical 5A E2E verification.
- Both Owner reports are received, but formal device Capture Contracts remain PARTIAL for normative end conditions, required sample sets, Outcome mapping, and physical verification. This is not “report missing”. DB Field Mapping remains DECIDED/REFLECTED. Do not re-query Motor/Battery for the same DB mapping.
- GL-04 five-axis: DECISION=DECIDED (non-inference / responsibility boundary); DOCUMENT=PARTIAL (Owner evidence received; normative Capture contracts incomplete); IMPLEMENTATION=NOT_APPLICABLE before applicable Owner contract; VERIFICATION=NOT_RUN; APPROVAL=PENDING.
- Unknown Owner semantics remain UNKNOWN/opaque, cannot be inferred COMPLETE, and are excluded from Current Aggregate.

### 19.7 Authority and approval boundary
- DB v0.8.3 remains unapproved pending separate final review. PR #216 remains OPEN / unmerged / not formally approved.
- No DDL, DB generation, schema change, Migration, Restore, implementation PR, merge/main update, or hardware operation is authorized by CC-04 or this ledger synchronization.
- Do not reopen CC-03, GL-01〜03, confirmed Field Mapping, or closed DB-001〜124 tracking. Earlier text in §19.2/19.2.1 is historical proposal state only and must not be used as current status.


### 19.8 2026-11-24 統括決定 CC-05 — DB-RV-02〜08

Source: [Issue #210 comment #7130272797](https://github.com/hamtech86/mini4wd-ai-system/issues/210#issuecomment-7130272797). This decision supersedes the historical "統括承認待ち" status for DB-RV-02〜08 in §19. Earlier investigation entries remain audit history only.

- DB-RV-01: already DECIDED by CC-01 / CC-03.
- DB-RV-02〜08: DECIDED by CC-05. DB Run lifecycle, Receipt persistence order, Aggregate Request/Attempt/Revision, immutable Artifact DAG, UUIDv4 + M4W-JCS-1 identity/hash, external source vs DB Mirror boundary, and Assignment/Current Aggregate eligibility are now selected at the logical-design level.
- DB-RV-06 explicitly rejects UUIDv5 / Namespace / Canonical Binary Name v2 as new v0.8.3 issuance schemes. Existing IDs are not changed.
- Implementation and verification remain separate: IMPLEMENTATION=NOT_STARTED; VERIFICATION=NOT_RUN. Hardware, crash durability, independent JCS conformance, CSPRNG, Owner Capture Contract and restore evidence remain their respective gates.
- DB-RV-01〜08 DECISION_STATUS=DECIDED. DOCUMENT_STATUS=REFLECTED after the CC-05 synchronization across Main, Entity Inventory, Cross-Document Audit and Self Review. v0.8.3 overall approval remains PENDING; PR #216 remains unmerged.
- CC-05 does not authorize DDL, schema change, DB generation, Migration, Restore, implementation PR, merge, main update, or hardware operation.
- Do not reopen CC-01〜05, GL-01〜03, DB Field Mapping, or closed DB-001〜124 tracking. Do not re-ask Motor/Battery for DB mapping. Their Evidence Matrices are RECEIVED; normative Capture Contract gaps remain Owner-specific gates.

| Gate | Decision | Document | Implementation | Verification | Overall approval |
|---|---|---|---|---|---|
| DB-RV-01〜08 | DECIDED | REFLECTED | NOT_STARTED | NOT_RUN | v0.8.3 PENDING |
| GL-04 | DECIDED responsibility boundary | PARTIAL (Owner evidence received; formal Capture Contract incomplete) | NOT_APPLICABLE until Owner Contract | NOT_RUN | PENDING |
| DB v0.8.3 overall | — | Draft synchronized | NOT_STARTED | NOT_RUN | PENDING |


### 19.9 2026-11-24 統括最終受入レビュー — DB v0.8.3 Decision Baseline / 後続Gate分類

Source: [Issue #211 final acceptance review comment #7130987157](https://github.com/hamtech86/mini4wd-ai-system/issues/211#issuecomment-7130987157), [CC-04 #7129872294](https://github.com/hamtech86/mini4wd-ai-system/issues/210#issuecomment-7129872294), [CC-05 #7130272797](https://github.com/hamtech86/mini4wd-ai-system/issues/210#issuecomment-7130272797).

**Review disposition:** DB v0.8.3 logical Decision Baseline is conditionally acceptable. This is not approval of v0.8.3 as a whole, not implementation acceptance, and not authorization to merge this ledger PR or any implementation PR.

- Reviewed DB Draft branch `db/v0.8.3-followup-remediation-20261121`, exact HEAD `4bf7f49abc79fe4b84820e86ebcc13d2d08c9b29`; four Draft documents were read back at that same SHA.
- CC-01〜05, DB-RV-01〜08, and DB-LR-01〜04 are DECIDED; their decision state must not be reopened because implementation or verification is pending.
- The old V083-RV-01〜05 and DB-LR-01〜04 proposal/pending entries in earlier sections are retained as audit history. Current state is defined by §19.5, §19.8, the four synchronized Drafts, and this §19.9.
- No evidence-supported A — DESIGN_BLOCKER remains in the reviewed logical Decision Baseline. GL-04 Owner-specific semantics remain opaque/UNKNOWN and excluded from COMPLETE / Current Aggregate; this is a bounded Owner gate, not permission to infer missing semantics.

#### 19.9.1 Remaining gates — ownership, recoverability, and disposition

| Gate | Class | Recovery | Owner / dependency | Current status and next action | Stops logical design review? |
|---|---|---|---|---|---|
| GL-04 Motor formal Capture Contract | D + E | CONDITIONALLY_RECOVERABLE | Motor Owner; Issue #35 | M-01〜M-09 Evidence Matrix received. Only normative gaps remain: start/end and terminal Outcome contract, required Record/Sample set, retry/loss semantics, and authoritative SPEC location. Update Issue #35 only where the Owner can provide a normative source or explicitly declare NO_CURRENT_BASIS. Until then DB remains UNKNOWN/opaque. | NO |
| GL-04 Battery formal Capture Contract | D + E | CONDITIONALLY_RECOVERABLE | Battery Owner; Issue #16 and external FW authority | Seven-domain Evidence Matrix received. Remaining normative gaps include Capture start/end, required COMPLETE sample set, byte/hash linkage, timestamp order, duplicate/partial/retry semantics, and Outcome mapping. No repeat Evidence Matrix or DB mapping request. Owner may provide formal source or explicitly mark unsupported items NO_CURRENT_BASIS. | NO |
| Motor M-04 normative SPEC source | E | NO_CURRENT_BASIS (current checked record) | Motor Owner; Issue #35 | Code/tests evidence exists, but a distinct normative SPEC location has not been established. Keep SPEC=PARTIAL / CODE=IMPLEMENTED. Do not relabel code comments/tests as normative SPEC. | NO |
| Motor physical benchmark / timestamp accuracy / physical STOP and current limit | D | CONDITIONALLY_RECOVERABLE | Motor Owner + physical equipment / user authorization; Issue #172 | NOT_RUN / NOT_CONFIRMED. Requires approved safety review, equipment, and explicit user authorization before any physical operation. `HARDWARE_CURRENT_LIMIT_CONFIRMED=false` remains. | NO |
| Battery selected-channel 0.0 validity | B + D | NO_CURRENT_BASIS for current semantic distinction; conditionally recoverable only if Owner supplies an authoritative validity contract or new evidence | Battery Owner / external FW authority; Issue #208 and PR #218 | FW rounds current below 0.01A to 0.0 and no validity discriminator is evidenced. Keep selected-channel 0.0 as UNKNOWN / fail-closed; preserve raw values. Do not infer inactive sentinel. | NO |
| Battery 5A physical E2E / expected-value validation | D + B | CONDITIONALLY_RECOVERABLE | Battery Owner + physical sample/fixture and authorized test setup; Issue #16 | NOT_RUN. Requires known-origin 5A dataset or reproducible fixture plus expected values; physical discharge requires separate explicit authorization. | NO |
| DB UUIDv4 issuance / CSPRNG / M4W-JCS-1 / Golden Vectors | B | CONDITIONALLY_RECOVERABLE | DB implementation owner; target runtime and implementation authorization | Logical choices DECIDED; implementation NOT_STARTED; independent conformance and entity-specific issuance-path verification NOT_RUN. Build deterministic vectors and runtime evidence only after implementation authorization. | NO |
| DB Receipt / Journal / SQLite transaction and crash recovery | B | CONDITIONALLY_RECOVERABLE | DB implementation owner; target OS/runtime and authorized test environment | Logical sequence DECIDED; implementation NOT_STARTED; verification NOT_RUN. Requires implementation authorization, crash-injection environment, and exact-head tests. | NO |
| RawLog filesystem durability / read-back / fsync / rename | B + D | CONDITIONALLY_RECOVERABLE | DB / storage implementation owner; target OS, filesystem, mount, and test medium | Logical acceptance conditions DECIDED; target-environment durability evidence NOT_RUN. Do not mark Durable / VERIFIED before environment-specific proof. | NO |
| Restore Phase A/B and source-to-mirror consistency | B | CONDITIONALLY_RECOVERABLE | DB implementation owner; approved backup/restore test environment | Two-phase rule DECIDED; implementation and restore exercise NOT_RUN. No Restore execution is authorized by this review. | NO |
| PR #218 Battery CH1/CH2 code acceptance | B | RECOVERABLE for source/CI review; physical E2E remains CONDITIONALLY_RECOVERABLE | Battery Owner / authorized reviewer; PR #218 | PR remains OPEN / DRAFT / UNMERGED. CI SUCCESS is confirmed on reviewed HEAD. Source review found two P1 fail-closed gaps: Service does not verify requested channel against persisted Session/Measurement Scope Keys; DB UI ignores Measurement rows with NULL Scope Key when deriving a distinct channel. Code acceptance remains PENDING until both are fixed with missing/mixed/mismatch tests. Findings: PR #218 comment #7131413650. Physical 5A E2E remains NOT_RUN. | NO |
| Governance ledger PR #216 acceptance | B / governance | RECOVERABLE |統括; PR #216 | This section updates the proposal ledger only. PR #216 remains OPEN / unmerged; formal review and merge are separate explicit actions. | NO |

#### 19.9.2 Five-axis state after final review

| Area | DECISION_STATUS | DOCUMENT_STATUS | IMPLEMENTATION_STATUS | VERIFICATION_STATUS | APPROVAL_STATUS |
|---|---|---|---|---|---|
| CC-01〜05 / DB-RV-01〜08 / DB-LR-01〜04 | DECIDED | REFLECTED in four Drafts | NOT_STARTED | NOT_RUN | v0.8.3 overall PENDING |
| GL-04 responsibility boundary | DECIDED | PARTIAL — Owner evidence received, formal normative contracts incomplete | NOT_APPLICABLE until applicable Owner contract / authorization | NOT_RUN | PENDING |
| Motor physical gate | Existing logical boundaries DECIDED | Evidence Matrix RECEIVED | Existing software evidence only | Physical NOT_RUN | PENDING |
| Battery 0.0 / 5A E2E gate | CH independence DECIDED; zero semantics UNKNOWN | Evidence Matrix RECEIVED; contract PARTIAL | PR #218 OPEN / DRAFT | CI SUCCESS only; physical 5A E2E NOT_RUN | PENDING |
| DB implementation / durability / restore gates | Logical requirements DECIDED | REFLECTED | NOT_STARTED | NOT_RUN | PENDING |
| DB v0.8.3 overall | — | Draft only | NOT_STARTED | NOT_RUN | PENDING |

#### 19.9.3 Re-entry and anti-resurfacing rule

1. A closed decision reopens only on new contradictory evidence that identifies the exact affected rule, source, and impact. Historical OPEN wording, missing implementation, or NOT_RUN verification is not contradictory evidence.
2. Owner reports already received are not requested again. Ask only for a missing normative source or a specifically identified new fact; if none exists, record NO_CURRENT_BASIS and retain the fail-closed disposition.
3. Every follow-up updates the relevant canonical Issue and links this ledger; do not create duplicate issue trackers for the same gate.
4. No gate above authorizes DDL, schema change, DB generation, Migration, Restore execution, implementation PR merge, main update, firmware change, physical energization, or hardware measurement.
5. Overall v0.8.3 approval, PR #216 merge, PR #218 merge, and physical test authorization remain separate explicit decisions.


## 20. 2026-11-26 統括終結処置 — 初回全体棚卸し完了・ロードマップ再開

本節は、§19.4 / §19.7 / §19.9等に残る過去時点のOPEN・ORANGE・未受領表現を、2026-11-26時点の現在状態として誤用しないための最新状態記録である。過去記述は監査履歴として保持し、本節を現在状態の優先記録とする。

### 20.1 全体棚卸しの完了判定
- アクティブ部門はMotor / Battery / DBの3部門。3部門の初回棚卸し回答は受領済み。非アクティブ領域を独立部門の未回答として扱わない。
- Motor Evidence Matrix、Battery Evidence Matrix、DB v0.8.3 Decision Baselineおよび後続Gateの統括read-backは実施済み。
- 旧DB-001〜124の個別追跡・全件Crosswalkは終了済み。既回答Field Mappingや既決定論点の再照会・再審査は禁止。
- 未実施の実装・耐久性検証・Owner Capture Contract・実機試験は、各正本Issueの後続Gateとして残す。これらは初回棚卸しの未完了を意味せず、ロードマップ再開を妨げない。
- 初回全体棚卸しIssue #217は、上記の受入確認をもって完了・クローズする。

### 20.2 DB審査状態の訂正
- DB v0.8.3 Decision Baseline: CONDITIONAL ACCEPTED / LOGICAL DESIGN REVIEW CLOSED（Issue #211 comment #7174282529）。
- DB-RV-01〜08、DB-LR-01〜04、CC-01〜05はDECIDED。具体的な新規矛盾・反証がない限り再OPENしない。
- Issue #211は後続Gateの追跡先としてOPENを維持する。旧タイトル・本文のORANGE条件付き差戻しは歴史的審査記録であり、現在の論理設計審査状態ではない。
- DDL/schema/DB生成/Migration/Restore/実装PR/merge/main反映は本節で許可されない。従来のユーザー承認境界を維持する。

### 20.3 台帳PRとロードマップの関係
- PR #216はガバナンス台帳の提案PR。文書レビューはACCEPTABLE AS GOVERNANCE REGISTER DRAFT（PR comment #7131360562）。
- PR #216のmergeは別個の明示判断事項であり、未mergeを理由にロードマップを停止しない。PR #216はOPEN / UNMERGEDを維持する。
- PR #216の正式merge、PR #218のmerge、実装権限、実機操作許可はそれぞれ独立した承認事項であり、本節では実施・許可しない。

### 20.4 ロードマップ再開規則
- 全体棚卸し・初回分類のGateはCLOSED。ロードマップ工程1〜6へ復帰可能。
- 次の実作業は工程1「DB RawLog v2対応」の実装準備。DB部門は既決Decision Baselineに基づくGap / target files / sequence / tests / rollback・failure isolationを一括提示する。
- 工程2〜6は依存関係に従い並行準備する。実装・merge・実機操作は個別の承認境界を守る。
- 新しい矛盾が見つかった場合は該当する正本Issueだけを更新し、全体棚卸しを再OPENしない。
- 各GateのNOT RUNはそのGateにのみ適用し、決定済み設計・完了済み棚卸しへ転記しない。

**統括最終状態:** INITIAL_CROSS_DEPARTMENT_INVENTORY = COMPLETE / CLOSED。ROADMAP = REOPENED。PR #216 = OPEN / UNMERGED（非ブロッカー）。Issue #211 = OPEN（後続Gate追跡、論理設計審査は終結）。
