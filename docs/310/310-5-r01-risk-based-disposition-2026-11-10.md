# 310-5 R01 リスクベース運用判定 — 2026-11-10

## 目的と優先順位

本書は、Issue #35 の 2026-11-09 司令塔決定を、PR #193 の現行実装および2026-10-28にユーザーが共有した物理回路の正本と照合した運用判定である。旧R01文書に残る「全コマンドの同期fsync/hash-chain」「全履歴の個別terminal-safe化」「独立物理safe-state assertion」を一律必須とする記述は、Issue #35 のリスクベース方針に反する範囲で本書により置き換える。

この判定は、310-5正式受入、310-6移行、実機操作の許可ではない。

## 既共有の物理配線を正本とした確認

2026-10-28に共有された新仕様配線を、再確認を求めず物理回路の正本として適用する。

- 電源経路：12V DC adapter (+) → physical main switch → 2200µF + 0.1µF → L298N motor-driver supply path。
- モーター側電流経路：L298N → ACS712 #1（A0）→ A4 voltage-sense point → motor (+) → motor (−) → A5 voltage-sense point → ACS712 #2（A1）→ L298N (GND) → GND。
- Arduino Uno：PC USBから5V給電。したがって主電源スイッチをOFFにするとL298N側のスイッチ後電源経路は遮断される一方、Arduino自体はUSB給電で通電を継続し得る。
- A0/A1は独立したACS712入力。A4/A5は独立した電圧検出点。A2=KY-024、A3=thermistor。各センサー系とArduinoのGNDは共通。
- ACS712各系には1kΩ LPFが共有仕様に記載されている。

この既共有配線定義により、主電源スイッチの設計上の遮断対象はL298N側の電源経路と判断できる。Arduino USB電源まで遮断するスイッチではない。これは共有済み配線図・仕様に基づく回路トポロジーの判断であり、現在の実装個体での導通測定や電圧測定を実施したという意味ではない。共有仕様と現物が異なる場合のみ、その差分確認が残る。

## 実装確認結果

PR #193 の以下の実装をソース確認した。

1. `SequenceController.startup_recover()` は、未完了workを回復する前に `.310-rearm-inhibited` を永続化する。既存のre-arm markerまたはEvidence reconciliation markerがある場合、または未完了workを回復した場合は、当該controllerの `start()` を拒否する。
2. `SequenceController` は各stage送信直前にもmarkerを確認し、markerが残る場合は非zero指令への進行を拒否する。
3. Protocol V1/V2のserial-backed送信経路にもmarker確認があり、markerが残る間はARM/nonzero送信を拒否する。UNKNOWNのwrite/flush/ACK結果をSUCCESSに読み替えない。
4. `measurement_310/recovery_release.py` は明示起動のみであり、startup/recoveryから自動実行されない。serial portを開かず、STOP/ARM/PWMを送らず、測定も開始しない。
5. release helperはRawLog rootのsymlink/非directory、未完了work、symlink/non-regular marker、operator ID/note欠落を拒否する。主電源OFF・ローター停止、および主電源スイッチがL298N motor/driver supplyを遮断することについて、別々のoperator confirmationを要求する。
6. operator action auditを追記してfile fsyncした後にmarkerを削除し、最後にroot directoryをfsyncする。物理状態は独立計測ではなくoperator attestationであると明記する。

## 運用上の境界

- releaseは、過去のcommand outcomeを検査・再構成・SUCCESS化する処理ではない。元のRawLog、intent、Evidenceを変更せず、UNKNOWNはUNKNOWNのまま扱う。
- `--decision-note` には、確認した対象と未解決のUNKNOWNをどう扱うかを簡潔に記録する。UNKNOWNを成功・ACK済み・物理停止確認済みとして記録してはならない。
- marker解除は自動再開ではない。release後も新しいcontroller/processで明示的な新規操作を開始する必要がある。markerを読み込んだ既存controllerのin-memory review latchは解除されないため、既存プロセスをそのまま再利用しない。
- 共有済み配線仕様上、主電源スイッチはL298N側の電源経路を遮断し、Arduino USB給電は残る。release helperを実行する際は、共有仕様と現物が一致していることを運用者が確認できることが条件。共有仕様との不一致や判断不能があればmarkerを残す。
- 主電源OFFまたはローター停止を判断できない場合、あるいはUNKNOWNの扱いを判断できない場合はmarkerを残し、再ARMしない。

## R01のリスクベース判定

| 項目 | 判定 | 根拠 / 残件 |
|---|---|---|
| recovery markerによる自動再始動抑止 | SOFTWARE CANDIDATE PASS | SequenceController / Protocol V1 / V2の送信境界とhost regressionで確認。実機reset後の挙動は未確認 |
| 手動operator release | SOFTWARE CANDIDATE PASS | incomplete work拒否、symlink拒否、二段階attestation、audit先行、marker解除のhost testあり |
| 全command journal / 全履歴の個別physical proof | NOT REQUIRED AS A BLANKET GATE | Issue #35の費用対効果再評価により一律要求しない。UNKNOWNをSUCCESSにしない原則は維持 |
| main switchのL298N供給遮断 | DESIGN CONFIRMED / PHYSICAL CONTINUITY NOT MEASURED | 共有済み配線ではadapter (+)からmain switchを経てL298N側へ給電する構成。ArduinoはPC USB給電で別系統。共有配線と現物が一致する前提で設計上の遮断対象は確認済み。導通測定は未実施 |
| reset後の物理出力OFF / no auto-resume | NOT RUN | source/host testのみ。実機波形・物理動作は未確認 |
| target-host T18 profile | NOT RUN | hosted CIでは代替不可。8秒超過は単独FAIL条件ではない |
| current limit / 電源 / 配線 / 発熱 | BLOCKED / NOT RUN | `HARDWARE_CURRENT_LIMIT_CONFIRMED=false`を維持 |

## 2026-11-10 hosted verification reference

- PR #193 headとして指定された `b752a691a79676c6992aa93b867e9a2d708a6474` のT18 production-path workflow run #51（run ID `42549695143`）: job completed / success。
- 同headのBreak-in and Battery Tests workflow run #1710（run ID `42549695024`）: 4 jobsすべて completed / success。
- これらはGitHub-hosted software evidenceであり、target PCのfilesystem/fsync特性、物理STOP、主電源遮断、current limit、reset波形の証明ではない。

## 結論

R01のhost software candidateは、リスクベースの簡素なmanual releaseを含めて実装・host test済みと評価する。ただしR01全体の正式PASSにはしない。主電源スイッチの設計上の遮断経路は既共有配線から確認できた。なお、現物導通、current-limit/電源/配線/熱の現物確認、必要な物理no-auto-resume確認は未実施であるため、310-5は未受入、310-6は引き続きBLOCKEDとする。

本書はArduino接続、`/dev/ttyACM0` / `/dev/ttyUSB0`アクセス、firmware upload、Fuse/EEPROM操作、モーター通電、310秒測定を許可しない。


## 2026-11-10 follow-up source audit — firmware conformance and supply ambiguity

This follow-up is a source/document review only. No hardware was connected or energized.

### Confirmed firmware/specification mismatch

The current branch copy of `firmware/motor/MotoreRev.ino` still contains the following behavior in `updateSensors()`:

- `sensor.currentAvg = (sensor.current1 + sensor.current2) / 2.0f`
- `sensor.currentAvg` is then used by brush-peak detection.
- `sensor.power` is calculated using `sensor.motorVoltage * sensor.currentAvg`.

This conflicts with Issue #35's canonical sensor contract: A0/ACS712 #1 is the winding-current channel; A1/ACS712 #2 is a separate brush-stability observation; A0 and A1 must not be averaged or treated as interchangeable current channels. Therefore the current firmware source is **FAIL — SPECIFICATION NONCONFORMANCE** for this requirement. It must not be described as 310-4/310-5 compliant until corrected and regression-tested. This finding is based on source inspection, not physical behavior.

### Reset behavior — evidence boundary

The inspected source initializes the PWM and direction pins as outputs, writes PWM=0 and direction LOW, initializes `driveArmed=false` / empty ARM token, and calls `stopMotor()` before entering READY. STOP also clears the ARM token. This supports the software initialization/no-stale-token design.

It does not establish the electrical pin state during the MCU reset-to-`setup()` interval, the L298N enable input's behavior while the MCU pins are high-impedance, or the physical motor output during brownout/reset. Those remain **NOT RUN** until separately authorized physical verification. No claim of physical no-auto-resume PASS is made.

### Supply description — unresolved electrical ambiguity

The already-shared circuit description literally says `12VAC adapter (+)` and then routes that point through a physical switch and `2200µF + 0.1µF` to the L298N supply path. The notation is internally ambiguous:

- An AC output has no fixed positive terminal (`+`).
- A polarized 2200µF electrolytic capacitor must not be assumed safe directly across an unrectified AC source.
- The documented path does not identify a bridge rectifier, DC output rating, polarity, or adapter model.

This may be a wording error for a 12V DC adapter, but that must not be silently assumed. Until the actual adapter output is identified as AC or DC and its rated voltage/polarity are established from its label/specification, the L298N supply path, capacitor polarity/voltage stress, and current-limit assessment remain **BLOCKED**. Do not energize the circuit to discover the answer.

### Updated disposition

| Item | State |
|---|---|
| A0/A1 independent-channel contract in current firmware source | **FAIL — source-level mismatch** |
| Startup software defaults / ARM token invalidation | SOURCE REVIEW PASS; physical reset interval NOT RUN |
| Physical reset/no-auto-resume | NOT RUN |
| Adapter output type, rated voltage and polarity | BLOCKED — description ambiguous |
| Driver supply / capacitor suitability / current limit / thermal qualification | BLOCKED / NOT RUN |
| R01 host software candidate | SOFTWARE CANDIDATE PASS only |
| 310-5 formal acceptance | NOT ACCEPTED |
| 310-6 | BLOCKED |
| `HARDWARE_CURRENT_LIMIT_CONFIRMED` | `false` — unchanged |

The firmware mismatch requires a compliant code correction under the applicable 310-4 change process before the safety review can pass. The adapter ambiguity requires identification from existing markings/specification; it does not authorize a live measurement. No Arduino connection, serial access, firmware upload, motor energization, or 310-second run was performed or authorized.


### Owner clarification — supply is DC 12V (2026-11-10)

The project owner clarified that the adapter supply is **12V DC**, not AC. This resolves the AC/DC ambiguity in the earlier wording `12VAC adapter (+)`. The canonical power-path description should therefore be interpreted as a 12V DC supply feeding the physical switch and the `2200µF + 0.1µF` input-capacitor network before the L298N supply path.

This clarification does **not** independently establish the adapter's actual output polarity, regulation/tolerance, current capability, capacitor polarity/voltage rating, wiring continuity, or current limiting. Those electrical qualification items remain NOT RUN / BLOCKED pending documentary/nameplate evidence and appropriately authorized non-energized inspection. No live test is implied or authorized.

Updated disposition: supply type = **DC 12V, owner-confirmed**; polarity/rating/current capability and downstream protection = **NOT YET VERIFIED**. `HARDWARE_CURRENT_LIMIT_CONFIRMED=false` remains unchanged.


## 2026-11-10 follow-up — A0/A1 data-flow impact audit

The source audit was extended beyond the firmware producer. This is a static source review of the current PR branch; it does not change the legacy DATA26 wire format or RawLog v1 originals.

### Canonical meaning (Issue #35)

- A0 / ACS712 #1: winding-current measurement. This is the only one of the two ACS712 channels that may supply winding current for current-based control, power, and winding analysis.
- A1 / ACS712 #2: independent brush-stability observation. It must not be converted to an interchangeable winding-current value, averaged with A0, or substituted for A0.
- A4 and A5 remain independent voltage inputs.
- RawLog v2 is a separately specified format. The old DATA26 / RawLog v1 fields do not become valid v2 fields merely because their names remain in legacy code.

### Confirmed legacy data-flow impact

| Layer | Existing legacy fields / behavior | Required disposition |
|---|---|---|
| Firmware acquisition | `current1` from A0 and `current2` from A1; both converted using ACS712 sensitivity | Retain A0 conversion for winding current; A1 must remain a raw independent observation unless its physical meaning is separately approved |
| Firmware derived values | `currentAvg` averages current1/current2; feeds brush peak, power, current ripple, peak power/current | Remove these cross-channel derivations; do not replace by blindly renaming A0 as old average |
| DATA26 serializer | Emits current1, current2, current_avg, power, current_ripple, peak_current, brush_peak_current | Preserve historical RawLog v1 bytes/schema; mark legacy derived fields as non-authoritative/deprecated in the new contract; do not present them as v2 semantics |
| Python protocol/parser | `CSV_FIELDS` and parser require the fixed 26-column contract including current_avg and derived fields | Legacy parser compatibility is coupled to DATA26; any firmware column removal/reordering requires a separately approved protocol migration, not an isolated firmware edit |
| MeasurementManager | Requires and finite-checks current_avg, power, current_ripple, peak_current, brush_peak_current; constructs Measurement from them | New measurement/control path must consume A0-derived winding current and independent A1 observation explicitly; old required derived fields cannot be treated as valid safety/control inputs |
| Measurement model / builder | Stores current1/current2 plus current_avg, power, current_ripple, peak_current, brush_peak_current | Separate raw/converted channel observations from approved derived values; avoid relabeling A1 as current |
| FeatureExtractor / PerformanceAnalysis | average_current reads current_avg; torque estimate consumes it; brush lifecycle reads brush_peak_current | Torque/current estimate must use valid A0 winding-current samples; brush lifecycle cannot continue using the firmware's A0/A1 averaged brush_peak_current |
| BreakinController | Brush peak approach reads brush_peak_current; current safety helper scans current1, current2, current_avg | Safety current must use A0 only. A1 must not be treated as current or used as a substitute. Brush stability logic requires a separately defined A1 observation algorithm/threshold before use |
| UI / DB / config | Legacy current_avg/power/ripple/peak fields appear in column lists, model fields, UI display and SQL schema | Treat as legacy compatibility only; v2 schema must follow Issue #170 and Issue #35 rather than perpetuating these old derived semantics |

### Change boundary and correction decision

1. The firmware defect is confirmed: A0 and A1 are averaged and the average is used for brush peak and power/ripple/peak calculations.
2. A firmware-only substitution (e.g. setting `currentAvg=current1`) is insufficient: it would leave the old `brush_peak_current` name/meaning misleading, and the Python control/analysis path would still accept the legacy derived values.
3. Removing DATA26 columns or changing their order in-place is also not acceptable: it breaks the current fixed-width legacy parser and would rewrite the meaning of existing RawLog v1 records.
4. Therefore the corrective implementation must be a coordinated, explicitly versioned 310-4 change: preserve old RawLog v1 originals, prevent legacy averaged/derived fields from being accepted as current safety/torque/brush evidence, define an independent A1 observation field/validity contract, and make the new RawLog v2 schema consume named A0/A1 raw samples plus calibration/timestamps per Issue #35 / Issue #170.
5. Until that coordinated change is implemented and regression-tested, current A0/A1 source contract remains **FAIL**. This finding blocks 310-5 acceptance. No physical test or firmware upload is authorized by this audit.

### Required regression coverage before re-review

- Firmware/source tests assert there is no A0/A1 averaging and no A1-derived winding-current or power/control input.
- A0 calibration/conversion tests prove winding-current calculations depend only on A0 raw value and the A0 calibration snapshot.
- A1 tests prove it is retained as an independent observation and cannot satisfy A0 current validity or current safety gates.
- Firmware DATA/serial contract tests explicitly document whether legacy DATA26 fields are retained as deprecated compatibility fields or superseded by a new protocol version; no silent column reorder/removal.
- Python parser/MeasurementManager tests reject missing/invalid A0 control current and do not require legacy A0/A1-derived averages as authoritative inputs.
- BreakinController tests prove over-current safety uses A0 only, and A1 missing/abnormal observations are not miscounted as missing A0 control feedback.
- FeatureExtractor/PerformanceAnalysis tests prove torque uses A0-derived winding current and brush-life analysis does not consume the old averaged brush peak.
- RawLog v1 byte-preservation and RawLog v2 schema tests prove the legacy original is unchanged and v2 records preserve distinct A0/A1 samples and their calibration/time metadata.

### Status

**FAIL — A0/A1 firmware and legacy consumer semantics remain nonconforming.** The audit defines the coordinated correction boundary; it does not claim the correction has been implemented. 310-5 remains NOT ACCEPTED and 310-6 remains BLOCKED.
