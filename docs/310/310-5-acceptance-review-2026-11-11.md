# 310-5 正式受入審査用まとめ — 2026-11-11



---

## 2026-11-11 司令塔方針転換 — 受入範囲と後続工程（本節を旧結論に優先）

司令塔は、310の最低限の完了と実用化を優先し、実機安全性の未確認だけを理由に310全体または後続ソフトウェア/UI工程を停止しない方針へ変更した。

### 310-5 disposition

**ACCEPTED WITH RESTRICTIONS — software/host implementation scope.**

受入対象:
- PR #193の現行候補に含まれるソフトウェア/ホスト実装
- RawLog/Evidence保存・回復処理、R01 no-auto-rearm gate
- same-UART priority STOP host transport
- T18 integrity / persistence diagnostics
- 既掲のCI、host regression、compile-only evidence

受入範囲の限定:
- 本受入は物理STOP、GPIO波形、電流遮断、reset中のpin状態、current limit、thermal qualificationをPASSと宣言しない。
- これらのNOT RUN / NOT CONFIRMEDは記録として残すが、ソフトウェア/ホスト範囲の受入や310-6 UI作業を止める一律条件にはしない。
- `HARDWARE_CURRENT_LIMIT_CONFIRMED=false` は根拠が揃うまで維持する。これは未確認の保護機能をPASSにする変更ではない。
- 310-5受入はArduino接続、firmware upload、EEPROM/Fuse操作、motor energization、310秒実測を許可しない。

### 310-6 disposition

**PROCEED — UI/software integration.**

Issue #178を実行基準として、既存Qt event loopへのnon-blocking tick、Start/STOP、段階/PWM/経過時間/状態表示、RawLog v2 IDとmotor instance紐付け、complete/incomplete/faulted保存、History/GitHub登録を進める。既存identity/ARM/token/STOP/UNKNOWN、RawLog v2、A0/A1独立、A2/A3参考値限定の契約を維持する。

310-6のUI/host作業は、実機安全性の未確認を理由に停止しない。CI・compile・HEXは各々の証拠範囲で評価し、実機動作証明に読み替えない。

### Benchmark / physical operation

モーター運転時に生じる不具合・性能差・制約は、Issue #172等のベンチマーク工程で実測ログを基に切り分け、修正・吸収する。実機通電・測定は対象工程での明示的な実施指示後に行う。310-6 UI統合を物理試験待ちにしない。

### 310-7

310-1〜310-6の成果、残留事項、実用化上の制約を集約して310完了報告を作成する。ベンチマークで得た物理実測結果は、310のソフトウェア受入証拠と分けて記録する。

本節により、本文中の「310-5 NOT ACCEPTED」「310-6 BLOCKED」「物理確認完了まで後続工程を停止」とする旧結論を置き換える。
