# 310-5 安全性試験一覧 — 2026-11-02

**対象:** 310-4 v0.5契約 / PR #183 HEAD `291e8b17d31c2c4590986a4615f9454b9be666ce`  
**実装参照:** PR #181 HEAD `e10d06bd1c5baf16df253792483bc4902582fdba`、PR #182 HEAD `d9e718b607a873759fffd58fc75bf950af499095`、legacy main `130e453ea3907f071209687a06c3e73535a8952d`  
**状態:** 試験計画・初期判定。実機試験は未承認。PASSは限定された既存ソフトウェア範囲にのみ適用する。

| ID | 310-5要求 / 試験 | 方法・証拠 | 初期判定 | 未実施・制約 |
|---|---|---|---|---|
| S01 | STOP latch後、ログ保存より先にSTOP送信 | SequenceController.abort→_record_aborted_stage→_append/fsync→send_stopのソース順 | **FAIL** | STOPがfsyncより後。修正後の回帰試験が必要 |
| S02 | TX write/flushが停止してもSTOPを送れる | PySerialTransport.sendの同期write/flushをblocking fakeで保持しSTOP注入 | **FAIL** | 独立STOP経路・bounded timeoutなし |
| S03 | Writer/command lock待ちがSTOPを妨げない | lock保持中にSTOP要求、request latchと実際の送信開始を別々に計測 | **FAIL** | legacy serial managerは同じcommand lockを待つ。現行テストもin-flight write後のSTOPを期待 |
| S04 | 通信断・ACK timeout・遅延/重複ACK | deterministic transport/clockで全パターン注入 | **NOT RUN** | 既存テストはtimeout/mismatchの一部のみ。310-4 codec未実装 |
| S05 | 不正フレーム・CRC・COBS・session/epoch不一致 | 310-4 concrete codecに対するfuzz/boundary vectors | **BLOCKED** | concrete codecなし |
| S06 | Python例外・プロセス停止 | 各状態で例外/killしwork areaとSTOP結果を検証 | **NOT RUN** | process crash matrix未実施 |
| S07 | RawLog append/fsync失敗時に測定継続しない | writer fault injection、後続append count・PWM send countを検査 | **NOT RUN** | append failure testsは存在。fsync遅延・STOP先行性の試験はない |
| S08 | MCU freeze/reset時の独立driver cutoff | reset/freeze注入とenable/power stage波形 | **BLOCKED** | 実機承認・独立cutoff仕様/測定なし |
| P01 | 実搭載MCU・基板・clock同定 | chip marking/signature、board revision、clock測定 | **BLOCKED** | ATmega328Pは設計baselineのみ |
| P02 | BOD fuse設定・readback | fuse bytes read-only取得、datasheet条件照合 | **BLOCKED** | Fuse read/writeは個別承認が必要 |
| P03 | 外部supervisor/hold-up回路 | schematic、部品型番、実装確認、threshold/hold-up測定 | **BLOCKED** | 外部監視回路の実装証拠なし |
| P04 | 低電圧時PWM/ARM停止 | supervisor thresholdを模擬/実測しPWM/ARM禁止を検証 | **BLOCKED** | 意図的電圧低下試験は未承認 |
| P05 | EEPROM各write境界で電源断 | invalidate/payload/CRC/readback/marker各点で断電 | **BLOCKED** | 電源遮断試験未承認 |
| P06 | EEPROM 36,600 boot events耐久予算 | per-slot/per-cell write counterとdatasheet条件照合 | **BLOCKED** | 実装counter・対象chip条件・寿命証拠なし |
| P07 | 電源復帰後に自動再ARMしない | reboot/invalid journal/unknown identity後の状態遷移 | **BLOCKED** | boot identity実装・実機証拠なし |
| M01 | .data+.bss ≤900B | 対象FW exact toolchainのlinker map/avr-size | **BLOCKED** | 310-4対象FW/build未確定 |
| M02 | stack ≤700B、reserve ≥448B | worst nested path stack watermark/high-water | **BLOCKED** | map/stack測定なし |
| M03 | RX/TX workspace各194B・所有権 | sizeof/ownership state machine/overflow injection | **BLOCKED** | 310-4 frame/buffer実装なし |
| M04 | TX_OWNED中不変・追加queue禁止・counter saturation | max frame/continuous TX/overflow/wrap fixtures | **BLOCKED** | 対象実装・fixtureなし |
| A01 | A0/A1独立、A2/A3 reference only、A4/A5独立 | schema channel mapとFW mappingの照合 | **FAIL** | RawLog schema mapは存在するが310-4 firmware acquisition path未実装 |
| A02 | 1変換1 ADC_SAMPLE・個別timestamp/sequence | channel-switch/cadence fixtureとsample count照合 | **FAIL** | legacy CSV loggerは契約上のADC_SAMPLE単位ではない |
| A03 | raw 0正常、unavailable=0xFFFF、欠損を代用しない | 0/1023/0xFFFF/未取得 fixture | **BLOCKED** | 310-4 ADC record pathなし |
| A04 | PRECONDITION_INVALID / CONVERSION_TIMEOUT / NOT_ACQUIRED | bounded acquisition routine fault injection | **BLOCKED** | analogRead bounded timeout実装なし。存在しない保証を仮定しない |
| A05 | A2/A3を制御/STOP/品質判定に使わない | call graph + injected A2/A3 extremes | **BLOCKED** | 新しい制御経路未実装 |
| L01 | 1,000,000µs半開window×channel loss accounting | exact-boundary synthetic schedule vectors | **FAIL** | channel/window expected/attempted/valid/invalid/missing実装なし |
| L02 | missing=expected−attempted、未知損失UNATTRIBUTABLE | channel-unknown/interval-unknown/batch loss vectors | **FAIL** | loss ledger未実装 |
| L03 | batch/sample二重計上禁止・訂正append-only | duplicate/drop/correction vectors | **BLOCKED** | transport Evidence ledgerなし |
| L04 | transport-evidence sibling + manifest inventory/hash/count | package fixtureにrecords/evidence/manifestを生成し実hash比較 | **FAIL** | 現行310-2 writerは2-file packageのみ。既存testが第三ファイル拒否を固定 |
| L05 | incomplete packageをcompleteにしない・original preservation | crash/torn-tail/recovery retry/hash validation | **PASS (限定)** | 310-2既存recoveryテスト/CIのみ。companion Evidence追加後の挙動は未確認 |
| Y01 | command_sent_nsはwrite/flush完了後 | blocking send clock injection、ACK timeout起点比較 | **PASS (限定)** | 310-3 source/testに対応あり。実対象310-4 codec未統合 |
| Y02 | ACKはcommand/session/epoch/contextと一致 | wrong/late/duplicate ACKとtoken collision | **FAIL** | 現行SequenceControllerはPWM値中心、codec/全識別子相関なし |
| Y03 | fsync前にnonzero command送信しない | _begin_stage()の送信前処理とRawLog append位置をソース照合 | **FAIL** | _begin_stage()はsend_pwm(index)を先に実行し、durable TX intent/Evidence appendを確認できない。ACK後のSESSION_EVENTは送信後記録であり代替にならない |
| Y04 | fsync p99.9/max + margin < 10秒−STOP reserve | target host/storage fingerprintごと≥10,000 samples、分布/最大/合算評価 | **BLOCKED** | 実host測定なし |
| Y05 | 不明command outcomeを安易に再送しない | partial write/flush timeout/late ACK recovery | **NOT RUN** | retry/reconciliation test未実施 |
| W01 | Python管理PWM0..30、各10,000ms、全31段階 | injected clock/ACK、stage count/order/duration | **PASS (限定)** | 310-3 engine unit tests/CI。実機時間精度は未確認 |
| W02 | 異常時に後続stageへ自動進行しない | mismatch/timeout/storage fault時のsent PWM sequence | **PASS (限定)** | 既存310-3 unit test/CI。310-4 command correlationは別途FAIL |
| W03 | PWM command/applied値を区別し、stage contextを相関 | command_id/context token/ACK/sample mapping fixtures | **FAIL** | stage_context_idはPython内生成だがsend_pwmへ渡されない。wire token/codecなし |

## 実施証拠の区分
- **CI metadata:** PR #183の2 workflows success、PR #181/#182のtest jobs success。CI runはコードの当該HEADに紐付く。
- **テストソース確認:** 310-3 24 test functions、310-2 22、legacy STOP 18、native FW harness 1をソース上で確認。これらの合計を同一run実行件数とは扱わない。
- **ローカル実行:** git cloneはDNSでgithub.com解決失敗。pytest/native harnessは未実施。
- **コンパイル/map/stack:** 未実施。
- **実機:** 未承認・未実施。

## 判定の読み方
- FAILはソースまたは既存テスト契約から要求不適合/契約不整合を確認したもの。
- BLOCKEDは対象実装・実機情報・権限等が不足して実施できないもの。
- NOT RUNは試験を定義できるが、まだ実施していないもの。
- PASS (限定)は指定した既存ソフトウェア単体の範囲のみ。310-4全体の受入PASSではない。
- 本一覧のいずれも実機安全性を証明しない。HARDWARE_CURRENT_LIMIT_CONFIRMED=falseを維持する。


## 2026-11-03 host regression follow-up (PR #185 / #186)

This supplement updates the execution evidence without changing the initial matrix classifications into whole-system PASS claims.

| Matrix row | Follow-up evidence | Updated interpretation |
|---|---|---|
| S01 — STOP-before-log | PR #185 changes the host abort order to attempt STOP before appending the aborted-stage record. Its host regressions cover STOP-before-append, STOP while append stalls, and STOP-send failure; CI run `41462228503` passed (RawLog/sequence 38, full suite 313, break-in 19, battery 9). | The Python call order is improved and covered. **Not a safety PASS**: STOP still uses the shared synchronous UART transport; send attempt is not proof of delivery or physical stop. |
| S04 — timeout / delayed / duplicate ACK | PR #186 tests invalid ACK domain values, invalid codec consumed lengths, receive failure, STOP send failure, disconnect state clearing, delayed prior-stage ACK after next PWM, and late ACK after timeout. CI run `41538695288` passed: RawLog/sequence 38, full suite 326, break-in 19, battery 9. | Host regression coverage is expanded. Session identity, device epoch/boot identity, reconnect stale-frame binding, and the complete 310-4 codec contract remain unproven. |
| Y02 — ACK correlation | Same PR #186 tests above. | Retain **FAIL** for the full 310-4 requirement: host-only PWM correlation tests do not implement/prove session+epoch+context binding. |
| Y03 — durable intent before nonzero PWM | No change in PR #185/#186. | Retain **FAIL**. A durable intent append+fsync before send is absent; post-ACK event is not a substitute. |
| S02/S03 — independent bounded STOP path | No change in PR #185/#186. | Retain **FAIL**. Shared synchronous write/flush and command-lock behavior remain; no bounded independent STOP transport is established. |
| L04 — transport Evidence artifact / manifest | No RawLog v2 package contract change authorized or made. | Retain **FAIL / contract mismatch**. Do not add a third package artifact or change manifest rules without the design authority resolving the relationship. |

Evidence links:
- PR #185: https://github.com/hamtech86/mini4wd-ai-system/pull/185
- PR #186: https://github.com/hamtech86/mini4wd-ai-system/pull/186
- PR #185 CI: `41462228503`
- PR #186 CI: `41538695288`

All evidence above is host-side software/CI only. No firmware compile, serial communication, physical energization, Fuse/ISP operation, EEPROM power interruption, ADC injection, or 310-second hardware measurement was performed. `HARDWARE_CURRENT_LIMIT_CONFIRMED=false` remains in force. This supplement is not a 310-5 completion report, acceptance request, or authorization to proceed to 310-6.


## 2026-11-03 source-level transport / sequencing audit

Reviewed the actual host implementation at the 310-3 base referenced by PR #185/#186 (commit d9e718b607a873759fffd58fc75bf950af499095), rather than relying only on test summaries.

| File / method | Direct source observation | Safety interpretation |
|---|---|---|
| `measurement_310/engine.py::SequenceController._begin_stage` | Calls `self.send_pwm(index)` and only afterwards captures `command_sent_ns`. There is no pre-send TX-intent append/fsync in this method or in the shown start path before the first call. | Y03 remains **FAIL**. The subsequent ACK event cannot establish a durable record before actuation. |
| `measurement_310/engine.py::SequenceController.abort` at base HEAD | Original base order records the aborted stage (which appends through the RawLog session) before calling `send_stop()`. PR #185 changes this order in its branch and adds host tests. | Base source confirms the defect; PR #185 is a narrowly scoped ordering improvement only. It does not prove delivery or physical stopping. |
| `measurement_310/transport.py::PySerialTransport.__init__ / connect` | Constructor accepts port, baudrate and read timeout only. `serial.Serial(..., timeout=self.timeout_s)` is opened without an explicit `write_timeout`. | A finite read timeout does not bound write/flush. S02 remains **FAIL**. |
| `measurement_310/transport.py::PySerialTransport.send` | Calls synchronous `write(payload)`, then `flush()`; no independent STOP channel or bounded STOP deadline is present in this transport. `ProtocolClient.send_stop()` delegates to the same `transport.send()` used for PWM. | A blocked write/flush can prevent STOP from reaching the transport call. S02 remains **FAIL**; host ordering in PR #185 does not change this. |
| `measurement_310/transport.py::ProtocolClient.disconnect` | Clears receive buffer, pending messages and pending ACKs. | Useful local cleanup, but not a device-session/boot-epoch identity mechanism. Y02 remains **FAIL** for session/epoch/context correlation. |
| `measurement_310/engine.py::SequenceController` ACK handling | The controller accepts a two-field `(pwm, ack_utc)` result and compares the PWM value with `stage_index`. | This does not bind ACK to a command ID, measurement session, device boot epoch, or transmitted stage context. Y02 remains **FAIL**. |

### Audit boundaries

- The source audit is static inspection of host Python at the stated commit; it is not a runtime timing test.
- PR #185/#186 are separate Draft PRs. Their CI results do not change the inspected base source unless those changes are integrated.
- No firmware source/build, serial device, board, driver, or physical STOP behavior was exercised.
- No RawLog v2 schema or 310-4 acceptance document was changed.
- This audit does not authorize a code change, merge, hardware operation, or stage transition.


## 2026-11-03 firmware-evidence boundary review

The accepted 310-4 design/acceptance documents define firmware obligations, but the reviewed 310-4 acceptance PR #183 changes only four documentation files (design, decision register, final review report, and acceptance-test specification). It contains no firmware implementation change. This is a scope observation about PR #183, not a claim that no firmware exists anywhere in the repository.

The current evidence package still contains no exact 310-4 firmware build identity, pinned compiler/core/build flags, linker map, `avr-size` output, per-structure `sizeof` inventory, stack watermark, ADC acquisition trace, or TX-congestion STOP scheduler trace. Accordingly:

| Acceptance item | Evidence required by accepted 310-4 contract | 310-5 disposition |
|---|---|---|
| T14 / M01–M04 — SRAM and ownership | Exact target build + map/size + UART ring accounting + structure sizes + worst-path stack watermark + ownership/overflow traces | **BLOCKED / NOT RUN** — no attributable build/map/stack or runtime trace in the reviewed evidence. Numeric budgets remain requirements, not measured results. |
| T15 / S08 — STOP under TX congestion and MCU fault | Deterministic simulator trace for TX full/TX_OWNED/partial frame/ADC assembly; bounded STOP latch latency; no nonzero PWM after latch; separate hardware cutoff evidence for MCU freeze/reset | **BLOCKED / NOT RUN** — no simulator trace or independent cutoff evidence. Host STOP-before-log tests do not satisfy this firmware test. |
| T16 / A01–A05 — ADC acquisition | Exact sensor/front-end/VREF identity, bounded acquisition implementation, one-conversion/one-sample trace, per-channel timestamps/sequences, failure-state fixtures, reference uncertainty analysis | **BLOCKED / NOT RUN** — no attributable firmware acquisition trace or approved reference dataset. Existing host schema tests do not establish ADC behavior or accuracy. |
| T17 / L01–L04 — loss and companion package | Implemented per-channel/window loss ledger and transport-evidence sibling with manifest inventory/hash/count roundtrip | **FAIL / NOT RUN** — L04 contract mismatch remains FAIL; other implementation evidence absent. No schema or manifest change is authorized here. |

### Required next evidence (software-only first)
1. Identify the exact firmware source path, branch/commit, board target, compiler/core versions, and build flags intended to implement the accepted 310-4 contract.
2. Produce a reproducible non-hardware build and linker map/size report; enumerate all static buffers and UART core rings; then obtain a worst-case stack watermark using an approved simulator/test harness.
3. Provide deterministic firmware-level simulator traces for TX congestion + STOP, ADC channel sequencing/failure states, and loss accounting. Keep physical cutoff, reference-instrument accuracy, fuse, EEPROM power interruption, and energized board tests outside this work until separately authorized.

No source implementation was changed in this review. No firmware compilation or hardware operation was performed. These rows are not PASS, and this review does not authorize implementation, merge, energization, or 310-6.
