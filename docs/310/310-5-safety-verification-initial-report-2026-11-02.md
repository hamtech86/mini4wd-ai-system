# 310-5 安全性検証 着手・一次調査報告 — 2026-11-02

## 1. 位置付け・権限
本書は310-5担当の着手確認および一次ソース調査結果であり、工程受入報告ではない。上位司令塔の指揮下で調査を継続する。仕様変更、既存PRのマージ、ファームウェア/Python実装変更、実機試験は本書によって許可されない。

実機安全ゲート `HARDWARE_CURRENT_LIMIT_CONFIRMED=false` を維持する。STOP ACK、PWM=0、CI成功を物理停止の証明として扱わない。

## 2. 参照HEAD・GitHub状態

| 対象 | 参照 | 状態 |
|---|---|---|
| 310-4設計 | PR #183 / `docs/310-4-design-v0.5` | Open / Draft / Unmerged |
| 310-4 HEAD | `291e8b17d31c2c4590986a4615f9454b9be666ce` | 4文書を含む |
| PR #183 base | `main` / `130e453ea3907f071209687a06c3e73535a8952d` | GitHub上のmain HEAD |
| 310-1 | PR #180 HEAD `5db3314ddf1efc2c068330ac333367662542ae5c` | Open / Draft / Unmerged |
| 310-2 | PR #181 HEAD `e10d06bd1c5baf16df253792483bc4902582fdba` | Open / Draft / Unmerged |
| 310-3 | PR #182 HEAD `d9e718b607a873759fffd58fc75bf950af499095` | Open / Draft / Unmerged |
| 310-5調査ブランチ | `safety/310-5-verification` | PR #183 HEADから作成 |

注意: PR #183はmainをbaseとしており、PR #180〜#182のDraft実装ブランチを統合していない。310-2/310-3コードはそれぞれのPR HEADを別参照として調査した。mainの実装状態とDraft積層ブランチの実装状態を同一視しない。

GitHub APIからブランチとファイルを参照した。ローカル作業ツリーの現在ブランチ、未コミット差分、ローカル実行環境の状態はこの接続から取得できないため未確認。

## 3. CI確認

### 310-4 HEAD
| Workflow | Run | Conclusion |
|---|---:|---|
| Break-in and Battery Tests | 41448444929 | success |
| DB Path Safety Phase 2 | 41448444816 | success |

両runはHEAD `291e8b17d31c2c4590986a4615f9454b9be666ce` に紐付く。Combined commit status APIはstatus entriesなし。Workflow runsは両方completed/success。

### 310-2 / 310-3 HEAD
| 対象 | Run | Jobs |
|---|---:|---|
| PR #181 HEAD `e10d06b...` | 41260941805 | test-battery / test-breakin / test-raw-log-and-sequence / test-full-suite: success |
| PR #182 HEAD `d9e718b...` | 41278191730 | test-battery / test-breakin / test-raw-log-and-sequence / test-full-suite: success |

CIは既存ソフトウェアテストの実行証拠であり、310-4のwire protocol、実機STOP、BOD/fuse、EEPROM電源断、ADC精度、SRAM/stack、host fsync性能の証明ではない。

## 4. 310-4設計文書の確認対象
1. `docs/310/310-4-design-v0.5.md` (blob `8d34271419f9cac21ac62989bf5e5100916ee453`)
2. `docs/310/310-4-decision-register-2026-11-02.md` (blob `3a5e1d890ed52c6bf5f0309de080c2315a45c9d6`)
3. `docs/310/310-4-implementation-acceptance-tests-2026-11-02.md` (blob `65423d102152125c939429e7e1eb87a539ad3085`)
4. `docs/310/310-4-final-review-report-2026-11-02.md` (blob `baf604f1651d1eea82ec711944f46fc0e04b05cc`)

4文書は設計・試験仕様の成果物であり、実装・試験完了を意味しない。PR #183はDraftのまま。310-5担当は文書記載を実機証拠と読み替えない。

## 5. 310-1〜310-3の契約・実装参照
- 310-1: A0/A1独立、A2/A3 reference only、A4/A5独立、ADC_SAMPLEは1変換1レコード、Pythonが31段階を管理、物理出力はACKから推定しない。RawLog v2 schema文書はPR #180 HEADを参照。
- 310-2: `raw_log_v2/storage.py` / `raw_log_v2/validator.py` をPR #181 HEADで確認。既存public packageはmanifest.json + records.jsonlの2ファイル契約。
- 310-3: `measurement_310/engine.py` / `measurement_310/transport.py` をPR #182 HEADで確認。wire codecは310-4に委ねられ、具体codecは未実装。Python controllerは31段階、10,000ms、ACK gated、send後のmonotonic起点を実装。
- mainの既存motor firmwareは `firmware/motor/MotoreRev.ino`、legacy CSV/line command/FW 3.03。310-4 COBS/CRC frame、ADC_BATCH、stage-context token、device epoch contractの実装と同一ではない。

## 6. 一次安全性所見

### 6.1 STOPのfsync依存 — FAIL（ソース確認）
PR #182 HEAD `measurement_310/engine.py` の `SequenceController.abort()` は、`send_stop()` より先に `_record_aborted_stage()` を呼ぶ。`_record_aborted_stage()` は `_append()` を呼び、PR #181 HEADのRawLog appendはファイル書込み後fsyncを行う。したがってSTOP要求が中断段階のRawLog追記/fsyncより後になる経路がコード上存在する。310-4の「STOPはfsync待ちにならない」契約に反する。
証拠種別: GitHub上のソースコード読取。動的fault-injectionは未実施。

### 6.2 STOP送信の同期ブロッキング — FAIL（ソース確認）
PR #182 HEAD `measurement_310/transport.py` の `PySerialTransport.send()` は同期 `write()` と `flush()` を実行する。SequenceController.abort()の `send_stop()` は同じtransport経路を通る。TX backpressure時のSTOP独立経路、bounded send deadline、lock/fsync非依存は確認できない。
既存mainの `communication/serial_manager.py` でも emergency_stop() は `_command_lock` 取得後にSTOP送信・ACK待ち・disconnectを行い、送信中ロック待ちを回避する独立経路は見当たらない。
証拠種別: ソース読取。通信mockでの遅延注入・実機STOPは未実施。

### 6.3 RawLog companion Evidence — FAIL（契約不整合の実装確認）
PR #181 HEADのRawLog v2 writer/validatorはpublic packageをmanifest.json + records.jsonlの2ファイルに限定する。一方、310-4はtransport-evidence-v1.jsonlをpackage root siblingとしてmanifest inventory/hash/countへ登録する要求を追加した。既存validatorが当該第三ファイルを受理する実装は確認できない。310-4文書自身の条件に従えば、現状でpackageをcomplete扱いしてはならない。RawLog v2 schema変更は310-1別承認事項であり、本工程で独断変更しない。
証拠種別: ソース読取。validator fixture実行は未実施。

### 6.4 310-4 wire protocol / firmware適合 — FAIL（未実装確認）
PR #182 transportはcodecを注入する抽象契約で、具体wire codecを持たない。mainのMotoreRev.inoはlegacy newline command/CSV firmwareであり、310-4のCOBS/CRC framing、session/device epoch、command correlation、STOP frame、ADC_BATCH、個別変換timestamp/statusの適合実装は確認できない。したがって現時点で310-4契約に対するfirmware適合PASSは出せない。
証拠種別: ソース読取。compile/target map/serial simulationは未実施。

### 6.5 PWM stage command correlation — FAIL（ソース確認）
PR #182 SequenceControllerはstage_context_idをPython内で生成するが、`send_pwm(index)` 呼出しにはPWM値のみを渡す。310-4のstage_context_tokenをPWM_SETへ載せ、ACK/sampleへ相関する実装は確認できない。ACK照合もPWM値中心で、310-4が要求するsession/epoch/command/contextの全照合を実装したcodecはない。
証拠種別: ソース読取。異常frame/late ACK試験は未実施。

### 6.6 STOP後の方向出力 / MCU異常 / 物理遮断 — BLOCKED
mainのMotoreRev.inoのstopMotor()はPWM=0とIN3/IN4 LOWを行い、STOPコマンド処理はARM tokenを無効化する。しかし、これはソフトウェアコードの動作であり、TX full時のlatency、MCU freeze/reset、driver enable inactive、独立hardware cutoffの証明ではない。実機試験は個別承認待ち。

### 6.7 EEPROM / BOD / Fuse / 電源監視 — BLOCKED
設計文書はATmega328P基準、16MHz時VCC条件、4.3V BOD単独不十分、external supervisor/hold-upを要求する。実搭載MCU marking/signature、基板版、supervisor部品型番/回路、fuse readback、VCC/hold-up実測の証拠は取得できていない。EEPROM書込み中の電源遮断、Fuse read/writeは未承認・未実施。

### 6.8 SRAM / Stack / RX-TX workspace — BLOCKED
実際の310-4対象FWの確定build flags/compiler/coreでのmap、.data+.bss、全buffer sizeof、worst-case stack watermark、heap使用量、194B RX/TX workspace ownershipの証拠がない。既存native harnessの存在やCI successを代用しない。コンパイル・map取得は実装対象/ビルド構成確定後に実施する。

### 6.9 ADC / acquisition loss — FAIL（未実装確認）
mainのlegacy firmwareはA0/A1/A4/A5等を周期読取してCSV化するが、310-4で定義した1変換1 ADC_SAMPLE、個別midpoint timestamp、sequence、status、0xFFFF unavailable、PRECONDITION_INVALID/CONVERSION_TIMEOUT/NOT_ACQUIRED、A0-A5ごとのloss accountingを実装した取得経路は確認できない。A2/A3の制御・品質判定禁止も新protocol経路で確認できない。
証拠種別: ソース読取。ADC入力注入・reference captureは未実施。

### 6.10 fsync性能 / deadline — BLOCKED
310-3はsend後にcommand_sent_nsを取得する順序を実装している。一方、対象host fingerprint、intent/evidence fsync分布、mean/p50/p95/p99/p99.9/max、D_STOP_reserve、10秒stage予算の実測値がない。STOP前にRawLog append/fsyncが発生する所見もある。ARM許可に必要な性能条件は未証明。

### 6.11 PWM 0..30 / 310秒シーケンス — FAIL（契約適合不足）
Python側に31段階・各10秒・ACK gate・monotonic timerは存在し、Arduino側の独立310秒シーケンサは確認されない。しかしstage_context_token/command correlation、異常時のSTOP独立性、後続段階未到達の証拠、保存失敗時のdurable stateが310-4契約全体を満たす証拠はない。したがって部分実装をPASSとしない。

## 7. 4.1〜4.7 一次判定

| 指示書区分 | 一次判定 | 理由 |
|---|---|---|
| 4.1 STOP/異常時 | FAIL | abortでRawLog fsync後にSTOP、STOP送信は同期write/flush。TX congestion・通信断の動的試験は未実施 |
| 4.2 電源/EEPROM/BOD | BLOCKED | 実機型番・fuse・外部監視回路・電源条件・電源断証拠なし |
| 4.3 SRAM/バッファ | BLOCKED | 対象FW build/map/stack/ownershipの実測なし |
| 4.4 ADC/品質 | FAIL | 310-4 ADC_SAMPLE/個別timestamp/status経路の実装を確認できない |
| 4.5 loss/RawLog | FAIL | channel/window loss accountingおよびcompanion Evidence package実装を確認できない |
| 4.6 Python/fsync | FAIL | STOPのfsync依存。host別latency/p99.9/maxとdeadline margin未取得 |
| 4.7 PWM 0..30 | FAIL | 31段階の骨格はあるが、310-4のstage-context/command correlationと安全契約が未充足 |

## 8. 着手時点の件数と進捗
- 主要検証区分: 7
- ソース/設計照合: 7/7
- 一次FAIL: 5区分（4.1, 4.4, 4.5, 4.6, 4.7）
- 一次BLOCKED: 2区分（4.2, 4.3）
- PASS: 0
- ローカル動的テスト: 0（この実行環境ではローカルcheckout/test runnerを確保できていない）
- CI: 310-4 HEADの2 workflows success、310-2/310-3 HEADの各4 jobs success（上記参照。310-4実装適合の証明ではない）
- コンパイル/map/stack: 未実施
- ハードウェア試験: 未承認・未実施
- 実装差分: なし

「ソース照合7/7」は調査完了数であり、工程進捗率や安全合格率ではない。PASS率は0/7。

## 9. 310-5継続計画
1. PR #183のT01–T18全項目を4.1–4.7へ分解し、各テストのfixture、期待値、証拠保存先を対応付ける。
2. PR #181/#182の対象テスト一覧とworkflowを照合し、CIで実際に実行されている試験と未実装の試験を分離する。
3. STOP先行性を保つため、abort時のRawLog/fsync/STOP順序をdeterministic fake transport + injected blocking writerで再現するテスト仕様を作成する。仕様変更を伴わない修正範囲か、先に司令塔判断を要するかを区別する。
4. transport-evidence-v1と既存2-file RawLog packageの整合について、310-1 schema authorityの判断が必要なため変更せず保留する。
5. wire codec/FW実装は310-4の実装許可が必要。承認前にコードを変更しない。
6. MCU/fuse/supervisor/EEPROM/ADC/STOP/310秒/電流制限に関する実機試験申請を準備するが、明示承認前は実行しない。
7. 可能なhost-only試験環境と実行権限を確保し、試験結果・ログ・hashを追記する。

## 10. 未解決事項・司令塔判断を要する点
1. STOPの最優先性: 現状のabort順序はRawLog append/fsyncの後にSTOP送信。設計契約に反するため、修正方針と実装許可が必要。
2. RawLog companion artifact: 310-1/310-2の2-file package contractと310-4のthird sibling artifact inventory要求の整合が必要。310-5担当がschemaを変更してはならない。
3. 310-4具体codec/FW実装: 現状未実装。実装担当・実装許可・対象HEADを明示する必要がある。
4. 310-4設計の前提: 本指示書が「310-4で確定した設計契約」を明示しているため、310-5検証の基準契約として扱う。PR #183のDraft/Open/UnmergedはGitHub上の公開・マージ状態であり、上位司令塔による工程指示の効力を覆すものではない。PR #183をマージしたとは扱わない。
5. hardware current limit / independent cutoff: falseのまま。物理保護の証明がない状態で通電試験を行わない。

## 11. 結論
310-5の着手確認と設計/実装の一次照合を実施した。CI成功は確認したが、310-4契約に対する実装適合PASSは0件。STOPのfsync依存など、コード読取で確認したFAILが存在する。電源/EEPROMおよびSRAM/stackはBLOCKED。実機試験・通電・310秒測定は未承認・未実施。

本書は一次調査報告であり、310-5完了審査申請ではない。上位司令塔の判断を待つ論点を提出しつつ、判断不要なhost-only検証準備と証拠整理は継続する。


## 12. 既存テストのカバレッジ照合（追加調査）

GitHub上でテストソースを取得し、テスト関数の定義と310-4試験要求を照合した。ここでの件数はソース中の `test_*` 定義数であり、同一CI runで実行された総数を意味しない。

| テストファイル | 参照HEAD | 定義数 | 主な対象 |
|---|---|---:|---|
| `tests/test_measurement_310.py` | PR #182 HEAD `d9e718b...` | 24 | ACK gate、31段階、RawLog append失敗、fragmented ACK、send/ACK timing |
| `tests/test_raw_log_v2.py` | PR #181 HEAD `e10d06b...` | 22 | append-only、crash recovery、manifest commit、schema、package closure |
| `tests/test_serial_emergency_stop.py` | main `130e453...` | 18 | legacy serial manager/controllerのARM/STOP/lock競合 |
| `tests/test_firmware_safety_native.py` | main `130e453...` | 1 | native C++ harnessでlegacy FW STOP/PWM/direction/ARM state |

### 12.1 STOPの既存テストは独立性を証明していない
`tests/test_serial_emergency_stop.py::test_emergency_stop_serializes_with_an_in_flight_positive_pwm_write` は、positive PWM writeが完了してからSTOPが送信されることを期待している。これは既存実装のwrite直列化を確認するテストであり、TX writeが永久にblockされた場合にもSTOPが独立して出せることを証明しない。
`test_stop_request_event_is_set_before_lock_wait` はSTOP request eventをlock待ち前にセットすることを確認する一方、実際のSTOP worker完了はlock解放後である。request latchとSTOP出力実行を区別する必要がある。

### 12.2 RawLog companion artifactとの衝突を既存テストが固定
`tests/test_raw_log_v2.py::test_normal_finalize_publishes_exactly_two_files` は完成パッケージがmanifest.json + records.jsonlの2ファイルだけであることをassertする。`test_final_package_rejects_unexpected_files_without_deleting_work` はunexpected fileを含むpackageを拒否する。したがって310-4が要求するtransport-evidence-v1.jsonlを同じpackageへ加える場合、現行310-2実装/テスト契約のままでは通らない。これは310-1 schema authorityを含む明示的な整合判断が必要であり、310-5側で勝手に変更しない。

### 12.3 310-3既存試験で確認できる範囲
`tests/test_measurement_310.py` はACK timeout、mismatch、RawLog append failure、ACK/non-ACK分離、fragmented/coalesced frame、send後のmonotonic timestamp起点などを扱う。一方、STOP要求からsend_stopまでに中断stage append/fsyncが先行しないことを検証する専用テストは確認できない。また具体310-4 codecを通じたcommand_id/session/epoch/context一致、ADC_BATCH decode、T01/T02/T03のdevice epoch/session collision、T09 TX full STOP、T17 companion package、T18 host fsync p99.9/maxは未カバー。

### 12.4 CIとテスト実行証拠の境界
PR #181/#182で該当workflow jobsがsuccessであることはGitHub Actionsのrun/job metadataから確認した。ただし本調査環境から `git clone` を試みたところ、DNSでgithub.comを解決できずローカルpytest/native harnessを実行できなかった。CIのsuccessは保持するが、未確認のテスト件数・個々のテスト実行ログを推定しない。


## 13. 310-5提出状態・追加CI確認（2026-11-02）

- 310-5 PR: #184
- URL: https://github.com/hamtech86/mini4wd-ai-system/pull/184
- Branch: `safety/310-5-verification`
- 最新提出HEAD（追加試験一覧を含む）: `da930a1a4ff8ca8dfeffdd5a0ee0a9da10e97a67`
- Base: `docs/310-4-design-v0.5` / PR #183 HEAD `291e8b17d31c2c4590986a4615f9454b9be666ce`
- PR状態: Open / Draft / Unmerged
- 変更ファイル: 2（本報告書、37項目の試験一覧）。Python/FW変更なし。

PR #184で起動したGitHub Actions run `41450041113` はcompleted/success。4 jobs（test-full-suite、test-battery、test-raw-log-and-sequence、test-breakin）がsuccess。runの固定head_shaは `7e63aca7770e637aea993f0a00541e13030a4a2a` であり、最新HEAD `da930a1...` より前（試験一覧文書追加前）のcommitである。差分は文書追加のみでコード変更なし。最新文書HEADに対する別runは取得できていないため、run SHAを最新HEADと同一視しない。

37項目の一覧集計:
- PASS: 4（限定ソフトウェア範囲）
- FAIL: 10
- BLOCKED: 19
- NOT RUN: 4

ローカルclone試行は `Could not resolve host: github.com` で失敗。ローカルpytest/native harnessは未実施。CI成功はGitHub Actionsの証拠として保持するが、実機安全性・310-4 wire protocol適合のPASSには転用しない。
