# 310-4 残存事項決定表 — 2026-11-02

対象: PR #183 / docs/310/310-4-design-v0.5.md  
基準: Issue #35、Issue #170、Issue #174、310-1 PR #180、310-2 PR #181、310-3 PR #182、司令塔完遂指示。

| 項目 | 分類 | 決定・現状 | 未解決理由 / 必要入力 | 担当 | 解消条件 |
|---|---|---|---|---|---|
| EEPROM耐久イベント数 | 承認済み | 36,600 boot events | 方式承認ではない | 310-4設計 | 実装で要求を満たすことを試験 |
| EEPROM 16-slot摩耗計算 | 技術根拠により確定 | 約2,288回/slot、markerは約4,576 write操作/slot | 実EEPROMの耐久条件は別 | 設計担当 | MCU datasheet条件・書込み回数実証 |
| EEPROM BOD/fuse/電源断 | 設計入力不足で保留 | BOD値未確定 | 正確なMCU型番、fuse bytes、基板版、電源範囲、datasheet write条件が未提示 | Hardware設計担当 | 実装対象の識別情報と電源設計根拠を提出 |
| EEPROM commit順序 | 技術根拠により確定 | invalidate→payload/CRC→readback→commit marker last→verify | 書込み実証は未実施 | Firmware担当（実装許可後） | 全境界電源断試験合格 |
| Evidence保存期間 | 承認済み | 10年以上 | 保存媒体の選定は未承認 | データ運用責任者 | 容量・媒体・移行・復元計画を提示 |
| 独立バックアップ | 承認済み | 最低1系統、独立して検証 | 具体的保存先未確定 | データ運用責任者 | hash照合＋restore/readability試験 |
| 検出不能な損失 | 承認済み | 許容しない | 未知byte範囲は明示的unresolved/incomplete | Python担当（実装許可後） | 全byte/sequenceのaccountability試験 |
| チャンネル別・期間別損失 | 承認済み | Evidenceでchannel×time-window記録 | window幅・粒度は未定 | 計測設計担当 | window定義と試験ベクトル承認 |
| 20Hz | 310-4の対象外（採用判断） | 未採用。候補値を設計要求にしない | ACS712型番、帯域、PWM周波数、filter、settling、統計量、誤判定率が未提示 | 計測設計担当 | 参照実験を別途承認し、事前基準を満たす |
| ADC scan順 | 技術根拠により確定 | 候補順A0,A1,A4,A5,A2,A3。各変換独立 | 実機取得時間は未測定 | Firmware担当（実装許可後） | timestamp/順序/周期試験 |
| ADC conversion failure検出 | 設計入力不足で保留 | analogRead値だけでは断線・浮遊入力を確定検出できない | bounded ADC routine、診断回路の有無 | Hardware/Firmware担当 | 検出対象・回路・failure semanticsを定義 |
| UART frame arithmetic | 技術根拠により確定 | 194B batch、約33.7ms、平均負荷約34.3% | burst/worst-case latencyは未測定 | Protocol担当 | worst-case scheduler/queue試験 |
| TX時STOP | 承認済み | TX backpressureでSTOP処理を阻害しない | 実装証明なし | Firmware担当（実装許可後） | TX詰まり時STOP試験 |
| Buffer ownership/occupancy/overflow | 承認済み | 明示的状態・occupancy/high-water/loss区分 | 具体的配置は未確定 | Firmware担当（実装許可後） | ownership invariant/overflow試験 |
| SRAM予算 | 実装後検証待ち | 650B static案 + 384B stack + 256B margin | compiler map/sizeof/core ring/stackがない | Firmware担当 | 実ビルドmapとstack余裕を提出 |
| fsync failure semantics | 技術根拠により確定 | intent未fsyncなら送信禁止、証跡失敗後nonzero PWM禁止、可能ならSTOP、incomplete | target storage性能未測定 | Python担当（実装許可後） | fault injection合格 |
| fsync latency budget | 設計入力不足で保留 | 数値未確定 | 対象OS/filesystem/storage/load測定が必要 | Python設計担当 | p50/p95/p99/max測定＋期限合格基準を承認 |
| RawLog v2 schema | 承認済み契約を維持 | 変更なし。ADC_SAMPLE=1 conversion | なし | 全担当 | schema validatorで無変更を確認 |
| 310-1 timestamp/epoch/context | 承認済み契約を維持 | midpoint、full epoch、取得時context固定 | 実装後試験は未実施 | Firmware/Python担当 | 対応する受入試験合格 |
| 310-2 recovery | 承認済み契約を維持 | append-only、original preservation、manifest-last | Evidence companion integrationは未実装 | Python担当 | crash/recovery/hash試験合格 |
| 310-3 timing/ownership | 承認済み契約を維持 | Python owns stages、ACK-gated、host monotonic | 310-4 concrete codec integration未実装 | Python担当 | mock integration tests + separate implementation approval |
| 310-5 | 310-4の対象外 | 明示的に未許可 | 310-4受入・別承認が必要 | 司令塔 | 別途正式指示 |

## 過去指摘の閉鎖状況

| 指摘群 | 最終状態 |
|---|---|
| ADC_BATCH length / framing arithmetic | 設計記載あり。実装試験待ち |
| stage_context_id / token mapping | 設計契約あり。実装試験待ち |
| State transition / stale frame / STOP→reARM | 設計記載あり。実装試験待ち |
| STOP_ACK size / command_id vs stop_request_id | 3-byte ACK維持、識別子分離。実装試験待ち |
| Boot identity / EEPROM commit | journal契約あり。MCU/BOD/電源入力待ち |
| Loss / overflow / sequence | host expansion・channel/window requirement追加。実装試験待ち |
| 20Hz | 明示的未採用 |
| SRAM / TX backpressure / STOP | 予算は計画値、compiler・stack・実機外のmock証跡待ち |
| Session tag restart collision | A9.1契約あり。crash/restore test待ち |
| Sequence rollover/ambiguity | A9.2契約あり。boundary test待ち |
| Evidence durability / fsync / recovery | A9.3およびF2.7。fault injection待ち |

**総合:** 設計文書上の契約は統合したが、設計受入の最終判断に必要な一部の技術入力と、実装後検証の証拠は未取得。これらを設計記述の欠落と混同しない。


## 2026-11-02 最終修正審査指摘への決定追記

| 指摘 | 決定・分類 | 根拠／解決内容 | 残る境界 |
|---|---|---|---|
| EEPROM耐久表現 | 技術根拠により確定 | 100,000 write/erase cyclesはEEPROMセル単位。36,600 boot events時、16-slot輪番でmarker各セル最大4,575 write、payload各セル最大2,288 write。全markerセル合計73,200 write操作はaggregateでありセル耐久値ではない。 | データシートの実条件適用、BOD/電源断、実装後の耐久証跡は別途 |
| ADC候補周期 | 技術根拠により確定 | T/T+25/T+100msは同一channelの25ms/75ms交互間隔。平均20 conversion/s/channelだがuniform 20Hzではない。 | 20Hz採用判断は行わない。非等間隔aliasingとreference captureが必要 |
| RawLog sequence | 技術根拠により確定（既存schemaの意味範囲） | Issue #170/PR #180のADC_SAMPLE.device_sample_sequenceはintegerかつepoch内monotonic、固定uint16幅の規定なし。host uint64 extensionを既存integerに格納し、wire uint16はcompanion Evidenceに保持。schema/type/version変更なし。 | validator/package fixtureで既存integer許容とmanifest companion inventoryを実装後確認 |
| batch/loss/context/Evidence | 設計入力不足で保留（package実装） | batch_sequence、loss_counter、stage_context_token、wire uint16はRawLog fieldへ追加せず、transport-evidence-v1 sibling artifactに保持。Issue #35 §3.4に沿いpackage inventory/manifestでhash参照。 | 現行manifest validatorの許容形式・artifact inventory extensionは実装前にschema fixtureで確定 |
| CI | 技術根拠により確定 | 対象HEAD a21d22bの2 workflow runs、5 jobs成功をGitHub Actionsから確認。 | CIは文書・既存ソフトウェア回帰の結果で、実機安全性を証明しない |
