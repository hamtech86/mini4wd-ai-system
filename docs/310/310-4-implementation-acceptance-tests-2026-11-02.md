# 310-4 実装後受入試験仕様 — 2026-11-02

**状態:** 試験設計完成。未実施。実装・実機試験の許可ではない。  
**共通ルール:** 試験は原則host-side deterministic fault injection / simulatorから開始。物理EEPROM電源断、ADC参照測定、実ボードSTOP等は個別の実機承認後のみ。RawLog v2 schemaは変更しない。

各試験は、試験ID、ビルド/設定、入力fixture、操作ログ、期待結果、実際の結果、証跡SHA-256を保存する。未実施はPASS扱いしない。

## T01 Session tag allocator

**前提:** 一時ファイルシステム、固定namespace、既知high-water、fault injection可能なallocator。  
**操作:** (a) allocation commit直後/HELLO前にprocess kill、(b) write/fsync/rename/dir-fsync各境界でkill、(c) journal欠落・CRC破損・truncation・古いbackup復元・namespace不一致、(d) 最終tagとexhaustion、(e) 並行allocation。  
**期待:** commit済tagは消費済み。commit不明は再利用せずfail-closed。壊れた/rollback疑いjournalではHELLO禁止。tagは1..0xFFFFFFFE、wrapなし。  
**合格:** 全実行でtag重複ゼロ。状態を証明できない全ケースで新規session開始を拒否。各クラッシュ点の再起動後journalが検証可能。  
**証跡:** allocator journal前後、fault injection trace、割当一覧、再起動ログ、hash。

## T02 Device sequence rollover / duplicate / gap

**前提:** 固定full device_epoch_id、wire uint16 sequence generator、RawLog v2 validator。  
**操作:** 65534,65535,0,1; exact duplicate; 同sequence異payload; gap; modular delta 32767/32768; delta 0; wrap前後でhost restart。  
**期待:** 正常wrapはextended sequence連続増加。完全一致duplicateはdeduplicate。競合duplicateと32768以上の曖昧deltaはunresolved。gapは記録し、欠損ADC_SAMPLEを合成しない。  
**合格:** 採用sampleのRawLog device_sample_sequenceはfull epoch内でstrictly increasing。RawLog schema/type unchanged。unresolvedはpackage incomplete。  
**証跡:** 入力frame、extended sequence table、Evidence loss/gap records、RawLog validator出力。

## T03 boot epoch / checkpoint consistency

**前提:** 異なるfull boot_id64、同一low32 tagを持つfixtureを用意。  
**操作:** checkpoint commit前後のcrash、欠落/破損checkpoint、同一epochのHELLO/ARM/STOP/session change、真のreboot、low32 tag collision。  
**期待:** sequence stateはfull epoch IDで分離。session境界ではresetしない。異なるfull boot IDでのみ新epoch。checkpoint不明なら関連sample unresolved。  
**合格:** low32衝突でepoch誤結合ゼロ。復旧時にsequenceを推測rebasingしない。  
**証跡:** handshake frame、full identity mapping、checkpoint bytes/hash、recovery report。

## T04 TX partial write / ACK delay / missing / late ACK

**前提:** deterministic serial mock、frame codec、clock injection。  
**操作:** serial write 0 byte/partial/exception、ACK delay、ACK loss、duplicate ACK、wrong command_id/context/session/epoch/type、STOP後の古いACK、deadline後ACK。  
**期待:** intentをdurable commitしてからwrite。partialはtx_error。ACK exact match以外はstage進行不可。timeoutはoutcome unknown。late ACKでstage startを遡及設定しない。STOP優先。  
**合格:** no false applied stage、no stage advance without matching durable ACK、old ACK cannot authorize new stage.  
**証跡:** TX intent/complete/error、raw RX bytes、ACK-match outcomes、host monotonic trace。

## T05 fsync failure / latency / crash

**前提:** injectable evidence writer and storage latency simulator.  
**操作:** intent fsync failure、RX evidence fsync failure、completion fsync failure、manifest/index fsync failure、fsync latency crossing stage deadline、crash at every boundary、torn final line。  
**期待:** intent未commitならcommand bytes未送信。evidence failure後nonzero PWM禁止。transport usableならSTOP attempt。no fabricated/backdated timestamp。package incomplete。original evidence bytes preserved.  
**合格:** failure後nonzero command count=0; incomplete classification exact; no original artifact rewrite; recoverable events hash-verified.  
**証跡:** injected failure matrix、disk event trace、original/recovery hashes、package validator.

## T06 EEPROM power interruption / commit atomicity

**前提:** exact MCU and EEPROM datasheet; journal emulator first. Physical power interruption only after separate hardware authorization.  
**操作:** marker invalidation中、payload各byte、CRC各byte、readback、marker commit前後、brownout/reset loopで電源断。  
**期待:** 起動時に前世代または新世代の完全valid recordのみ選択。部分record選択なし。identity invalid時BOOT_ID_INVALID。retry loopで書込みを浪費しない。  
**合格:** 全interrupt pointでpartial identity acceptance=0。36,600 boot-event budgetのslot write countとdatasheet条件が整合。BOD/fuse/supplyは実物証跡で一致。  
**証跡:** MCU marking、fuse dump、datasheet revision/conditions、power waveform、journal dump before/after、reset log。

## T07 ADC cadence / 20 Hz qualification

**前提:** exact ACS712 variant, PWM frequency, analog front-end schematic/filter response, predeclared threshold statistic and error limits.  
**操作:** candidate schedule T/T+25ms/T+100ms repeated; record per-channel timestamp deltas across at least 10 periods. Separately authorized high-rate reference acquisition at controlled phases; include channel-switch/stage settling, PWM phase, threshold-near points and all relevant PWM values.  
**期待:** raw conversion order and individual midpoint timestamps correct; same-channel intervals alternate 25ms and 75ms. Report long-run average as 20 conversions/s/channel only, never uniform 20Hz. Compare candidate statistic to reference. Cadence adopted only if predeclared bias/variance/false-positive/false-negative/uncertainty criteria pass.  
**合格:** 25/75ms pattern and bounded timing deviations match the approved schedule. No cadence is approved by this test alone; non-uniform aliasing/settling must remain within pre-approved bounds in the reference comparison. Otherwise reject the candidate and propose a revised cadence/filter.  
**証跡:** instrument calibration, reference raw capture, filter transfer data, timing traces, analysis notebook/report.

## T08 SRAM and stack maximum

**前提:** pinned Arduino core/compiler/library versions and exact build flags.  
**操作:** sizeof every structure/buffer, linker map, HardwareSerial ring allocation, stack watermark under worst nested parser/CRC/COBS/STOP/TX, heap instrumentation, max buffer occupancy.  
**期待:** all allocations bounded; no dynamic String/heap in critical path; stack reserve and safety margin preserved.  
**合格:** static usage + worst stack <= 2,048 bytes with approved margin; no stack/heap collision; no overflow; one in-place TX frame assumption confirmed or design returned.  
**証跡:** compiler version, build output, map, sizeof table, stack watermark logs, heap instrumentation.

## T09 STOP under TX blockage

**前提:** simulated UART TX full/permanently backpressured; RX STOP path active; separate physical test requires approval.  
**操作:** STOP arrives during ADC batch assembly, while TX owns partial frame, and while UART availableForWrite=0; repeat with RX/TX bursts and full loss counters/history.  
**期待:** software output-zero request and STOP latch do not wait for TX drain or batch completion. No buffer overwrite/interleaving. STOP_ACK waits until current atomic frame boundary if single workspace, then highest priority.  
**合格:** STOP state transition bounded by approved loop-service deadline independent of TX drain; no nonzero PWM after STOP_LATCHED; physical stop not inferred from ACK.  
**証跡:** scheduler trace, pin/output-state simulation, ownership transitions, max STOP latency, queue high-water.

## T10 RawLog / Evidence / checkpoint / manifest closure

**前提:** fixture package with known record and event counts and hashes.  
**操作:** remove/alter each artifact in turn; change one byte; remove ACK link; remove checkpoint; truncate Evidence tail; omit backup; restore from backup; crash during manifest-last publication.  
**期待:** only fully verified package is complete. Any missing/altered artifact, unaccounted sequence gap, missing channel-window loss entry or unverified backup => incomplete/evidence_incomplete. 310-2 originals preserved; no synthesized samples/stages.  
**合格:** all valid fixtures pass exact hash/count/correlation validation; every corruption fixture fails closed and preserves originals. Backup restore yields byte-identical verified artifacts.  
**証跡:** manifest, SHA-256 list, record/event counts, recovery_record, backup restore log, validator output.

## T11 Channel/time-window loss accounting

**前提:** deterministic sample generator with injected losses for each channel and time window.  
**操作:** lose attempted conversion, fail conversion, overflow buffer, discard batch, drop RX byte range, fail Evidence fsync.  
**期待:** loss classes remain distinct; each identifiable loss increments correct channel/window count; unidentifiable range explicitly unresolved; no silent loss.  
**合格:** injected known losses exactly equal recorded counts by channel/window; aggregate counter reconciles where applicable; unknown loss marks package incomplete.  
**証跡:** source generator truth table, Evidence loss records, reconciliation report.

## T12 310-3 compatibility regression

**前提:** accepted 310-3 engine/transport contract and mock clock/transport.  
**操作:** verify ACK-gated stage start, previous-stage end at next command send, no advance on missing/mismatched ACK, STOP attempt, append failure write-disabled state, fragmented/multiple frame decode.  
**期待:** Python owns all 31 stages; monotonic host timing unchanged; no physical-state claim from ACK/send; existing RawLog v2 package semantics unchanged.  
**合格:** existing 310-3 tests pass unchanged or changes are separately reviewed; no RawLog schema delta; no new FW scheduler.  
**証跡:** test report, commit IDs, raw mock traces, schema diff.

## Overall gate

All T01–T12 must be individually reported PASS/FAIL/BLOCKED with evidence references. BLOCKED is not PASS. T06 and physical portions of T07/T09 require separate hardware authorization. No CI-only result can satisfy physical safety or measurement qualification.


## 最終完遂指示対応 — 追加受入試験（すべて未実施）

### T13 EEPROM耐久・電源完全性
前提: 実chip marking/signature、datasheet revision、board revision、fuse dump、温度/電圧範囲、external supervisor/hold-up設計の承認。操作: 36,600 events slot rotation modelとper-cell counter照合。全温度/電源公差/負荷stepでsupervisor threshold測定。各byte write境界でpower interruption注入しVCC waveformを記録。期待: marker≤4,576/cell、payload≤2,288/cell、aggregate marker=73,200。16MHz動作中VCC≥4.5V。power-failで新規commit抑止、既開始writeはhold-up内完了、曖昧journalはBOOT_ID_INVALID。合格: supervisor falling threshold min≥4.5V across specified tolerance/temp、hold-upは実測worst-case write completion+marginを満たす、partial record valid acceptance=0。満たせない場合EEPROM-only設計FAIL。証跡: marking/signature、fuse、scope waveform、temp/voltage sweep、journal dump、counter report。

### T14 SRAM/map/stack
前提: compiler/core/library/build flags固定、実装は別承認後。操作: linker map/avr-size、全構造体・buffer sizeof、HardwareSerial ring、worst nested parser/CRC/COBS/ADC/TX/STOP/ISR stack watermark、heap instrumentation。期待: static≤650B、stack≤384B、protected reserve≥256B、frame≤194B、RX≤40B、TX single workspace≤194B、critical pathにString/new/mallocなし。合格: 全上限同時達成、overflow/heap-stack collision/TX overwriteなし。上限超過はFAIL。証跡: map、symbols、sizeof、stack trace、heap trace、call graph。

### T15 TX congestion中STOPとMCU fault
前提: deterministic mock/simulator。実機は別の書面許可とindependent cutoff必須。操作: TX full、TX_OWNED、ADC batch assembly、RX burst、全stateでSTOP注入。別途MCU reset/freezeとdriver-enable/pull-down/cutoff観測。期待: STOP latch first、PWM0、direction LOW、ARM invalidation、STOP_LATCHED。UART drain/availableForWrite/ACKを待たない。TX frameは非interleaveでframe boundaryまでよいがoutput actionを遅らせない。MCU fault時は外部回路がdriver inactiveにする。合格: software transitionは事前承認bounded loop-service deadline内、latch後nonzero PWMなし。physical safetyはindependent driver-disable測定のみで判定。ACK単独はPASS根拠でない。証跡: scheduler/pin/enable waveform、TX occupancy、reset/freeze injection、driver/cutoff report。

### T16 ADC精度・低周波統計
前提: exact ACS712 suffix/vendor datasheet、schematic/filter、VREF/AVCC測定、traceable calibrated reference、statistic/window/settling/uncertainty/error/false-classification limitsを事前定義。操作: A0/A1個別zero/gain校正、A0,A1,A4,A5,A2,A3の個別midpoint取得。PWM0..30、threshold-near、channel switch、thermal/power cornersでreferenceと同期比較。25/75ms timestampsを維持。期待: A0だけ正式電流、A1独立、A2/A3参照、A4/A5独立raw。ADC ±2LSB contributionとsensor/reference/noise/offset/settling/filter termsを報告。合格: uncertainty budget内、bias/variance/repeatability/false classification限界内、timing/settling合格。variant/limits欠落はBLOCKED。証跡: sensor marking、calibration cert、paired raw captures、VREF、filter response、timing trace、uncertainty analysis。

### T17 fsync latency/crash/durability
前提: target host/storage benchmark profile、command/stage deadlines、safety marginを事前承認。操作: intent/RX/ACK/file/directory/manifest fsync各classを代表・stress loadで測定しmean/p50/p95/p99/p99.9/max/count/errorを記録。write/fsync/dir-fsync error、deadline超過、各intent/write/RX/ACK/checkpoint/manifest境界crash、backup restoreを注入。期待: durable intent前nonzero送信なし、failure後nonzero禁止、STOP best-effort、unknown-send intent再送なし、original保持、reconcile不能はincomplete。合格: measured worst-case persistence+serial/ACK/scheduler+preapproved margin < applicable deadline、p99/p99.9もdeadline内。全fault caseがhash verified completeまたは明示incomplete、silent successなし。backup restore hash identical。証跡: benchmark manifest、latency distributions、fault trace、recovery hashes、validator、restore report。

### T18 20Hz候補の非採用確認
前提: T16入力と別途承認されたhigh-rate reference capture。操作: 25/75ms候補統計をreferenceとphase/settling/noise別に比較。期待: uniform20Hzへの再ラベル、単純Nyquist=10Hz主張なし。合格: named low-frequency statisticの事前uncertainty/aliasing/classification boundsを満たす場合のみ候補を推奨できる。sampling clock採用やfirmware変更は別承認。証跡: reference captureとanalysis。

T13–T18はNOT RUN。実装・compile・serial・energize・motor measurementの許可ではない。


## T13 EEPROM endurance and power interruption
**前提:** exact MCU datasheet and emulator; physical power interruption only after separate authorization. **操作:** 36,600 event wear calculation; inject interruption at marker invalidation, each payload/CRC byte, readback, commit marker and post-commit; repeat brownout loops. **期待:** max slot visits 2,288; marker 4,576/cell; payload≤2,288/cell; aggregate marker 73,200; no provision rewrite; ambiguous record rejected. **合格:** every simulated cut selects previous valid or fully verified new record; otherwise BOOT_ID_INVALID. Physical qualification requires VCC≥4.5V for ≥57.8ms plus reviewed margin, verified early warning/supervisor and zero partial-record acceptance. **証跡:** chip marking/signature, datasheet, EEPROM dumps, per-cell counters, power waveform.

## T14 BOD/fuse and 16MHz
**前提:** exact MCU and approved supervisor circuit; no fuse writes without approval. **操作:** read fuse bytes, ramp VCC and inject pulses; verify reset threshold/delay/clock. **期待:** BOD 4.3V range 4.1–4.5V; 16MHz speed-grade requires VCC≥4.5V; external supervisor asserts before VCC falls below 4.5V. **合格:** no operation outside speed-grade envelope; no EEPROM corruption; 4.3V BOD-only configuration is FAIL. **証跡:** fuse dump, supply/clock waveform, supervisor datasheet and board schematic.

## T15 SRAM and bounded buffers
**前提:** pinned compiler/core/library/build flags. **操作:** linker map, sizeof inventory, UART ring size, 194B RX/TX max frames, nested parser/CRC/COBS/STOP/ISR stack watermark, heap audit. **期待:** static≤900B; stack≤700B; reserve≥448B; no second ADC 173B staging array; no critical-path heap/String; no TX-owned overwrite. **合格:** all bounds simultaneously met, no canary/collision/overflow, max frame round-trip. **証跡:** map, size output, sizeof table, stack canary, heap symbol audit.

## T16 STOP under blocked TX and writer
**前提:** simulator with permanent TX backpressure, partial TX frame, ADC batch and blocked Evidence writer. **操作:** inject valid STOP in each state. **期待:** STOP_LATCHED, PWM=0, direction outputs LOW, ARM invalidated before ACK; no wait for TX drain/flush/fsync/batch. **合格:** actions within preapproved bounded loop-service deadline independent of TX; no later nonzero PWM accepted; ACK may be delayed. Physical stop not inferred. **証跡:** scheduler/register/pin trace, ownership log, max STOP latency.

## T17 ADC precision qualification
**前提:** exact ACS712 suffix/module/filter, supply, VREF, source impedance, PWM frequency, statistic, Uallow/risk limits approved; reference Uref(k=2)≤Uallow/3. **操作:** zero/threshold-near/mid/max levels; ≥30 stable windows per level per channel; A0/A1 separately; relevant polarities/temp; high-rate reference phases; MUX dummy conversion and timestamps. **期待:** role separation unchanged; no uniform 20Hz claim. **合格:** each level abs(bias)+Uref≤Uallow, repeatability/95% interval/offset drift/hysteresis/false classifications within preapproved limits. Missing Uallow/risk limits = BLOCKED. **証跡:** sensor marking, schematic, filter, calibration cert, raw data and uncertainty report.

## T18 fsync latency and recovery
**前提:** exact host/OS/filesystem/storage/runtime; configured D_intent/D_evidence derived from measured stage slack and STOP reserve. **操作:** ≥10,000 intent and ≥10,000 Evidence commits; normal/max batch load, cold/warm, storage contention; inject short write, ENOSPC, fsync delay/error, crash at append/fsync/rename/directory-fsync, reboot and backup restore. **期待:** durable intent before nonzero TX; failure blocks continuation; STOP bypasses writer; recovery preserves originals. **合格:** every operation≤hard budget; p99.9 and max≤configured limits; zero missed 10s deadlines; STOP within its separate bound; exact hash/count/ACK reconciliation and byte-identical backup restore. Missing budget or silent loss = BLOCKED/FAIL. **証跡:** latency distribution mean/max/p50/p95/p99/p99.9, fault trace, hashes, recovery and restore report.

## Updated gate
T01–T18 individually PASS/FAIL/BLOCKED. BLOCKED is not PASS. Physical T13/T14/T16/T17 require separate explicit approval. This specification authorizes none of the prohibited actions.


## 公式資料
- Atmel-42735B-ATmega328/P Datasheet Complete, 11/2016: https://docs.arduino.cc/resources/datasheets/Atmel-42735-8-bit-AVR-Microcontroller-ATmega328-328P_Datasheet.pdf — §§12.3–12.4 (SRAM/EEPROM), §12.6.4 Table 12-1 (EEPROM write sequence/time), §15.5 and Table 32-8 (BOD), §28.3–28.5 (ADC timing/MUX), §32.3 (speed grade), §32.8 (ADC characteristics).
- Allegro MicroSystems ACS712 Datasheet Rev.22 (2024-02-13): https://www.allegromicro.com/-/media/files/datasheets/acs712-datasheet.pdf — family bandwidth, FILTER pin and variant sensitivity; exact installed suffix/module remains unknown.
- Microchip ATmega328P product page: https://www.microchip.com/en-us/product/ATMEGA328P
