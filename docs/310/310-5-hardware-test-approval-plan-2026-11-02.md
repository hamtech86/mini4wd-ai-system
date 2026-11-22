# 310-5 ハードウェア試験計画・承認前チェック — 2026-11-02

**目的:** 310-5で未確認のハードウェア項目について、試験方法・安全条件・承認に必要な情報を整理する。  
**権限状態:** 本書は試験計画のみ。実機試験の実施承認ではない。  
**安全ゲート:** `HARDWARE_CURRENT_LIMIT_CONFIRMED=false` を維持。通電、モーター駆動、電源電圧変更、Fuse操作、EEPROM電源遮断は行わない。

## 1. 現時点で共通して不足する実機情報

| 必須情報 | 現状 | 承認前に必要な証拠 |
|---|---|---|
| 実搭載MCU | ATmega328Pは設計基準のみ | IC marking、signature、board revision |
| 基板/回路 | exact schematic未取得 | 回路図、基板revision、driver/enable pin map |
| 電源構成 | nominal条件のみ | 電源型番、出力範囲、電流制限値、配線図 |
| hardware current limit | false | current limit設定値、測定証拠、保護素子定格 |
| external supervisor | 実装確認なし | 部品型番、threshold、reset接続、hold-up容量/波形 |
| STOP物理経路 | 独立cutoff未証明 | driver enable/power cutoff回路、fail-safe state |
| ADC前段 | exact sensor/filter未確認 | ACS712 suffix/module、filter、VREF、analog schematic |
| 復旧方法 | 試験別に未確定 | 電源再投入、MCU再初期化、ヒューズ/保護復帰手順 |

これらが不明なままでは、試験電圧・予想電流・停止方法を安全に確定できない。値を推定して申請しない。

## 2. 試験計画

| ID | 試験 | 計画方法 | 予想電流/電圧 | 停止方法 | 現状 |
|---|---|---|---|---|---|
| HW01 | MCU/基板同定 | 無通電でmarking/board revisionを撮影・記録。必要なら承認後read-only signature | 無通電同定は0。signature読取時の供給条件は未確定 | 無通電作業終了。通電readは個別承認 | BLOCKED |
| HW02 | Fuse/BOD readback | exact MCUを同定後、承認済みISP手順でread-only dump。Fuse writeは禁止 | ISP電源条件・電流未確定 | programmer disconnect。誤write防止 | BLOCKED |
| HW03 | supervisor/hold-up | 回路図と部品仕様照合後、モーター/driverを切離した試験治具でthreshold・reset・hold-up波形を測定 | 実回路仕様なし。値未確定 | bench supply output disable、治具側切離し | BLOCKED |
| HW04 | 電圧低下時PWM/ARM | HW03合格後、driverを切離し、supervisor入力だけを制御してreset/ARM inhibitを観測 | threshold・電源範囲未確定 | 電源を通常範囲へ戻し、再ARM禁止を確認 | BLOCKED |
| HW05 | EEPROM write interruption | モーター/driverを切離し、journal write境界ごとに電源遮断。再起動後journal/BOOT_ID状態を検証 | board/MCU電源条件・電流未確定 | bench supply output disable。partial identityは無効扱い | BLOCKED |
| HW06 | ADC reference/入力 | motor driverを物理切離し、traceable sourceでA0〜A5へ個別入力。raw/status/timestampを照合 | ADC input range/series resistance未確定 | source output zero/off、入力切離し | BLOCKED |
| HW07 | STOP/通信断/TX full | モーターを切離し、PWM/IN/enableをlogic analyzer/scopeで観測。通信断、TX full、ADC batch中STOPを注入 | logic-only試験時の電流・電圧は回路確認後確定 | bench supply disable、driver切離し、reset | BLOCKED |
| HW08 | 310秒 PWM 0〜30実機測定 | HW01〜HW07の安全ゲート・current limit・独立cutoff・firmware acceptance後に別途申請 | motor/load/current limit未確定 | 独立hardware cutoff + operator power disconnect | NOT AUTHORIZED |

## 3. 個別承認申請に添付する必須項目

各試験について、以下をすべて確定してから個別承認を申請する。

1. 試験ID、目的、合否基準、対象FW commit/build ID
2. MCU marking/signature、基板revision、回路図revision
3. 配線図（電源、GND、driver、motor disconnect、ADC/ISP、scope probe）
4. 電源型番、設定電圧、電流制限値、予想最大電流、ヒューズ/保護素子
5. 実施前の状態確認と接続順
6. STOP手段、独立cutoff、電源遮断位置、異常時の即時操作
7. 予想される機器影響、故障モード、復旧手順
8. 記録器材、測定点、ログ形式、証拠保存先
9. 実施者、立会者、実施時間帯
10. 実施後の無通電確認、残留電圧確認、状態復元チェック

## 4. 試験の順序依存

- HW01の無通電同定を最初に行う。
- HW02/HW03は実搭載MCUと回路図が確定してから実施する。
- HW04/HW05はsupervisor/hold-up条件が検証できるまで実施しない。
- HW06はADC前段とreference source接続条件を確定してから実施する。
- HW07は独立STOP/driver cutoffの回路と観測点が確定してから実施する。
- HW08はHW01〜HW07の必要条件を満たし、個別の明示承認を受けた場合のみ候補となる。

## 5. 現在の承認状態

全HW試験は未承認・未実施。HW01の無通電外観確認も、この担当は実行していない。電源、モーター、USB/serial、Fuse/ISPを操作していない。

本書は上位司令塔が試験承認の可否を判断するための計画であり、試験実施許可・310-5受入・310-6移行の根拠ではない。
