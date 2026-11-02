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
**操作:** high-rate reference acquisition (separately authorized) and candidate sampling at fixed phases; include channel-switch/stage settling, PWM phase, threshold-near points and all relevant PWM values.  
**期待:** raw conversion order and individual midpoint timestamps correct. Compare candidate statistic to reference. 20 Hz adopted only if predeclared bias/variance/false-positive/false-negative/uncertainty criteria pass.  
**合格:** no aliasing/settling violation beyond approved bounds; otherwise 20 Hz rejected and revised cadence/filter proposed.  
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
