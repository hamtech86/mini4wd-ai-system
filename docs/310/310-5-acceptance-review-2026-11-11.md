# 310-5 正式受入審査用まとめ — 2026-11-11

## 1. 現在の判定

- PR #193 current branch: fix/310-5-t18-durable-batching
- 統合コード commit: 7992b5154613f2cf5fe195adc8ae4778c50415aa
- 現在の文書HEAD: c9f9503982a9779fac005b5ea7fc055a99a92575（統合後の文書更新のみ）
- STOP priority実装PR #197はPR #193候補へsquash merge済み。
- ソフトウェア・ホスト側の主要検証はPASS。310-5の正式受入は上位司令塔の宣言待ち。
- 本書は物理的なハードウェア安全認定ではない。HARDWARE_CURRENT_LIMIT_CONFIRMED=falseを維持する。

## 2. 主要なPASS証拠

| 領域 | 結果 | 証拠 |
|---|---|---|
| 全リポジトリ回帰 | PASS — 655 passed / 2 xfailed | GitHub Actions run 43007309667 |
| RawLog / Sequence回帰 | PASS | run 43007309667 |
| Battery / Break-in回帰 | PASS | run 43007309667 |
| T18 hosted production path | PASS | run 43007309565 |
| ATmega328PB compile | PASS | run 43007309632 |
| Legacy DATA26 retirement / native motor safety | PASS | run 43007309635 |
| Protocol V2 native codec | PASS | run 43006802183（統合コードにfirmware変更なし） |
| Database path safety phase 2 | PASS | run 43006802251 |
| Target-host T18 profile / checksum | PASS | 2026-11-11 owner-run report: docs/310/310-5-target-host-t18-results-2026-11-11.md |

Target-host T18の主な結果:
- 31 stages / 3,100 ADC_BATCH / 37,200 ADC slots / 10,143 Evidence events。
- profile status PASS、checksum OK。
- sequence_complete最大 9,362.612762ms。10,000msの単回観測budget内。
- sequence_completeの観測回数は1回のためp99.9はNOT MEASURABLE。PASSと扱わない。
- stage elapsed max 15,280.459091msは診断値。旧8,000ms ceilingは合否ゲートではない。
- durability operations changed=false。

## 3. STOP通信経路

独立した第2の物理STOP端点を必須とする条件を外し、既存の単一モーターUART (/dev/ttyACM0) に同一UART優先送信を実装した。/dev/ttyUSB0はバッテリー放電FTDIであり、STOP経路として使用しない。

- PySerialTransportが唯一のserial.write() ownerとなる。複数writerによるbyte interleavingは禁止。
- 通常送信のflush待ちはwrite lockの外に置き、通常flush待ちの間でもSTOP frameを書ける。
- STOP要求時にhost TX inhibitを先にlatchし、COBS delimiter + 完全なSTOP frameを送る。
- 送信中の通常writeだけはframe境界まで待つ。未開始の通常送信と以後の通常TXは拒否する。
- default write_timeout=100ms、STOP caller deadline=250ms。production factoryはwrite_timeoutがSTOP deadlineの半分未満であることを確認する。
- disconnected / short write / timeout / unresolvedはUNKNOWN。STOP成功や物理停止へ読み替えない。
- 通信断・STOP結果不明時はL298N 12V供給をOFFのまま保持し、再開・再ARMしない。

STOPの物理応答、PWM=0/D7/D8 LOWの実ピン状態、モーター電流停止、reset-to-setup期間の電気状態はNOT RUN。独立した電気的cutoffを実装したという意味ではない。

## 4. R01 no-auto-rearm / recovery

- SequenceController.startup_recover()は未完了workの回復・削除より先に.310-rearm-inhibitedを永続化する。
- ProtocolV2HostSessionはRawLog-bound factoryでre-arm rootを束縛し、send_stage_pwm()の本番ARM/nonzero境界で.310-rearm-inhibitedと.310-evidence-reconciliation-requiredを検査する。
- UNKNOWN write/flush/ACKはSUCCESSへ変換せず、同一sessionはfail-closed。古いnonzero commandを自動再送しない。
- recovery_release.pyは未完了RawLog work、symlink、operator ID/note欠落、power-off確認欠落、main-switch isolation確認欠落を拒否する。auditをfsyncしてからmarkerを解除し、serialを開かず、STOP/ARM/PWMを送らない。
- releaseの物理状態根拠はoperator attestation only。独立した物理測定とは主張しない。
- Issue #35のリスク比例方針により、全コマンド個別のActuationSafetyJournal hash-chain / terminal-safe化 / independent physical assertionを一律必須とはしない。既存DurableIntentJournal、exact ACK correlation、persistent recovery marker、明示的operator releaseを採用する。

## 5. 電源・電流・熱の評価

- Owner-provided supply rating: **12.3V DC / 5A**。これは提示済み定格であり、センサーで読み取ることを要求しない。
- ST L298 datasheet DS0218 Rev.5: motor supply operating up to 46V、DC current up to 2A per channel、total DC current up to 4A、overtemperature protection。外部sense resistor端子があり、current control/protectionはsense signalと外部chopping/enable controlを組み合わせる設計として記載されている。
- 12.3VはICのmotor-supply上限内。ただし5A supply ratingは2A/channel current limitを意味しない。ACS712は測定素子であり、ハードウェア遮断器ではない。
- よってHARDWARE_CURRENT_LIMIT_CONFIRMED=falseを維持する。電源定格がセンサーで読めないことだけを理由にFAILとはしないが、5A供給能力からL298N channel current protectionを推定もしない。
- capacitor voltage/polarity、adapter transient/short-circuit protection、実装基板のsense/enable詳細は既存仕様だけで断定しない。測定不能値を反復要求せず、未確定の保護機能をPASS扱いしない。
- これは物理HW08の実施制限。新センサー、回路変更、部品追加、配線変更は要求しない。

References:
- STMicroelectronics L298 datasheet DS0218 Rev.5: https://www.st.com/resource/en/datasheet/l298.pdf
- STMicroelectronics L298 product page: https://www.st.com/en/motor-drivers/l298.html

## 6. Reset / power restoration / physical limits

- ArduinoはPC USB 5Vで独立給電。12.3V DC supplyはphysical main switchを経由してL298N driver supplyへ入る。
- Main switch OFFはL298N supply pathを遮断する設計だが、Arduino USB給電は継続し得る。したがってOFF操作だけではMCU resetやSTOP latchを意味しない。
- setup()最初期のsafe GPIO initializationとboot時のfresh session/no command replayはsource-level evidence。MCU reset中のhigh-impedance GPIOとL298N enable inputの物理状態はNOT RUN。
- 既存機器を改造しない運用手順として、planned interruption前にSTOP、driver supply OFF、rotor停止確認、driver supply OFFのままArduinoをUSB再起動、fresh host/device session、明示的な新ARM後にのみdriver supply復帰を採用する。
- unexpected reset / communication loss / unknown stateではdriver supplyをOFFのまま保持し、auto-rearmしない。この運用手順は物理安全保証ではない。

## 7. 残留項目と受入範囲

| 項目 | 状態 | 取扱い |
|---|---|---|
| Physical STOP / pin waveform / current cessation | NOT RUN | 実機試験未承認。物理PASSを主張しない |
| Reset GPIO high-impedance interval / physical no-auto-resume | NOT RUN | source/host evidenceと分離 |
| Current limit / adapter transient / thermal hardware qualification | NOT RUN / NOT CONFIRMED | HARDWARE_CURRENT_LIMIT_CONFIRMED=false。HW08の前提として保持 |
| EEPROM real power-cut / BOD fuse readback | NOT RUN | Issue #35のRELAX/INVESTIGATE。Fuse write禁止 |
| On-board stack watermark / analog accuracy | NOT RUN | static/host evidenceと分離 |
| UI heartbeat/status indication | 310-6 scope candidate | RUN/STOP/communication unknown/frozenを識別するUI作業は310-6で扱う。310-5の物理証明に読み替えない |
| HW08 310-second run | NOT AUTHORIZED / NOT RUN | 別途明示承認が必要。現状実施禁止 |

## 8. 上位司令塔への提案

**提案: 310-5を「ソフトウェア/ホスト検証範囲に限定した条件付き受入」として審査する。**

条件:
1. 受入対象はPR #193の現行ソフトウェア/ホスト実装、R01 recovery gate、same-UART STOP transport、T18 storage diagnosticsに限定する。
2. 310-6はUI統合のみを対象とし、Arduino接続、モーター通電、EEPROM/Fuse操作、物理STOP試験、310秒測定を含めない。
3. HARDWARE_CURRENT_LIMIT_CONFIRMED=falseを維持し、HW08は別途明示承認までBLOCKED/NOT RUNとする。
4. 物理STOP、reset pin state、current cessation、thermal/current-limit safetyをPASSと宣言しない。
5. 上位司令塔がこの制限付き範囲を明示的に承認した場合のみ310-5 ACCEPTED WITH RESTRICTIONSとし、そうでなければNOT ACCEPTED / 310-6 BLOCKEDを維持する。

本書自体は正式受入宣言でも、ハードウェア操作許可でもない。
