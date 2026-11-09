# 310-5 リスクベース再評価 — 2026-11-09

## 目的・判定境界

Issue #35の2026-11-09司令塔方針に従い、310-5の既存要求・試験・ブロッカーをリスクと実装コストに照らして再分類する。本書は設計判断の候補と現在の証拠を整理するものであり、310-5受入、310-6移行、実機作業の許可ではない。

分類:
- KEEP: 具体的な故障経路または運用上の必要性があり維持する。
- RELAX: 目的は維持するが、過剰な網羅性・完全性・閾値を緩和する。
- REMOVE: 現在の合否条件から除外する。
- INVESTIGATE: 現物・回路・仕様・確率等の根拠が不足し、結論を保留する。

## 現状証拠の基準点

- PR #193 HEAD: b752a691a79676c6992aa93b867e9a2d708a6474
- Hosted T18: 31 stages、3,100 ADC batches、37,200 ADC slots、10,143 Evidence events、最大1,606.381ms。310 loss windows PASS、RawLog validation errors 0、Evidence bundle verified。
- Hosted regression: 4 jobs PASS、628 passed / 2 xfailed。
- Target-hostの過去runは、PR #193のdurable-batching変更を含まない旧実装で全stageが8秒を超えたためFAIL扱いとなった。これは新HEADのtarget-host実測ではない。
- PR #193 exact HEADでのtarget-host再測定はNOT RUN。GitHub-hosted runはtarget PC/storageの代替ではない。
- R01のpersistent marker checkはProtocol V1/V2およびSequenceControllerのstage-send境界へ統合済み。ただしActuationSafetyJournal lifecycle、operator reconciliation/release、過去nonzero command全件のphysical safe-state証拠は未完了。
- HW01–HW08の物理試験は未実施・未承認。HARDWARE_CURRENT_LIMIT_CONFIRMED=false。

## リスク別再分類

| 要求 / 試験 | 分類 | 故障シナリオ・影響 | 発生可能性の根拠 | 運用者対処 | 対応・コスト判断 | 現在の状態 |
|---|---|---|---|---|---|---|
| STOP後 / reset後の自動再始動防止 | KEEP | 古い指令再実行により意図しない回転 | ソフトウェア経路・電源断後の実機頻度は未測定。再始動が発生すれば回転する | 主電源遮断。再開前に状態確認 | 複雑なreset予防ではなく、boot時出力OFF、ARM無効、古い指令破棄を維持 | ソフトウェア試験あり。実機NOT RUN |
| reset自体の完全防止 | REMOVE | MCU resetそのもの。reset後に自動再始動しないならresetだけで駆動再開には至らない | 実機発生率は不明。プロジェクト上resetは起こり得る前提 | reset後の状態表示・再確認 | resetゼロ化のための追加保護は目的にしない | 設計方針変更 |
| heartbeat / status表示 | KEEP | MCUフリーズ・通信断を稼働中と誤認 | 現行UI未実装のため頻度不明 | 表示で状態確認、反応しない場合は主電源遮断 | RUN/STOP/通信不明/応答停止を識別する最小表示を優先 | 未実装 |
| 独立STOP回路・driver cutoff | INVESTIGATE | MCU/通信が停止要求を処理できずモーター出力が残る | 実機故障率・停止不能時の影響は未測定 | 手の届く主電源スイッチで遮断 | 一律必須とせず、主電源遮断性・回転の危険・追加回路コストを比較。電気事故防止に必要な遮断は別扱い | 回路/配線証拠不足 |
| 外部voltage supervisor / BOD | INVESTIGATE | 電源低下・過渡でMCU誤動作、または電源条件逸脱による損傷 | MCU実装型番、電源条件、過渡波形未取得 | 電源遮断・電源条件是正 | reset予防と損傷予防を分離。実チップdatasheetと電源/過渡/逆電圧を確認して必要な保護を選ぶ | 型番・回路・波形なし |
| EEPROM全write境界の電源断試験 | RELAX / INVESTIGATE | boot epoch / journal破損、再起動後の状態誤認 | 実機の電源断時挙動は未測定。全境界を試す費用は高い | 自動再始動させず、必要なら主電源遮断・再初期化 | すべてのbyte境界網羅は要求しない。永続boot identityが安全動作に不可欠な境界に限定 | native emulatorのみ。実機NOT RUN |
| RawLog/Evidenceの全件完全保存 | RELAX | 初期テレメトリ欠損・解析不能 | target-host runで保存遅延を実測。欠損率の運用実績はまだ少ない | 欠損表示、必要なら測定をやり直す | 全サンプル完全保存を安全要件にしない。欠損は明示し、頻発時に改善 | hosted検証PASS。target exact HEAD未測定 |
| command intent / ACK / outcome UNKNOWN | KEEP（実装簡素化） | コマンド送達結果不明のまま再送・自動再開し二重駆動 | write/flush/ACKの失敗経路はテスト済み。実機頻度は未測定 | 状態をUNKNOWN表示し、判断不能なら主電源遮断 | UNKNOWNをSUCCESSにしない、自動再送しない、自動再開しない。全イベント同期fsync/hash chainや全commandの独立物理確認を一律要求するかは再検討 | persistent marker integrationあり。R01 lifecycle未完了 |
| ADC A0/A1/A2/A3/A4/A5の欠損 | RELAX | 測定解析の欠損。制御用途外のチャンネル欠損を停止扱いする過剰反応 | 実機ADC誤差・欠損率未測定 | 欠損/無効を表示し、解析から除外 | A0巻線電流・A4/A5電圧と、A1独立観測・A2/A3参考値を分離。A1/A2/A3欠損を制御停止へ混在させない | ソフトウェアaccountingあり。物理精度NOT RUN |
| ADC連続3回失敗で停止 | INVESTIGATE | 制御入力欠損の継続、または単なる分析データ欠損 | 3回の物理的根拠・失敗率との関係が示されていない | 欠損表示、必要な場合は手動停止 | 3回を絶対閾値にしない。制御に実際に使う信号と測定品質用信号を分離し、根拠を示せる場合のみ閾値化 | native testsあり。閾値根拠未確認 |
| T18 8,000ms ceiling | REMOVE | stage処理/保存が8秒を超える | 8秒は10秒からSTOP reserve 1秒+margin 1秒を差し引いた設計配分であり、実害・停止遅延の実測根拠ではない | 遅延内容を確認し、実害がある場合に改善 | 8秒超過のみでFAILにしない。時間は診断値として残す | PR #193 codeで合否ゲート除去を実装中 |
| T18 target-host profile | KEEP（診断） | 保存・fsync・finalize・recoveryの実態が見えない | 旧実装のtarget-host runでp50 24.5秒、max 32.6秒。これは性能実態の証拠であり危険確率の証拠ではない | 異常な遅延時は結果を確認し必要に応じて再測定 | 新HEADで実測し、遅延を分解する。8秒達成は要求しない。データ破損やSTOP阻害など具体的実害がなければ性能値のみで工程を停止しない | exact HEAD target-host NOT RUN |
| SRAM 900B / stack 700B / reserve 448B | INVESTIGATE | stack overflow、メモリ破壊、UART/ADC workspace破損 | 静的監査はあるが実機stack watermark・最悪実行時の占有率なし | 不具合時は停止・電源遮断 | 3つの数値の根拠と現行imageの余裕を再確認。メモリ破壊防止は維持し、根拠のない余裕値を絶対視しない | compile/disassembly evidenceあり。on-board watermark未実施 |
| current limit / 電源 / 配線 / 発熱 | KEEP（最優先） | 過電流・短絡・逆接・逆起電力・過熱によるArduino/driver/配線損傷、発煙 | 現物電源・電流制限・保護素子・回路revisionが未確認。リスク頻度を推定できない | 手の届く主電源遮断 | 電源・電流制限・配線・保護素子・温度の現物確認を優先。根拠が揃うまでcurrent-limit confirmedをfalse維持 | BLOCKED / NOT RUN |

## T18コード変更の扱い

- 旧8,000ms ceiling、within_8s_budget、stage_budget_msによる合否判定を廃止する。
- 31段階、3,100 ADC batches、37,200 ADC slots、loss-window、RawLog validation、Evidence bundle、normal-completion STOP_REQ等の整合性チェックは残す。
- stage elapsed p50/p95/p99/p99.9/max、各fsync target、finalization phaseを診断値として出力する。
- profile statusはデータ/イベント整合性の検証結果で決定し、時間値だけではFAILにしない。
- 実行結果をPASSにするために測定値を加工しない。遅延はそのまま記録する。

## HW01–HW08の再分類

| ID | 現行計画 | 再分類 | 再評価後の扱い |
|---|---|---|---|
| HW01 | MCU marking / board revision / schematic identification | KEEP | 損傷防止・実機仕様特定の基礎。必要情報だけ取得 |
| HW02 | Fuse/BOD read-only | INVESTIGATE | MCU identity確定後、BOD設定が損傷防止/誤動作防止に必要か確認。Fuse writeは禁止 |
| HW03 | External supervisor/hold-up proof | INVESTIGATE | 実電源条件で必要性が示された場合のみ。回路がないだけで直ちにFAILとしない |
| HW04 | Brownout時出力OFF / no auto-resume | KEEP | reset後に自動駆動しない基本動作。実機波形確認は条件確定後 |
| HW05 | EEPROM全write境界断電 | RELAX | boot identity/再始動制御に必要な境界へ限定 |
| HW06 | A0-A5 analog reference/accuracy | RELAX | A0/A4/A5の必要測定を優先。A1は独立観測、A2/A3は参考値。用途外の精度保証を要求しない |
| HW07 | STOP under congestion / independent cutoff / latency | SPLIT: KEEP + INVESTIGATE | ソフトウェアSTOP優先処理は維持。独立物理STOP/cutoffは主電源遮断を含めて比較し、具体的危険がある場合のみ必須化 |
| HW08 | 310秒PWM0-30実機run | SEPARATE AUTHORIZATION | current limit・電源/配線の確認後に別途明示承認。今回の再評価だけでは実施しない |

## 現在の進捗判定

| 領域 | 状態 | 次の作業 |
|---|---|---|
| リスク基準共有 | COMPLETE | Issue #35へ2026-11-09基準を追記済み |
| T18 8秒合否ゲート | IMPLEMENTATION IN PROGRESS | code / tests / report schema / PR descriptionを同期 |
| T18 hosted path | PASS | 新コードでCI再実行 |
| T18 target-host exact HEAD | NOT RUN | 新HEADを対象PC/storageで診断実行。時間値は合否ゲートにしない |
| R01 marker checks | INTEGRATED | markerの存在時に自動再始動を阻止する部分は維持 |
| R01 lifecycle/operator workflow | NOT COMPLETE | 過剰なjournal要件を整理し、UNKNOWN・運用者確認・電源遮断の最小手順へ再設計 |
| HW01–HW08 | NOT RUN / NOT AUTHORIZED | 現物情報を揃え、KEEP/INVESTIGATE対象だけをまとめて審査 |
| 310-5 acceptance / 310-6 | NOT ACCEPTED / BLOCKED | 再分類後の証拠を審査して決定 |

## 明示的な制限

本書はリスク対応の設計見直しであり、Arduino接続、/dev/ttyACM0や/dev/ttyUSB0へのアクセス、firmware upload、Fuse/EEPROM操作、モーター通電、310秒測定を許可しない。HARDWARE_CURRENT_LIMIT_CONFIRMED=falseを維持する。
