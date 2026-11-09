# 310-5 R01 リスクベース運用判定 — 2026-11-10

## 目的と優先順位

本書は、Issue #35 の 2026-11-09 司令塔決定を、PR #193 の現行実装および2026-10-28にユーザーが共有した物理回路の正本と照合した運用判定である。旧R01文書に残る「全コマンドの同期fsync/hash-chain」「全履歴の個別terminal-safe化」「独立物理safe-state assertion」を一律必須とする記述は、Issue #35 のリスクベース方針に反する範囲で本書により置き換える。

この判定は、310-5正式受入、310-6移行、実機操作の許可ではない。

## 既共有の物理配線を正本とした確認

2026-10-28に共有された新仕様配線を、再確認を求めず物理回路の正本として適用する。

- 電源経路：12VAC adapter (+) → physical main switch → 2200µF + 0.1µF → L298N motor-driver supply path。
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
