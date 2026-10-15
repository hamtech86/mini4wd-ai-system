# Firmware / Python UI 接続契約（暫定固定候補・司令塔承認待ち）

- 対象リポジトリ: `hamtech86/mini4wd-ai-system`
- 起点: Issue #75 司令塔判断 `issuecomment-6189183596`
- 対象統合候補: PR #74 head `72f72c76c2eb4431da0fea0a4fd53920e1cd3ec2` と PR #78 head `19a9f01637379ae50260d9ca82d813bb7c3d36ea` を含む
- この文書の状態: **レビュー用提案。Issue #35の正本ではない。司令塔の明示承認前に仕様固定済みと扱わない。**
- DATA: 26項目固定。RawLogの受信本文を補正・再構成しない。
- 実機試験: 未実施。

## 1. 責任分界

- Arduino Uno: ADC/センサー読取、状態報告、方向/PWMなど明示指令の実行、ハードウェア安全保護。
- Python/UI: 接続INFOの検証、通常電圧フィードバック、方向別の測定値解釈、Benchmark/Break-in/Sequenceの進行判断、異常測定の判定と停止要求。
- Arduino内の独立した電圧フィードバックループは使用しない。旧 `VCTRL=ON` と `TARGET=n` はPWM制御を開始せず、`ERROR,VOLTAGE_CONTROL_OWNED_BY_HOST` を返す。`VCTRL=OFF` は冪等な安全コマンドで、PWMを変更しない。
- コマンド送信成功と実機停止確認は異なる状態。現在のホスト実装は通常コマンドの応答を完全には相関確認しないため、停止確認UIは別途実装・検証が必要。

## 2. INFO 識別契約

### 要求・応答

要求は `INFO\n`。接続直後の起動出力に依存せず、クライアントは明示要求を行う。現行ファームウェアの応答例:

```text
INFO,TYPE=MOTOR,MODEL=MOTOR_BREAKIN_V3,FW=3.00,BUILD=ACS-CAL-LOG-20261013-01,ID=000001
```

| フィールド | 意味 | クライアント要件 |
|---|---|---|
| TYPE | デバイス種別 | 必須、`MOTOR` のみ許可 |
| MODEL | ファームウェア機種 | 必須、`MOTOR_BREAKIN_V3` のみ許可 |
| FW | ファームウェア表示バージョン | 必須、空欄不可 |
| BUILD | ファームウェアビルド識別子 | 必須、空欄不可 |
| ID | ファームウェア内部識別文字列 | 必須、空欄不可。ただし個体固有IDとはみなさない |

クライアントのINFOタイムアウトは1.0秒。無応答、壊れた形式、必須項目欠落、未許可TYPE/MODEL、同一キーの重複、値が矛盾する重複は識別失敗とし、駆動コマンドを許可しない。未知の追加キーは前方互換のため許容する提案。旧FWでBUILD等が欠落する場合は暗黙に許可せず、明示的な互換性表が別途承認されるまで拒否する。

起動時に出力されるINFOは接続時バッファ処理で失われ得るため、接続時の再問い合わせを正とする。INFO行は新規RawLog本文に含めない。

## 3. DATA 26項目

順番は固定。すべての数値項目は空欄・非数値・NaN/Infを制御値として受け入れない。無効フレームは測定として採用しないが、RawLog収集側では受信した原文をそのまま保持する。

| # | 項目 | 型・単位 | 意味 |
|---:|---|---|---|
| 1 | record_type | 文字列 | `DATA` |
| 2 | device_model | 文字列 | 機種名 |
| 3 | instance_id | 文字列 | ファームウェア側の識別値。DBのMotor Instance IDとは別 |
| 4 | elapsed_time | 整数・ms | 実行開始からの経過時間 |
| 5 | raw_acs1 | 整数・ADC count | ACS712 #1の生ADC値 |
| 6 | raw_acs2 | 整数・ADC count | ACS712 #2の生ADC値 |
| 7 | current1 | 数値・A | 電流センサー1換算値 |
| 8 | current2 | 数値・A | 電流センサー2換算値 |
| 9 | voltage1 | 数値・V | A4 / VM1側の測定電圧 |
| 10 | voltage2 | 数値・V | A5 / VM2側の測定電圧 |
| 11 | motor_voltage | 数値・V、符号付き | 生の差分 `V4 - V5`。絶対値化・方向補正してRawLogへ書き戻さない |
| 12 | pwm | 整数・0–255 | 現在のPWM指令値 |
| 13 | direction | 文字列 | `FWD` または `REV` |
| 14 | state | 文字列 | `INIT`, `READY`, `RUN`, `PAUSE`, `STOP`, `COMPLETE`, `ERROR` 等 |
| 15 | current_avg | 数値・A | ファームウェアの平均電流値。欠落時に0Aへ補完しない |
| 16 | power | 数値・W | ファームウェア算出電力 |
| 17 | current_ripple | 数値・A | 電流リップル |
| 18 | voltage_ripple | 数値・V | 電圧リップル |
| 19 | peak_power | 数値・W | ピーク電力 |
| 20 | peak_current | 数値・A | ピーク電流 |
| 21 | peak_voltage | 数値・V | ピーク電圧 |
| 22 | peak_pwm | 整数・0–255 | ピーク時PWM |
| 23 | brush_peak_current | 数値・A | ブラシピーク電流 |
| 24 | raw_magnetic | 整数・ADC count | 磁気センサー生値 |
| 25 | magnetic_level | 数値・V相当 | ADCから換算した磁気センサー値 |
| 26 | motor_temperature | 数値・°C | サーミスタ換算温度 |

### 方向別制御電圧

- TERMINAL: FWDは制御値 `V4 - V5 = motor_voltage`。REVは制御値 `V5 - V4 = -motor_voltage`。
- INPUT: FWDは `voltage1` (A4)、REVは `voltage2` (A5)。
- 方向変換はPythonの制御値だけに適用し、生の26列を変換しない。
- 駆動中の電圧フィードバック制御で期待電圧が0以下、欠落、非有限値、方向と矛盾する場合は無効フィードバックとする。待機/停止中の0Vとは区別する。

## 4. コマンド契約（現行実装と提案の区別）

| コマンド | 目的 | 暫定扱い |
|---|---|---|
| INFO | 識別情報 | INFO応答を返す |
| STATUS | 状態照会 | STATUS行を返す |
| PING | 通信確認 | PONGを返す |
| START | 現在方向で開始 | 識別済みクライアントのみ |
| RESUME | 再開 | 識別済みクライアントのみ |
| FWD / REV | 方向指定・開始 | 識別済みクライアントのみ。開始前にCALスナップショットを出力 |
| PWM=n | 明示PWM指令 | 0–255。未識別時は0以外を拒否 |
| PAUSE | 一時停止 | PWM出力を0にし、ファームウェア側の電圧制御を無効化 |
| STOP | 停止 | PWMを0、方向出力をLOW、状態STOP、最終DATAとOKを出力 |
| VCTRL=OFF | 旧互換の安全無効化 | OK。PWM変更なし |
| VCTRL=ON | 旧制御の有効化 | ERROR。PWM変更なし |
| TARGET=n | 旧制御の目標電圧 | ERROR。PWM変更なし |

未識別時はSTART/RESUME/FWD/REV/PWM>0を拒否する。PWM=0、STOP、PAUSE、INFO、STATUS、PINGは安全経路として許可する。Python側の停止経路はPWM=0送信に失敗してもSTOPと切断を試行する。

## 5. 無効測定と安全停止

- DATAの必須数値項目が欠落、空欄、非数値、NaN/Inf、範囲外の場合、そのフレームを制御に使用しない。無効値を0V/0Aに置き換えない。
- 電流安全判定に使う `current_avg` が欠落/不正な場合、0Aに補完せず無効とする。
- Benchmark、通常Break-in、TuneBasic、Sequence/Adapterの駆動中経路で、無効フィードバックが連続3回発生した場合に停止する。有効測定が1回入ればカウンタをリセットする。
- ブラシピーク基準値の初回有効測定待ちにも同じ上限を適用し、無期限待機を避ける。
- 停止時はPWM=0、STOP、必要な切断を順に試行する。停止理由と停止確認状態は別の情報としてUIへ伝える。送信成功のみで物理停止確認済みとはしない。
- ソフトウェアテストは状態遷移・コマンド送信を検証できるが、物理的なPWM停止・電流遮断・センサー精度は実機試験まで未確認。

## 6. ACS712校正メタデータ

起動時校正は各ACS712を200回サンプリングし、`CAL,ACS1_ZERO=...,ACS2_ZERO=...` を出力する。READYかつPWM=0の間はゼロオフセットが自動追従する。駆動開始直前にもCALスナップショットを出し、その値を駆動中の電流換算に使用するオフセットとしてRawLogの補助行に残す。DATAの列数は増やさない。

校正値が駆動中に更新されないことはソース上の条件から確認できる。実際のセンサーオフセット精度や、起動前のドリフトへの適合性は実機未確認。

## 7. TuneBasic

`TUNE_BASIC` はレシピ定義の `voltage_control_mode: INPUT` を明示する。FWDではA4/voltage1、REVではA5/voltage2を参照する。レシピレベルのモードは各Phaseのmetadataへ伝播し、Sequence経路でも同じモードを使用する。通常のSTD-T/Full-T/STD-I/Full-Iのモード選択には影響させない。

## 8. 回帰テスト・CI

必須の自動検証:
- Arduino Uno向けコンパイル
- INFO必須項目・未知機種・重複キー・タイムアウト
- DATA 26列順・完全性・有限値・符号付きmotor_voltage
- TERMINAL FWD/REV方向変換とINPUT A4/A5参照
- 4 BenchmarkレシピとTuneBasic INPUT指定
- 連続3回無効測定による停止、単発無効値のスキップ、有効値によるカウンタリセット
- VCTRL=ON/TARGET拒否、STOP/PAUSE後に隠れたループがPWMを再設定しないこと
- RawLog本文不変性とCAL補助行の記録

現段階でCIは未確定。実機確認は未実施。

## 9. 未解決・司令塔判断待ち

1. Issue #35への正本追記内容・承認時点。
2. 停止確認をどの応答/STATUS/測定条件でUIへ提示するか。現行SerialControllerの通常コマンド応答照合は不十分であり、送信と物理停止確認を同一視できない。
3. INFO未知フィールド許容の最終採否（本案は許容）。
4. CAL行をRawLog補助行として保存する形式・タイミングの最終採否。
5. ソフトウェアCI成功後に実施する実機手順と安全条件。

## 10. 統合候補と順序

- PR #74: 起点 `872ae01545d9a4aff5d076914a68a6793beea653` からのファームウェア/Benchmark統合候補。未マージ。
- PR #78: PR #74の統合候補をbaseとするINFO識別ガード。Draft・未マージ。
- PR #79: PR #78 headを起点に本候補修正を積み上げたDraft・未マージ。
- 推奨順序: 司令塔レビュー → PR #79の差分/CI修正 → 司令塔が承認した統合計画に従ってPR #74/#78/#79を統合。担当はマージもDraft解除も行わない。
