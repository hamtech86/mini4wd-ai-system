# 310-6 UI統合 実装状況 — 2026-11-11

## 現在の状態

- 実装PR: #198（Ready for review）
- 基点: 310-5 条件付き受入済み integration branch
- UI/host統合: 実装中
- 実機接続・firmware upload・motor energization・310秒実機測定: NOT RUN
- `HARDWARE_CURRENT_LIMIT_CONFIRMED=false` を維持

## 採用した実装経路

既存の firmware `MotoreRevV2` はProtocol V2のbinary frameとADC_BATCHを使用する。PR #176/#177の旧ASCII DATA/AUX変換controllerを本番UIへ接続すると、現在のfirmware/host契約と二重化・不整合になるため、PR #198では使用しない。

本PRの本番経路は既存の次の実装を再利用する。

- `measurement_310.ProtocolV2HostSession`
- `measurement_310.SequenceController`
- `measurement_310.PySerialTransport`
- `raw_log_v2.RawLogV2Writer`
- `measurement_310.TransportEvidenceJournal` / Evidence bundle

旧ASCII controller、PR #177独自のv2 schema/storeはPR #198から除外済み。

## UI / worker

- MainWindowにWinding PWM Sweep panelを追加。
- 100ms QTimerはworkerへのtick要求をqueueするだけ。Serial I/O、HELLO/ACK、PWM段階遷移、RawLog書込みは専用QThread側で実行し、Qt UI threadを待たせない。
- 開始前にMotor Instance、既存Break-in非稼働、既存ASCII ARM/STOP latch状態を確認。
- USB serial port open時にArduinoがresetされるため、実行時にL298N 12V driver supply OFFを確認する操作確認を表示。
- `PySerialTransport.startup_delay_s=2.0` を使用し、Arduino setup完了後にHELLOを送信。
- 31段階（PWM 0〜30）、各10秒、Pythonが進行管理。
- 通常STOPとEmergency STOPはworkerへqueueし、同じProtocol V2 host sessionの優先STOP経路を使う。
- 1回のV2 session終了後はアプリ内の旧ASCII ARM/再接続を無効化し、次sessionはアプリ再起動とdriver supply OFFの運用を要求する。

## RawLog / ADC / Evidence

- RawLog Libraryがcanonical MOTOR log IDを発行し、選択Motor Instanceとmeasurement_session_idを紐付ける。
- 実測データは既存 `raw_log_v2` schemaで保存。別schemaを複製しない。
- ADC_BATCHのA0〜A5各slotを個別のraw ADC sampleとして保存。A0/A1平均、旧DATA26列からの電流/電力/温度/ブラシpeak推定は生成しない。
- A2/A3はraw reference sampleとして保存されても、制御・停止・異常判定には使用しない。
- RawLog packageと外部Transport Evidence sidecarをbundle manifestでhash結合する。
- RawLog Library/Instance Historyからfinal packageまたは.recovery前の.incomplete workとEvidenceを閲覧可能。
- GitHub exporterはmanifest、records、Evidence sidecar、bundle manifest、metadataを登録し、Evidence bundleを検証してから登録する。未回復workは登録拒否。

## Recovery / no-auto-rearm

- SequenceController.startup_recover()を新session開始前に必ず実行。
- incomplete workの回復時は `.310-rearm-inhibited` を永続化し、自動で消去しない。
- 回復されたpackageに既存Evidence sidecarがある場合のみbundle manifestを生成し、再ARMは行わない。
- UNKNOWN/未確定のSTOP結果を成功に変換しない。

## 検証

最新実装HEAD `4a7179675e2c45b31228f24aabc1e4d646841cf1`:
- Host regression / UI smoke: **661 passed, 2 xfailed** — PASS (run 43026233332)
- ATmega328PB compile: PASS。HEX/ELF/MAPとboot identity provisioner compile-only artifact (run 43026233493, artifact 13856624486)
- 310 T18 production-path workflow: PASS (run 43026233582)
- Host tests include Qt tick coalescing, RawLog ID/instance association, Evidence bundle export, and recovery work inspection.

ATmega328PB compileはMiniCore 3.1.3 / 16MHz external clock target。upload、EEPROM write、fuse operationは未実施。


CI/compileはhost・compile範囲の証拠であり、実機通信、STOP pin、電流遮断、current limit、thermal qualificationの実証ではない。

## 残件

1. PR #198のreview/統合と310-6ソフトウェア範囲の正式受入。
2. 実機ベンチマークは別途明示的な実施指示と運用条件の下で行い、そこで得たログから実用上の不具合を修正する。

この文書は310-6のソフトウェア実装状況であり、実機運転許可ではない。
