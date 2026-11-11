# 310-7 310プロセス完了報告・Benchmark引継ぎ — 2026-11-11

## 1. 司令塔方針

2026-11-11の司令塔方針転換に従い、310の最低限の完了と実用化を優先する。実機安全性の未確認だけを理由にソフトウェア/UI工程を停止しない。モーター運転時に発生する実用上の不具合は、Issue #172等のBenchmark実測工程でログを根拠に吸収・修正する。

この方針は未実施の物理試験をPASSに変更するものではなく、物理モーター運転の包括許可でもない。

## 2. 310工程の集約

| 工程 | 状態 | 根拠・補足 |
|---|---|---|
| 310-1 | Accepted | HEAD `5db3314` |
| 310-2 | Accepted | HEAD `e10d06b` |
| 310-3 | Accepted | HEAD `d9e718b607a873759fffd58fc75bf950af499095` |
| 310-4 | Design/integrity review completed | 既存の設計・整合性審査成果を保持。未実施の物理証明へ拡張しない |
| 310-5 | Accepted with restrictions — software/host scope | PR #193 merge commit `f875e05f1eff397160f26a5ade390d8860977049` |
| 310-6 | Integrated — UI/host scope | PR #198 merge commit `1161b8fac86dec7cbb9a8fdd1fdadd9e32b7ef41` |

### 310-5

受入対象はソフトウェア/ホスト実装、RawLog/Evidence保存・回復、R01 no-auto-rearm gate、same-UART priority STOP、T18 integrity/persistence diagnostics。物理STOP/pin/reset/current cessation/current limit/thermal qualificationはPASS宣言していない。

### 310-6

既存のproduction Protocol V2 stackをUIへ統合した。
- `ProtocolV2HostSession` + `SequenceController`
- `PySerialTransport` same-UART priority STOP
- `RawLogV2Writer` + `TransportEvidenceJournal` / Evidence bundle
- 100ms Qt timerから専用QThreadへtickをqueueし、serial/ACK/sequence/RawLog処理はUI thread外
- PythonがPWM0〜30、各10秒、31段階を進行管理
- RawLog Library正式IDとMotor Instance/sessionを紐付け
- ADC_BATCHのA0〜A5を個別raw sampleとして保存。A0/A1平均や旧DATA26派生値を生成しない
- incomplete workとEvidenceを閲覧・回復でき、re-arm inhibitを自動解除しない
- GitHub exportはmanifest/records/Evidence sidecar/bundle manifestを検証して登録

検証:
- Host regression/UI smoke: 661 passed, 2 xfailed — run 43026233332
- ATmega328PB / MiniCore 3.1.3 / 16MHz compile: PASS、HEX/ELF/MAP artifact 13856624486 — run 43026233493
- T18 production-path workflow: PASS — run 43026233582

Compileはupload/EEPROM/fuse操作を含まない。

## 3. 維持する制約

- `HARDWARE_CURRENT_LIMIT_CONFIRMED=false` を維持する。
- 物理STOP、reset中GPIO、ENA/ENB、current cessation、独立current limit、thermal protectionを未実施のままPASSとしない。
- Arduino接続、firmware upload、EEPROM/fuse操作、motor energization、310秒実機測定は、対象作業への明示的なユーザー指示なしに実施しない。
- USB serial openはArduino resetを誘発する。次session開始時はL298N 12V driver supplyをOFFにしてから開く運用確認をUIに設ける。
- STOP/通信断/UNKNOWN後に過去のnonzero commandを自動再送しない。recovery markerは自動解除しない。
- CI/compile成功を実機動作・物理安全性の証明へ読み替えない。
- 既存ハードウェアの変更・追加を前提としない。

## 4. Benchmarkへの引継ぎ

Issue #172を実測工程として維持する。
- PWM0〜30を各10秒、Python主導で進行。
- Protocol V2 ADC_BATCHのA0/A1/A4/A5を個別raw/timestampとして記録。A2/A3はreference-only。
- 回転ラベルは目視EVENTとして記録し、測定値やDerivedへ混入させない。
- 実測で判明した通信、タイミング、ノイズ、回転開始、停止、運用上の問題は実ログを根拠に修正し、再検証する。
- 実機工程は明示的な実施指示と運用条件の下で行う。現時点で実測ログは未取得。

## 5. 310-7完了条件

1. 310-1〜310-6の受入範囲・証拠・残留制約をこの報告に集約する。
2. Issue #172をBenchmark実測・分析の継続先として明示する。
3. 310全体のソフトウェア/host process closureと、物理Benchmarkの完了を別々に管理する。
4. 本報告のレビュー後、310プロセスのソフトウェア/host範囲を完了とする。

本報告は物理Benchmark完了報告でも、実機通電許可書でもない。
