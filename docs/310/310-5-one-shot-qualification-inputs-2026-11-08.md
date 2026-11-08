# 310-5 最終受入に必要な一括ハードウェア資格確認 — 2026-11-08

## 目的と状態

この文書は、310-5を一回のまとまった資格確認で完了させるための入力・試験順序・合格証拠を固定するもの。

- 現時点: **承認前 / 未実施**
- `HARDWARE_CURRENT_LIMIT_CONFIRMED=false` を維持
- Arduino upload、実機シリアル接続、モーター通電、EEPROM書込み/電源断、Fuse/ISP操作、310秒実測は未承認・未実施
- 本文書は実施許可ではない
- 310-5の正式受入前に310-6 UI統合を開始しない

## 1. 既知のハードウェア情報

- MCU設計基準: ATmega328P / Arduino Uno。実搭載チップのmarking/signatureは未確認。
- Motor driver: L298N。実基板のenable/cutoff配線と独立停止回路は未確認。
- Current sensors: ACS712 ×2。suffix/module/filter/reference条件は未確認。
- Firmware target: `arduino:avr:uno`, Arduino AVR core 1.8.8。
- Firmware mapping: D5 PWM、D7/D8 direction、A0/A1 ACS712、A2 magnetic raw、A3 thermistor raw、A4/A5 independent voltage channels。
- Hardware current limit: **未確認**。
- External voltage supervisor: 実装・部品型番・threshold・reset/hold-up配線の証拠なし。
- 電源型番・電流制限値・保護素子定格・実基板revision・回路図revision: 未取得。

上記で不明な値は推定しない。試験電圧・予想最大電流・停止閾値・復旧手順を仮定して実施しない。

## 2. 一括提出に必要な現物情報

実機作業に進む前に、以下を一つの提出物として確定する。

1. MCUの刻印写真、read-only signature取得結果、基板revision。
2. 回路図revisionと、D5/D7/D8、L298N EN/IN、電源/GND、独立STOP/cutoffの配線図。
3. 電源型番、出力範囲、設定電圧、電流制限値、ヒューズ/保護素子の型番・定格。
4. 外部supervisorの部品型番、threshold、reset接続、hold-up容量と測定波形。
5. EEPROM型番/容量、journal領域、provisioning領域の実機構成。
6. ACS712のsuffix/module、filter回路、VREF、A0〜A5の入力範囲とsource impedance。
7. 異常時の独立cutoff操作位置、電源遮断位置、残留電圧確認、復旧手順。

一項目でも不明なら、その項目に依存する試験はBLOCKEDのままにする。

## 3. HW01–HW08 試験順序と合格証拠

| ID | 実施内容 | 必須合格証拠 | 依存条件 / 状態 |
|---|---|---|---|
| HW01 | 無通電でMCU marking・基板revision・回路図を同定。通電read-only signatureは別途条件確定後 | 写真、型番、revision、signature、clock根拠 | 最初に実施。現状BLOCKED |
| HW02 | Fuse/BODをread-onlyで取得し、対象MCU datasheetと照合。Fuse writeは禁止 | 生dump、MCU identity、BOD設定、16MHz時の保証根拠 | HW01後。内部4.3V BODだけではPASSにしない |
| HW03 | 外部supervisor/hold-up回路の実装とthreshold/reset/hold-upを、motor/driver切離し治具で確認 | 部品型番、回路図、測定波形、reset出力、hold-up時間 | HW01・電源/回路情報確定後。実装なし/証拠なしはFAIL/BLOCKED |
| HW04 | driver切離し状態で電圧低下を模擬し、PWM=0、D7/D8 LOW、ARM無効、no auto-resumeを確認 | 入力電圧とreset/enable/PWM波形、状態ログ | HW03合格後 |
| HW05 | motor/driver切離し状態でEEPROM journal各write境界の電源断・再起動を検証 | 各境界のEEPROM dump、BOOT_ID/journal判定、invalid/unknown時fail-closed証拠 | HW01–04の電源条件確定後。Fuse操作なし |
| HW06 | traceable sourceでA0〜A5を個別入力しraw/status/timestamp/校正/settlingを照合 | 入力値、ADC raw、timestamp、channel独立性、誤差・不確かさ | ADC前段・VREF・入力範囲確定後。A0/A1は独立、A2/A3はraw reference only、A4/A5も独立 |
| HW07 | motor切離し状態でSTOP、通信断、TX full、ADC batch中STOPを注入し、GPIO/driver enableを観測 | PWM=0、D7/D8 LOW、ARM invalid、no auto-resume、独立STOP経路、STOP latency、L298N cutoff波形 | 独立STOP/cutoff回路と観測点が確定した後 |
| HW08 | PWM 0–30、各10,000ms、31段階=310,000msの統合実機測定 | 31段階のPython command/ACK、全ADC/RawLog/Evidence、電流制限・温度・停止監視、異常時独立cutoff記録 | HW01–07と全software gate合格後。**別途明示承認が必要** |

HW08は出力最大値探索ではない。Pythonが31段階を管理し、Arduinoは指令されたPWMを適用するだけ。現行310 sequenceは正転のみ。実測開始は独立current limitと独立cutoffが実証されるまで禁止。

## 4. 310-5 software/host側の未閉鎖ゲート

### 4.1 現在の合格済みソフトウェア証拠

Code/test source HEAD: `c2ba0a431a96d586c4449b4b98f8c31acd55bfb3`

- Full suite: **615 passed, 2 xfailed**。全4 host jobs success。
- Native protocol-v2 workflow: success。
- Arduino Uno compile/resource audit: success。
- RX workspace 194B / TX workspace 194B。
- UART RX/TX rings 24B each。
- Production static SRAM: 893B。
- ADC audit static SRAM: 894B。
- Conservative stack bound: 294B。
- Remaining SRAM: 860B、448B reserveより412B上。
- PR #191 persistence diagnostics merged into the integration branch。durability operationのskip/defer/combine/reorderなし。

これらはsoftware/compile evidenceであり、実機安全性証明ではない。

### 4.2 残るhost/storage作業

- R01: interrupted workのcommand-outcome reconciliation。既存 `.310-rearm-inhibited` markerを削除/回避しない。元RawLog、command-intent、transport Evidence、STOP outcomeを照合し、unknownをunknownのまま残す。
- T18: approved target host/storageでproduction-path 31-stage profileを実施。GitHub-hosted runnerの成功で置き換えない。RawLog/Evidence/intent append、fsync、finalize、recovery、backup/restoreを同じtarget host上で計測。
- T18再実行はR01の原因確認・reconciliation前に行わない。

## 5. 最終受入条件

310-5の正式受入は、次をすべて満たした後に一度だけ提出する。

1. T01–T18の全必須項目について、対象HEAD・実行条件・証拠をひも付け、PASS/FAIL/BLOCKED/NOT RUNを明示する。
2. HW01–HW07が合格し、current limit、external supervisor、独立STOP/cutoff、EEPROM/BOD/ADC条件を実証する。
3. T18 target-host production pathとR01 reconciliationが完了する。
4. HW08の310秒測定は、独立current limitとcutoffの確認後、別途明示承認を得て実施し、証拠を保存する。
5. 上位司令塔が最終審査し、正式受入を宣言する。

**現時点の判定: 310-5 NOT ACCEPTED。310-6 UI統合は未着手。**
