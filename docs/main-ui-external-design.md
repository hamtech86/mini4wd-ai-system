# Main UI 外部設計正本

- 文書ID: MAIN-UI-EXT-DESIGN
- 版: 1.3
- 作成日: 2026-10-24
- 対象: `hamtech86/mini4wd-ai-system` の Main UI
- 関連: [Issue #35 — 最新仕様・正本](https://github.com/hamtech86/mini4wd-ai-system/issues/35)、[Issue #80 — Main UI改修](https://github.com/hamtech86/mini4wd-ai-system/issues/80)、[Issue #93 — 統合ゲート](https://github.com/hamtech86/mini4wd-ai-system/issues/93)、[PR #119 — Benchmark preset scope](https://github.com/hamtech86/mini4wd-ai-system/pull/119)、[PR #120 — TuneBasic INPUT ramps](https://github.com/hamtech86/mini4wd-ai-system/pull/120)

## 1. 文書の位置付けと優先順位

この文書を Main UI の画面構成・情報階層・操作・表示規則に関する外部設計の基準文書とする。

仕様の責任分界は以下のとおり。

1. **Issue #35**: ファームウェア / Python / UI 接続契約、DATA・RawLog、制御・安全規則、計測値の意味の正本。
2. **本書**: Main UI の画面構成、情報階層、表示、操作、状態表示、画面上のエラー扱いの正本。
3. **Issue #80**: 本書に基づく実装指示・進捗・差分追跡。設計本文を重複管理しない。
4. **PR #92**: 実装差分。設計の正本ではない。

本書と Issue #35 が競合する場合は Issue #35 を優先する。本書に明記されていない事項は未確定とし、担当者が旧画面・旧Issue・記憶から補完してはならない。設計変更は司令塔が本書を更新して行う。

## 2. Main UI の目的

Main は「セッティングシミュレーター」の実行画面であり、ユーザーが実行状態を把握し、安全に操作するための画面とする。

Main で確認できる情報:

- デバイス接続状態とデバイス識別状態
- Motor / Battery の対象切替
- Instance と Recipe の選択
- Sequence / 実行状態と進行状況
- 実行中の主要測定値
- LOG / ERROR LOG と、実際に保持しているエラー詳細
- 停止要求の状態と、停止確認が得られているかどうか

Main に詳細情報を集約しないもの:

- RawLog の個別データ管理・編集・詳細閲覧
- GitHub 保存先・保存処理の詳細管理
- Session 詳細
- Instance 詳細・履歴詳細
- 推定ロジックや Benchmark の独自計算結果を、実行画面の独自計算で再生成した値

詳細は既存の該当画面・機能で扱い、Main に新しい RawLog 管理機能や新規 History 機構を作らない。

## 3. 画面構成と情報階層

### 3.1 上部: 接続

- Main の上部に Motor / Battery の接続操作と接続状態を配置する。
- シリアルポートが開いている状態と、デバイス INFO による識別検証が完了した状態を区別する。
- INFO 検証前、失敗時、切断後、再接続後は、Issue #35 の契約に従い駆動可能と扱わない。
- 接続状態の表示だけを根拠に、デバイス識別済みとみなさない。

### 3.2 対象・設定

接続領域の下に Motor / Battery のタブを置き、その実行設定領域に以下を配置する。

- 左側: Instance dropdown
- 右側: Recipe dropdown

既存の操作体系を維持し、Benchmark 専用の独立セレクターを追加しない。画面幅に応じて縦配置へ変更してもよいが、選択項目の意味と操作順序は維持する。

### 3.3 実行状態・Sequence

- 現在の実行状態と Sequence の進行状況を識別可能に表示する。
- 進行状況は Controller / SequenceExecutor 等が提供する値を使用する。
- UI は時間や進行状況を独自に再計算しない。
- Backend が正規値を提供しない項目は `--` 等の未提供表示とし、推測値で埋めない。

### 3.4 主要測定値

実行中の代表表示を Main 上の一箇所にまとめ、同じ値を複数の主要領域に重複表示しない。

必須項目:

1. Input Voltage
2. Motor Voltage
3. Driver Input Current
4. DIR
5. PWM
6. Elapsed Time
7. Remaining Time

表示例（配置は既存UI規約に合わせてよい）:

```text
EXECUTION
DIR                    FWD
PWM                    xxx
Input Voltage          x.xx V
Motor Voltage          x.xx V
Driver Input Current   x.xxx A
Elapsed Time           xx.x s
Remaining Time         xx.x s
```

#### 表示値の取得・意味

- **Input Voltage**: 物理的な入力側電圧。INPUT 方式では FWD = `voltage1`（A4 / VM1）、REV = `voltage2`（A5 / VM2）。Motor Voltage から生成しない。TERMINAL 方式で物理的入力側電圧が取得できない場合は、制御用端子間電圧で代用せず、未提供を表示する。
- **Motor Voltage**: `motor_voltage` の符号付き生値 `V4 - V5`。絶対値化・方向補正・RawLog への書き戻しを行わない。
- **Driver Input Current**: 現行のセンサー定義では ACS712 #1 / A0 / `current1` はドライバー入力経路の電流。モーター巻線電流や High-side Current と呼ばない。値の意味が確認できない場合、別フィールドである `current_avg` などを代用せず `--` とする。
- **DIR / PWM**: Backend が報告する現在の方向・PWM 指令値を表示する。UI が独自に推定しない。
- **Elapsed Time / Remaining Time**: Controller / SequenceExecutor が提供する正規値を表示する。UI 側で `duration - elapsed` を再計算しない。値が提供されない経路では `--` とする。

DATA の列順・RawLog 本文・センサー値を表示都合で変更しない。無効値・欠落値をゼロに補完しない。実測ゼロはゼロとして表示し、欠損とは区別する。

## 4. Recipe 選択

プロジェクトオーナーの決定（2026-10-23）により、Benchmark の対象プリセットは **STD-I と Full-I のみ** とする。TERMINAL 方式（STD-T / Full-T）は電圧挙動が不安定になりやすく、高抵抗モーターが起動しない場合があるため、Benchmark の対象外とし、受入条件にも含めない。TuneBasic は Benchmark と独立した Recipe とする。

| Recipe | Benchmark Type | Voltage Control Mode |
|---|---|---|
| STD-I | STANDARD | INPUT |
| Full-I | FULL_PACKAGE | INPUT |

- UI の Recipe dropdown は STD-I、Full-I、`TUNEBASIC (FULL INPUT)`、独立した `TUNE_BASIC_INPUT_3V_CHECK` を表示する。Full TuneBasic は `TUNE_BASIC` レシピへ接続するが、Issue #98 が明示的に解除されるまでは選択・フェーズ確認・擬似レジューム計画のみとし、実行はUI・プログラム経路の両方で禁止する。
- 「3.00 V / 30 s」のような条件表示だけで制御方式を識別させない。
- 選択された Type と Mode は Backend の実行コンテキストへ明示的に渡す。
- INPUT 対応 Backend がない場合、実行をブロックして原因を表示する。別モードへ暗黙にフォールバックしない。
- Benchmark の既定モードも INPUT とし、既定ラベルは STD-I / Full-I とする。
- Benchmark の実行手順・制御アルゴリズムそのものは本 UI 設計の対象外であり、変更しない。

### 4.1 TuneBasic の INPUT 制御と実機ゲート

- TuneBasic は Benchmark とは独立した Recipe とする。Main の Recipe dropdown では、限定確認用 `TUNE_BASIC_INPUT_3V_CHECK` と全工程 `TUNEBASIC (FULL INPUT)` の両方を選択・確認できる。ただし Issue #98 が明示的に解除されるまでは、全工程 TuneBasic はフェーズ確認・擬似レジューム計画のみであり、UI とプログラムの両経路で実行を禁止する。現時点で許可されている実機確認は、FW 3.03 / BUILD `EXPLICIT-ARM-STOP-ACK-20261023-01` の識別確認後に行う、限定 `TUNE_BASIC_INPUT_3V_CHECK`（FWD 10秒 + REV 10秒、3.00 V、PWM 35–120）のみ。Issue #98 はこの実機結果と、後続運転を許可するかの明示的判断を管理する。
- レシピカタログ内の全 TuneBasic 電圧制御フェーズは INPUT モードを使用する。FWD は `voltage1` / V4、REV は `voltage2` / V5 をフィードバックに使う。
- INPUT モードは 3 V 開始だけでなく、3→9 V ランプ、9 V 保持、フェードアウト、最終 3 V ベンチマークまで引き継ぐ。ランプ制御が内部制御フェーズを生成する場合も、元フェーズの `voltage_control_mode` を保持する。
- `motor_voltage = V4 - V5` は符号付き端子間測定値として表示・保存する。INPUT 制御値の代用にしない。REV で負の `motor_voltage` が得られても、REV の INPUT フィードバックは V5 / `voltage2` を使う。
- 自動テスト・ログ・シリアル ACK は物理停止の証明ではない。Issue #98 が未完了でも、ソフトウェア準備・回帰テスト・UIの選択表示は継続できる。一方、Full TuneBasic は Issue #98 の明示的解除前には UI からも直接関数呼び出しからも開始できない。限定実機確認の合否・物理停止確認と、Full TuneBasic の実行許可は別々に記録する。

## 5. LOG / ERROR LOG

- LOG と ERROR LOG を区別して表示する。
- LOG は実行時の状態変化や操作結果を追える読み取り専用表示とする。
- ERROR LOG は実際に記録されたエラー情報を表示する。存在しない traceback や原因を UI で創作しない。
- 実装済みのエラー詳細コピー操作は、実際に保持している情報だけをコピーする。
- 通常ログとエラー詳細の内容を、RawLog の測定データとして保存・混入させない。

## 6. 停止と安全状態

- 停止要求を送ったことと、デバイスの物理停止を確認したことは別状態として表示する。
- 停止要求の送信成功だけで「停止確認済み」と表示しない。
- Backend が物理停止確認を提供しない場合、確認済み表示は行わず、未確認であることを明示する。
- 未識別デバイスに対する駆動操作の許可・拒否は Issue #35 の契約に従う。UI 表示だけで Backend の安全ゲートを代替しない。

## 7. Instance と推定4項目に関する境界

Issue #35 が定める推定4項目は次のとおり。

1. 推定無負荷回転数
2. 推定トルク
3. ブラシピークライフサイクル
4. 対応車重

本書では、これらの算出ロジックを定義・変更しない。推定値を RawLog に混入させず、実測値や公称値と誤認させない。

**Main の Instance 領域に「最終セッションの4項目」と「今回の新セッションの4項目」を2組表示するかどうかは、現存する正本の記述だけでは確定できていないため、未確定事項として明示する。** 司令塔による画面配置の確定前に、担当者が2組を追加・削除・移動してはならない。確定後は本節を更新して仕様化する。

Instance History は新しい History テーブルを作らず、既存の Instance → Session → RawLog → Note / Result の関係を用いる。外部作業単独の履歴レコードを新設しない。スマートフォン等による参考 RPM は RawLog Note の参考情報として扱い、公式測定値・推定値の入力・Benchmark 値へ昇格させない。

## 8. 明示的な非対象

この UI 改修では、以下を変更しない。

- Arduino Firmware の制御・センサー読取仕様
- Benchmark / Break-in / TuneBasic の制御アルゴリズム
- 推定4項目の計算式・係数・正式な意味付け
- RawLog の本文形式、DATA 26 項目の順序と意味、CAL 補助行契約
- DB スキーマ、保存先、GitHub 保存処理
- Session / Instance のデータモデル
- 無効値のスキップ・停止条件の意味
- UI から見えない Backend の動作を、表示都合で代替実装すること

これらの変更が必要な場合は、別途影響範囲と理由を提示し、司令塔の承認を得る。

## 9. 検証基準

### 自動テストで確認する項目

- STD-I / Full-I の名称・Benchmark Type・Voltage Control Mode の対応、および STD-T / Full-T が非対応であること
- 選択した制御モードが実行コンテキストへ伝播し、暗黙フォールバックしないこと
- Input Voltage / Motor Voltage / Driver Input Current の取得元と欠損値の扱い
- Elapsed Time / Remaining Time が Controller / SequenceExecutor の値を表示し、UI で再計算されないこと
- INFO 識別状態、未識別時の駆動ブロック、停止要求と物理停止確認の区別
- LOG / ERROR LOG の表示とエラー詳細コピー
- RawLog 26 項目・CAL 補助行・DB に対する非変更
- MainWindow のオフスクリーン生成と主要表示要素の存在

### 手動・実機確認で別途確認する項目

- PyQt 画面の配置、文字切れ、実際の操作性
- シリアル受信から DATA 解析、測定値更新、UI 表示までの連続経路
- 実機でのセンサー値表示
- 実行中の Remaining Time と pause / resume を含む実測挙動
- 実際の STOP 応答・物理停止状態
- INPUT / TERMINAL の実機動作と配線上の電圧意味

CI 成功は自動テストの成功を意味するだけで、画面目視・実機合格を意味しない。未実施項目は未実施と記録する。

## 10. 現時点の実装追跡

2026-10-24 時点で PR #92 の Main UI統合、PR #119 の Benchmark preset scope、PR #120 の TuneBasic INPUT ramp propagation、および commit `db3c117049839c3731f57f9661041052d0a4ac77` の Full TuneBasic UI公開は main に統合済み。PR #119 と #120 の CI は成功している。ただし、GUIの目視確認と Issue #98 が管理する実機安全性判断は自動テストとは別であり、本書はそれらの完了を宣言しない。今後の実装状態は main と Issue #93 / #98 の最新コメントで追跡し、古い Draft PR の本文を現行仕様として参照しない。

実装報告は以下を分けて記載する。

- 実装済み
- CI 検証済み（対象 HEAD を明記）
- GUI 手動確認済み
- 実機確認済み
- 未解決 / ブロッカー

## 11. 更新手順

- 画面仕様の変更は司令塔が本書を直接更新する。
- 更新時は版、日付、変更理由、影響する画面項目を記録する。
- 担当 Issue には本書へのリンクと実装タスクを記載し、同じ仕様を複製しない。
- 実装担当は、本書と Issue #35 の現行版を基準に作業する。
