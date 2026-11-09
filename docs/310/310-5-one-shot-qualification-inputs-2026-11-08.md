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

Code/test source HEAD: `3b065388501d4be91f39b5c6d197cecf52c53f17`

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
3. T18 target-host profileは診断結果として実施・記録する。未実施または時間超過のみで自動FAILとせず、データ整合性・制御境界への具体的影響を審査する。R01はUNKNOWNの誤認と自動再始動を防ぐ最小要件を満たす。
4. HW08の310秒測定は、独立current limitとcutoffの確認後、別途明示承認を得て実施し、証拠を保存する。
5. 上位司令塔が最終審査し、正式受入を宣言する。

**現時点の判定: 310-5 NOT ACCEPTED。310-6 UI統合は未着手。**

## 6. T01–T18 current evidence map

The controlling test definitions are `docs/310/310-4-implementation-acceptance-tests-2026-11-02.md` at accepted 310-4 design HEAD `73a123d58005f1a04f4a207811e740153ac779e0`. Current evidence is separated below from physical completion.

| Test | Current software evidence | Still prevents full PASS |
|---|---|---|
| T01 Session identity | The old 32-bit tag allocator was superseded by the adopted full UUID session identity in protocol v2; zero/invalid session and handshake paths are covered by host/device tests. | Final traceability must record the superseding design decision; no legacy tag allocator PASS is claimed. |
| T02 Device sequence / gap | Device-owned uint64 monotonic allocation, batch-boundary exhaustion and fail-closed behavior are covered by native tests; host RawLog sequence/recovery tests run in CI. | Full duplicate/conflict/gap matrix and actual reboot/epoch continuity still require final evidence reconciliation. |
| T03 Boot epoch / checkpoint | Full boot identity journal emulator, corrupt/duplicate/exhaustion/write-failure tests, HELLO/epoch handling and host re-arm gate tests are present. | Physical EEPROM power-loss and real boot identity behavior remain untested. |
| T04 Partial TX / ACK | Host tests cover short/failed write, flush exception/timeout, ACK mismatch/timeout, fragmented/coalesced frames and post-flush timestamp origin; device ACKs echo session/epoch/command/context. | Physical UART delivery and complete target fault-injection matrix remain unqualified. |
| T05 fsync / crash / latency | Host fault injection, RawLog recovery, durable intent/Evidence tests and persistence diagnostics are present; full suite passes. | Approved target-host production-path latency/fault/recovery profile remains NOT RUN. |
| T06 EEPROM interruption | Native journal emulator covers invalid/corrupt/duplicate generation, exhaustion and write-failure boundaries. | Actual EEPROM power interruption and brownout are NOT RUN. |
| T07 ADC cadence | Native scheduler tests cover channel order, 25/75 ms pattern, overrun-to-NOT_ACQUIRED and micros wrap. | Reference acquisition, channel settling, PWM-phase error and physical timing qualification are NOT RUN. |
| T08 SRAM / stack | Exact Uno build and ADC audit images meet static memory limits; 894 B static, 294 B conservative nested stack, 860 B remaining. | On-board stack watermark and worst-case physical runtime occupancy are NOT RUN. |
| T09 STOP under TX blockage | Native TX scheduler test verifies STOP_ACK preempts ADC batch ownership; host independent STOP writer tests distinct bounded endpoint and failure latch. | Independent physical STOP wiring, MCU freeze behavior, driver cutoff and measured physical latency are NOT RUN. |
| T10 RawLog / Evidence closure | Companion manifest binds RawLog and Evidence hashes/counts; tamper, mismatch and extra-file tests are present; original two-file RawLog schema remains unchanged. | Actual target-host backup/restore and power-loss recovery are NOT RUN. |
| T11 Channel/window loss | Firmware assigns device-owned sequence per attempted slot; host persists ADC_BATCH slots as ADC_SAMPLE and tracks per-channel/window loss summaries; hosted production profile checks 310 summaries. | Actual hardware acquisition/loss behavior and target-host end-to-end loss reconciliation remain unqualified. |
| T12 310-3 compatibility | Exact code/test HEAD full suite: 615 passed, 2 xfailed; Break-in/Battery/RawLog-sequence jobs all success. | CI is software regression evidence only; no physical behavior claim. |
| T13 EEPROM endurance / BOD | Journal layout and compile-only provisioner exist; native emulator covers state/failure logic. | Datasheet-backed 36,600-event wear proof, fuse/BOD readback, external supervisor and hold-up waveforms are BLOCKED. |
| T14 SRAM/map/ownership | RX/TX workspaces exactly 194 B each; static .data+.bss 894 B; conservative stack 294 B; reserve 860 B; no second ADC staging buffer or unbounded queue. | On-board watermark, physical UART occupancy and live overflow/ownership trace are NOT RUN. |
| T15 STOP congestion / MCU fault | Host and native tests cover STOP priority, pending TX reply and STOP during ADC batch; fail-closed output state is software-tested. | Physical MCU reset/freeze, independent enable cutoff and measured driver inactive waveform are NOT RUN. |
| T16 ADC acquisition / precision | Firmware has bounded conversion timeout and explicit PRECONDITION_INVALID / CONVERSION_TIMEOUT / NOT_ACQUIRED slots; cadence scheduler is unit-tested. | Installed sensor variant, VREF/filter, traceable reference, uncertainty budget and physical accuracy limits are unknown/BLOCKED. |
| T17 Loss / companion package | Software verifies companion manifest, RawLog/Evidence hashes and tamper cases; hosted profile verifies loss-window summaries. | Target-host restore and real interrupted-storage reconciliation remain NOT RUN. |
| T18 fsync / deadline | 10,000-sample target-host synthetic fsync profile exists; GitHub-hosted production path completed 31 stages with all 310 loss summaries. | Actual target-host full production-path profile, including command intent, Evidence, RawLog finalize/recovery and backup/restore, remains NOT RUN. |

**Formal disposition remains NOT ACCEPTED.** The table records software evidence only; it does not convert any physical subtest to PASS. The outstanding R01, T13/T15 physical qualification, T16 analog reference qualification, T18 target-host production profile and HW01–HW08 gates must close before formal 310-5 acceptance.

## 7. One required target-host software run

The optional T18 target-host diagnostic uses only `InMemoryProtocolV2Transport` and `InMemoryIndependentStopWriter`. It does not open `/dev/ttyACM0`, `/dev/ttyUSB0`, or any serial device, and it does not energize hardware. It performs real RawLog, command-intent, Evidence and filesystem fsync operations on the selected host filesystem.

Run it from the existing local clone on the target storage, using a **new output root**. The previous incomplete root and its `.310-rearm-inhibited` marker are left untouched:

```bash
cd ~/mini4wd-ai-system-t18-pr190 &&
git fetch origin integration/310-5-unified-candidate &&
git switch integration/310-5-unified-candidate &&
git pull --ff-only origin integration/310-5-unified-candidate &&
test ! -e artifacts/310-t18-production-final-20261108-01 &&
python -m measurement_310.t18_production_profile \
  --output-dir ./artifacts/310-t18-production-final-20261108-01
```

The expected output directory contains `t18-production-profile.json`, `t18-production-stage-profile.csv`, their checksum, and a `rawlog/` tree. The JSON includes per-stage fsync target counts/total/max, p50/p95/p99/p99.9/max, stage timing, RawLog/Evidence/intent hashes, 310 loss-window summaries and validation results. A PASS requires 31 stages, 3,100 ADC_BATCH frames, 37,200 ADC_SAMPLE records, 310 passing loss-window summaries, verified companion Evidence bundle and exactly one normal-completion STOP_REQ through the in-memory writer. Stage elapsed time is observational only and is not an acceptance gate.

If this command fails or stalls, preserve the output root and process/storage evidence. Do not delete the output, remove the old marker, kill a D-state process, or rerun over the same output path. This run closes only T18 target-host software/storage evidence; it does not authorize or replace HW01–HW08.


---

## 2026-11-09司令塔訂正：リスクベース再評価によるT18 / HW資格条件の更新

本節は上記の旧記述のうち、8,000ms合否条件および一律必須の物理保護要求に優先する。Issue #35の2026-11-09リスクベース再評価基準を適用する。

### T18の扱い
- 8,000ms stage ceiling、STOP reserve 1,000ms、追加margin 1,000msを用いた合否判定は廃止する。
- stage elapsed、p50/p95/p99/p99.9/max、fsync target別時間、finalization時間は診断値として保持する。
- T18のPASS/FAILは、stage/batch/sample件数、ADC loss windowの整合、RawLog validation、Evidence bundle、command-intent記録、normal completion STOP_REQ等のデータ・イベント整合性で判断する。
- target-host profileは実際のfilesystem性能と保存/復旧挙動を把握する診断として残す。8秒を超えたことだけを理由に310-5を停止しない。
- 遅延がstage progression、実際に要求されたSTOP処理、指令結果の照合、データ整合性を阻害した場合は、その具体的影響を別途評価する。

### HW01–HW08の扱い
- HW01のMCU・基板・配線同定と、電源/電流制限/保護素子/発熱条件の確認は、機器損傷防止のため優先する。
- HW02のFuse/BOD確認、HW03の外部supervisor、HW05のEEPROM全write境界電源断、HW07の独立STOP回路は、すべて一律必須とせず、現物条件と故障シナリオに基づき必要性を判断する。Fuse writeは禁止のまま。
- HW04のreset後出力OFF・ARM無効・no auto-resumeは維持する。resetそのものを防止することは要求しない。
- HW06は現行の測定目的に必要なADC入力を対象にし、A0/A4/A5とA1/A2/A3の役割を混同しない。
- HW07はソフトウェアSTOP経路の動作確認と、独立物理STOP/cutoffの必要性判断を分ける。手の届く主電源遮断スイッチを運用条件として評価する。
- HW08の310秒実機測定は、電源・配線・current limitの確認後に別途明示承認を得る。今回の訂正はHW08の実施許可ではない。

### 正式受入の表記
- T18 target-host診断の未実施または8秒超過のみを310-5の自動FAIL条件にしない。実施済みの診断値と未実施理由/残留リスクは正直に報告する。
- R01は、UNKNOWNをSUCCESSにしないこと、reset/recovery後に古いnonzero commandを自動再送・自動再開しないことを維持する。全コマンド同期fsync/hash-chain、全履歴の個別operator decision、独立物理safe-state assertionを一律必須とするかは再評価する。
- 受入に必要な残りの項目は、Issue #35およびdocs/310/310-5-risk-based-reassessment-2026-11-09.mdの分類と理由に従って確定する。

この訂正も、310-5正式受入、310-6移行、Arduino/serial接続、firmware upload、Fuse/EEPROM操作、motor energization、310秒実測の許可ではない。HARDWARE_CURRENT_LIMIT_CONFIRMED=falseを維持する。
