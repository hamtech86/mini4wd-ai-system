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

## T13–T18 最終統合受入試験（各IDは本節で一度だけ定義）

### T13 EEPROM耐久・電源完全性・BOD/fuse
**前提:** exact MCU marking/signature、datasheet revision、board revision、fuse dump、approved supervisor/hold-up design。**操作:** 36,600-event wear modelをslotごとに照合。supervisor thresholdを温度/電圧公差で測定。marker invalidation、payload/CRC各byte、readback、marker commit前後で電源断をsimulationし、物理注入は別途許可後のみ。fuseはread-onlyで取得。**期待:** max slot visits 2,288、marker 4,576 writes/cell、payload 2,288、aggregate marker 73,200。16MHz動作中MCU pin VCC≥4.5V。4.3V BOD単独はFAIL。**合格:** supervisor worst-case falling thresholdとdelayを含め4.5V未満への動作継続なし。hold-upは実測worst-case write completion+approved marginを満たす。曖昧journalはBOOT_ID_INVALID、partial record acceptance=0。**証跡:** marking/signature、fuse dump、supervisor datasheet、scope waveform、EEPROM dump/counter。

### T14 SRAM/map/stack/buffer ownership
**前提:** compiler/core/library/build flags固定、実装許可後。**操作:** linker map/avr-size、全構造体sizeof、HardwareSerial ring、RX/TX workspace、nested parser/CRC/COBS/ADC/TX/STOP/ISR stack watermark、heap audit、ownership/overflow fixture。**期待:** static≤900B（UART rings含む）、stack≤700B、reserve≥448B、RX/TX各194B以下、追加ADC stagingなし、critical path heap/Stringなし。RX/TX ownership state machineを遵守。**合格:** 全上限同時達成、heap-stack collision/overflow/TX-owned overwrite=0。**証跡:** map、symbols、sizeof、stack trace、ownership log、high-water。

### T15 STOP under TX congestion and MCU fault
**前提:** deterministic simulator/mock。physical testは独立cutoff確認と別途書面許可後。**操作:** TX full/TX_OWNED/partial frame/ADC batch assembly/RX burst/Evidence writer blockedの各stateでSTOP注入。MCU reset/freezeとdriver-enable/pull-downもsimulationし、物理観測は別許可。**期待:** STOP_LATCHED→PWM=0→direction LOW→ARM invalidation。UART drain/availableForWrite/ACK/fsync/batchを待たない。ACKはatomic frame boundary後でもよい。**合格:** software transitionは承認済みbounded loop-service deadline内、latch後nonzero PWMなし。MCU fault時は独立hardware cutoffがdriver inactiveにする。ACK単独をphysical stop PASS根拠にしない。**証跡:** scheduler/pin/enable waveform、TX occupancy、reset/freeze injection、cutoff report。

### T16 ADC acquisition failure / cadence / precision
**前提:** exact ACS712 suffix/module/filter、schematic、VREF/AVCC/source impedance、PWM frequency、bounded ADC routine、statistic、Uallow/risk limits、traceable referenceを事前固定。**操作:** PRECONDITION_INVALID/CONVERSION_TIMEOUT/NOT_ACQUIRED、0 raw、0xFFFF invalid、MUX dummy conversion、channel switch、25/75ms boundary、PWM0..30、threshold-near/zero/mid/maxでA0/A1個別比較。各level/channel ≥30 stable windows。high-rate referenceとphase同期。**期待:** A0 formal current only、A1 independent、A2/A3 reference、A4/A5 independent。failed attempt increments sequence。断線等は診断回路なしに断定しない。20Hzは非採用、25/75ms nonuniform。**合格:** timestamp/order/schedule適合、reference Uref(k=2)≤Uallow/3、各level abs(bias)+Uref≤Uallow、repeatability/offset drift/hysteresis/false classificationは事前限度内。Uallow/risk/sensor variant欠落はBLOCKEDでaccuracy claim禁止。**証跡:** sensor marking、calibration certificate、VREF/filter data、paired raw capture、uncertainty analysis。

### T17 Loss accounting / RawLog companion package
**前提:** RawLog v2 validator、manifest schema、schedule fixture。**操作:** 1秒epoch-local half-open windowsの境界、per-channel expected/attempted/valid/invalid/missing、sequence wrap/gap、batch drop、unattributable loss、append-only correctionを試験。transport-evidence-v1.jsonlをpackage rootに置き、manifest inventory/hash/countを検証。**期待:** batch lossとsample lossを二重計上しない。channel不明を按分しない。既存records.jsonl schemaは不変。manifestがsibling artifactを表現できない場合completeにしない。**合格:** 全境界fixtureの期待値一致、全artifact hash/count一致、既存schema validator pass。manifest表現不能ならBLOCKED/incompleteでありschemaを勝手に拡張しない。**証跡:** fixture、manifest、validator output、hash/count report、recovery trace。

### T18 fsync latency / crash / deadline
**前提:** exact host/OS/filesystem/mount/storage/Python/runtime profile、10秒stage、STOP reserve、marginを承認済み。**操作:** intent/Evidence各≥10,000 commits、cold/warm、normal/max batch、storage contention。mean/max/p50/p95/p99/p99.9を別operation classで計測。short write/ENOSPC/fsync delay/error/crash append/fsync/rename/directory-fsync/reboot/restoreを注入。**期待:** durable intent前nonzero TXなし。failure/unknown後nonzero禁止、STOPはwriterから独立、unknown commandを再送しない。**合格:** D_stage=D_intent+D_serial_write+D_ack+D_required_evidence+D_scheduler+M < 10,000ms−D_STOP_reserve。各operation hard budget内、p99.9/max限度内、stage deadline miss=0、STOP独立上限内、hash/count/ACK reconciliation一致、backup byte-identical restore。profile/budget欠落または超過はARM拒否/FAIL。**証跡:** benchmark profile、latency distribution、fault trace、hash/recovery/restore report。

T13–T18は設計契約に対する実装後受入試験である。未実施はNOT RUNでありPASSではない。T13/T15の物理試験、T16の基準器測定は別途明示許可が必要。これらの記載は実装・compile・serial・energize・motor measurementの許可ではない。


## 公式資料
- Atmel-42735B-ATmega328/P Datasheet Complete, 11/2016: https://docs.arduino.cc/resources/datasheets/Atmel-42735-8-bit-AVR-Microcontroller-ATmega328-328P_Datasheet.pdf — §§12.3–12.4 (SRAM/EEPROM), §12.6.4 Table 12-1 (EEPROM write sequence/time), §15.5 and Table 32-8 (BOD), §28.3–28.5 (ADC timing/MUX), §32.3 (speed grade), §32.8 (ADC characteristics).
- Allegro MicroSystems ACS712 Datasheet Rev.22 (2024-02-13): https://www.allegromicro.com/-/media/files/datasheets/acs712-datasheet.pdf — family bandwidth, FILTER pin and variant sensitivity; exact installed suffix/module remains unknown.
- Microchip ATmega328P product page: https://www.microchip.com/en-us/product/ATMEGA328P
