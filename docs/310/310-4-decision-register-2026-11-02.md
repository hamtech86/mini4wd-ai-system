# 310-4 残存事項決定表 — 2026-11-02

対象: PR #183 / docs/310/310-4-design-v0.5.md  
基準: Issue #35、Issue #170、Issue #174、310-1 PR #180、310-2 PR #181、310-3 PR #182、司令塔完遂指示。

| 項目 | 分類 | 決定・現状 | 未解決理由 / 必要入力 | 担当 | 解消条件 |
|---|---|---|---|---|---|
| EEPROM耐久イベント数 | 承認済み | 36,600 boot events | 方式承認ではない | 310-4設計 | 実装で要求を満たすことを試験 |
| EEPROM 16-slot摩耗計算 | 技術根拠により確定 | 約2,288回/slot、markerは約4,576 write操作/slot | 実EEPROMの耐久条件は別 | 設計担当 | MCU datasheet条件・書込み回数実証 |
| EEPROM BOD/fuse/電源断 | 設計入力不足で保留 | BOD値未確定 | 正確なMCU型番、fuse bytes、基板版、電源範囲、datasheet write条件が未提示 | Hardware設計担当 | 実装対象の識別情報と電源設計根拠を提出 |
| EEPROM commit順序 | 技術根拠により確定 | invalidate→payload/CRC→readback→commit marker last→verify | 書込み実証は未実施 | Firmware担当（実装許可後） | 全境界電源断試験合格 |
| Evidence保存期間 | 承認済み | 10年以上 | 保存媒体の選定は未承認 | データ運用責任者 | 容量・媒体・移行・復元計画を提示 |
| 独立バックアップ | 承認済み | 最低1系統、独立して検証 | 具体的保存先未確定 | データ運用責任者 | hash照合＋restore/readability試験 |
| 検出不能な損失 | 承認済み | 許容しない | 未知byte範囲は明示的unresolved/incomplete | Python担当（実装許可後） | 全byte/sequenceのaccountability試験 |
| チャンネル別・期間別損失 | 承認済み | Evidenceでchannel×time-window記録 | window幅・粒度は未定 | 計測設計担当 | window定義と試験ベクトル承認 |
| 20Hz | 310-4の対象外（採用判断） | 未採用。候補値を設計要求にしない | ACS712型番、帯域、PWM周波数、filter、settling、統計量、誤判定率が未提示 | 計測設計担当 | 参照実験を別途承認し、事前基準を満たす |
| ADC scan順 | 技術根拠により確定 | 候補順A0,A1,A4,A5,A2,A3。各変換独立 | 実機取得時間は未測定 | Firmware担当（実装許可後） | timestamp/順序/周期試験 |
| ADC conversion failure検出 | 設計入力不足で保留 | analogRead値だけでは断線・浮遊入力を確定検出できない | bounded ADC routine、診断回路の有無 | Hardware/Firmware担当 | 検出対象・回路・failure semanticsを定義 |
| UART frame arithmetic | 技術根拠により確定 | 194B batch、約33.7ms、平均負荷約34.3% | burst/worst-case latencyは未測定 | Protocol担当 | worst-case scheduler/queue試験 |
| TX時STOP | 承認済み | TX backpressureでSTOP処理を阻害しない | 実装証明なし | Firmware担当（実装許可後） | TX詰まり時STOP試験 |
| Buffer ownership/occupancy/overflow | 承認済み | 明示的状態・occupancy/high-water/loss区分 | 具体的配置は未確定 | Firmware担当（実装許可後） | ownership invariant/overflow試験 |
| SRAM予算 | 実装後検証待ち | superseded: .data+.bss≤900B + stack≤700B + reserve≥448B | compiler map/sizeof/core ring/stackがない | Firmware担当 | 実ビルドmapとstack余裕を提出 |
| fsync failure semantics | 技術根拠により確定 | intent未fsyncなら送信禁止、証跡失敗後nonzero PWM禁止、可能ならSTOP、incomplete | target storage性能未測定 | Python担当（実装許可後） | fault injection合格 |
| fsync latency budget | 設計入力不足で保留 | 数値未確定 | 対象OS/filesystem/storage/load測定が必要 | Python設計担当 | p50/p95/p99/max測定＋期限合格基準を承認 |
| RawLog v2 schema | 承認済み契約を維持 | 変更なし。ADC_SAMPLE=1 conversion | なし | 全担当 | schema validatorで無変更を確認 |
| 310-1 timestamp/epoch/context | 承認済み契約を維持 | midpoint、full epoch、取得時context固定 | 実装後試験は未実施 | Firmware/Python担当 | 対応する受入試験合格 |
| 310-2 recovery | 承認済み契約を維持 | append-only、original preservation、manifest-last | Evidence companion integrationは未実装 | Python担当 | crash/recovery/hash試験合格 |
| 310-3 timing/ownership | 承認済み契約を維持 | Python owns stages、ACK-gated、host monotonic | 310-4 concrete codec integration未実装 | Python担当 | mock integration tests + separate implementation approval |
| 310-5 | 310-4の対象外 | 明示的に未許可 | 310-4受入・別承認が必要 | 司令塔 | 別途正式指示 |

## 過去指摘の閉鎖状況

| 指摘群 | 最終状態 |
|---|---|
| ADC_BATCH length / framing arithmetic | 設計記載あり。実装試験待ち |
| stage_context_id / token mapping | 設計契約あり。実装試験待ち |
| State transition / stale frame / STOP→reARM | 設計記載あり。実装試験待ち |
| STOP_ACK size / command_id vs stop_request_id | 3-byte ACK維持、識別子分離。実装試験待ち |
| Boot identity / EEPROM commit | journal契約あり。MCU/BOD/電源入力待ち |
| Loss / overflow / sequence | host expansion・channel/window requirement追加。実装試験待ち |
| 20Hz | 明示的未採用 |
| SRAM / TX backpressure / STOP | 予算は計画値、compiler・stack・実機外のmock証跡待ち |
| Session tag restart collision | A9.1契約あり。crash/restore test待ち |
| Sequence rollover/ambiguity | A9.2契約あり。boundary test待ち |
| Evidence durability / fsync / recovery | A9.3およびF2.7。fault injection待ち |

**総合:** 設計文書上の契約は統合したが、設計受入の最終判断に必要な一部の技術入力と、実装後検証の証拠は未取得。これらを設計記述の欠落と混同しない。


## 2026-11-02 最終修正審査指摘への決定追記

| 指摘 | 決定・分類 | 根拠／解決内容 | 残る境界 |
|---|---|---|---|
| EEPROM耐久表現 | 技術根拠により確定 | 100,000 write/erase cyclesはEEPROMセル単位。36,600 boot events時、16-slot輪番でmarker各セル最大4,576 write、payload各セル最大2,288 write。全markerセル合計73,200 write操作はaggregateでありセル耐久値ではない。 | データシートの実条件適用、BOD/電源断、実装後の耐久証跡は別途 |
| ADC候補周期 | 技術根拠により確定 | T/T+25/T+100msは同一channelの25ms/75ms交互間隔。平均20 conversion/s/channelだがuniform 20Hzではない。 | 20Hz採用判断は行わない。非等間隔aliasingとreference captureが必要 |
| RawLog sequence | 技術根拠により確定（既存schemaの意味範囲） | Issue #170/PR #180のADC_SAMPLE.device_sample_sequenceはintegerかつepoch内monotonic、固定uint16幅の規定なし。host uint64 extensionを既存integerに格納し、wire uint16はcompanion Evidenceに保持。schema/type/version変更なし。 | validator/package fixtureで既存integer許容とmanifest companion inventoryを実装後確認 |
| batch/loss/context/Evidence | 設計入力不足で保留（package実装） | batch_sequence、loss_counter、stage_context_token、wire uint16はRawLog fieldへ追加せず、transport-evidence-v1 sibling artifactに保持。Issue #35 §3.4に沿いpackage inventory/manifestでhash参照。 | 現行manifest validatorの許容形式・artifact inventory extensionは実装前にschema fixtureで確定 |
| CI | 技術根拠により確定 | 対象HEAD a21d22bの2 workflow runs、5 jobs成功をGitHub Actionsから確認。 | CIは文書・既存ソフトウェア回帰の結果で、実機安全性を証明しない |


## 最終完遂指示 — 技術判断確定表（2026-11-02）

| 項目 | 最終分類 | 確定判断 |
|---|---|---|
| MCU基準 | 技術的に確定 | ATmega328P/Pを設計基準。実搭載chipはmarking/signatureで実機確認し、未確認の保証をしない。 |
| EEPROM | 技術的に確定 | 1,024B、≥100,000 write/erase cycles/cell、CPU byte write typical 3.4ms。全条件寿命・byte atomicityは推定しない。 |
| 16-slot | 技術的に確定 | 36,600 eventsでmarker max4,576/cell、payload max2,288/cell、aggregate marker73,200。算術余裕21.85x/43.71x。 |
| BOD/fuse | 条件付き決定 | 16MHz VCC下限4.5V。4.3V BOD min4.1Vで単独不十分。external supervisor必須、BODは補助。Fuse policy確定、実機readback待ち。 |
| 電源断 | 条件付き決定 | marker-last journal。byte atomicityなし。supervisor+hold-up不適合ならinternal EEPROM-only禁止/BOOT_ID_INVALID。 |
| SRAM | 技術的に確定 | static≤900B、stack≤700B、reserve≥448B、max frame194B、RX/TX workspace各194B、ADC payloadはTX内構築。いずれも上限で実証値でない。 |
| STOP | 技術的に確定 | latch→PWM0→direction LOW→ARM invalidation/STOP_LATCHED。TX drain非依存。physical cutoffは外部回路。 |
| ADC | 技術的に確定 | A0 formal current only、A1 independent、A2/A3 reference、A4/A5 raw independent。25/75ms nonuniform、20Hz未採用。 |
| ADC精度 | 条件付き決定 | ADC 10-bit ±2LSB contribution。sensor/reference/offset/filter/settling/noiseを含むtraceable reference比較。未測定精度保証なし。 |
| fsync動作 | 技術的に確定 | durable TX intent前nonzero送信禁止、fsync失敗fail-closed、STOP best-effort、unknown send再送禁止。 |
| fsync性能 | 条件付き決定 | 固定ms値なし。mean/p50/p95/p99/p99.9/maxを測定しworst-case sum+margin<deadlineで合格。 |
| 実機証跡 | 実機確認事項 | chip/fuse/VCC/hold-up/EEPROM/ADC/STOP/driver/storage測定は未実施。 |

公式根拠: Atmel-42735B-ATmega328/P Datasheet Complete (11/2016), https://docs.arduino.cc/resources/datasheets/Atmel-42735-8-bit-AVR-Microcontroller-ATmega328-328P_Datasheet.pdf §§2,12.4–12.4.2,15.5,31.2,32.3,32.5,28.1–28.5.


## 最終完遂指示 — 決定登録

| 論点 | 分類 | 確定判断 | 未取得証跡 |
|---|---|---|---|
| MCU | 条件付き設計決定 | ATmega328P baseline; EEPROM 1,024B, SRAM 2,048B; 16MHzはVCC≥4.5V | 実搭載chip/package/signature/clock/VCC/fuse |
| EEPROM | 技術決定 | 100,000 cycles/cell; 36,600 events/16 slots; max visit 2,288; marker 4,576 writes/cell; payload 2,288; aggregate marker 73,200; margin 95,424; 21.86× | 実機電源/温度/電源断 |
| EEPROM commit | 技術決定＋回路条件 | 3.4ms/byte; 17 writes=57.8ms; marker-last+CRC/readback; arbitrary power-loss claim requires early warning+external supervisor+hold-up | 実回路波形/hold-up measurement |
| BOD/fuse | 技術決定 | BOD 1.8V range1.7–2.0; 2.7V range2.5–2.9; 4.3V range4.1–4.5. 4.3V alone cannot guarantee 16MHz; external supervisor required | fuse readback, supervisor limits, supply ramp |
| SRAM | 技術決定 | .data+.bss≤900B; stack≤700B; reserve≥448B; RX/TX max194B each; no second 173B ADC staging buffer; no dynamic heap/String in critical path | linker map/sizeof/stack/heap audit |
| STOP | 技術決定 | STOP_LATCHED→PWM0→direction LOW→ARM invalidation before ACK; no TX/fsync/batch wait | simulator then separately approved hardware test |
| ADC | 技術決定＋application tolerance | A0 official, A1 independent, A2/A3 reference, A4/A5 independent; 10-bit; 5V ideal 4.883mV/LSB; ACS712 quantization examples 26.4/48.8/74.0mA/count; no 20Hz adoption; 25/75ms nonuniform; discard one dummy conversion after MUX switch | exact sensor/filter/VREF/impedance, Uallow/risk limits, reference captures |
| ADC precision | 技術決定 | Uref(k=2)≤Uallow/3; ≥30 stable windows/level/channel; abs(bias)+Uref≤Uallow | Uallow and false-classification limit approval; no accuracy guarantee now |
| fsync | 技術決定＋host configuration | intent fsync before nonzero TX; fail-closed on fsync failure/uncertainty; STOP bypass; deadline overrun abort; ≥10,000 operations/type; mean/max/p50/p95/p99/p99.9 | D_intent/D_evidence measured on exact host; not run |
| Evidence retention | 承認済み要件 | ≥10 years; one independently verified backup; zero undetected loss; channel/time-window accounting | storage and restore evidence |

訂正計算: 36,600/16=2,287.5→max2,288; marker=2×2,288=4,576 (prior 4,575 was incorrect); 100,000−4,576=95,424; 100,000/4,576≈21.86; 36,600×2=73,200; 100,000×16/2=800,000 idealized; 17×3.4ms=57.8ms typical; 5,000/1,024=4.883mV/LSB; 2,048−900−700=448B.

「実装後検証待ち」は設計未決定を意味しない。上記設計判断は確定し、実装後検証は適合性証明に限定する。


## 公式資料
- Atmel-42735B-ATmega328/P Datasheet Complete, 11/2016: https://docs.arduino.cc/resources/datasheets/Atmel-42735-8-bit-AVR-Microcontroller-ATmega328-328P_Datasheet.pdf — §§12.3–12.4 (SRAM/EEPROM), §12.6.4 Table 12-1 (EEPROM write sequence/time), §15.5 and Table 32-8 (BOD), §28.3–28.5 (ADC timing/MUX), §32.3 (speed grade), §32.8 (ADC characteristics).
- Allegro MicroSystems ACS712 Datasheet Rev.22 (2024-02-13): https://www.allegromicro.com/-/media/files/datasheets/acs712-datasheet.pdf — family bandwidth, FILTER pin and variant sensitivity; exact installed suffix/module remains unknown.
- Microchip ATmega328P product page: https://www.microchip.com/en-us/product/ATMEGA328P

## 310-4最終統合決定 — 旧記載を置換（2026-11-02）

本節は本登録簿内の先行する「保留」「未定」「設計入力不足」表現と矛盾する場合に優先する。未測定の実機/host値は設計未決定ではなく、確定した契約への適合証跡として扱う。

| 項目 | 最終分類 | 最終契約 | 実装後/実機で取得する証跡 |
|---|---|---|---|
| MCU/EEPROM | 条件付き設計基準確定 | ATmega328P/P baseline。実搭載chipが異なる場合は同等以上のdatasheet条件で再評価。100k cycles/cellはdatasheet条件下の値。 | marking/signature, datasheet revision, temp/VCC profile |
| BOD/電源断 | 回路要件確定 | 4.3V BOD単独は16MHz下限を保証しない。external supervisorのworst-case falling thresholdはMCU pinで4.5V以上、delay中も4.5Vを下回らない。EEPROM write中はearly warning+hold-upでtransaction完了条件を満たす。不能ならEEPROM-only boot identityを禁止しBOOT_ID_INVALID。 | fuse readback, supervisor tolerance, VCC waveform, hold-up test |
| SRAM | 上限契約確定 | .data+.bss≤900B（UART rings含む）、stack≤700B、reserve≥448B、RX/TX workspace各194B以下、ADC batchはTX workspace内。 | compiler map, sizeof, stack watermark, heap/collision trace |
| STOP | 処理順契約確定 | STOP_LATCHED→PWM=0→direction LOW→ARM invalidation。TX workspaceを奪わず、TX drain/fsync/batchを待たない。ACKはframe boundary後可。 | simulator trace; physical cutoffは別承認のhardware test |
| ADC failure | 意味契約確定 | PRECONDITION_INVALID / CONVERSION_TIMEOUT / NOT_ACQUIREDを定義通り区別。sensor断線等は回路診断なしにADC値だけで断定しない。raw missingは0xFFFF+status、0は有効値。 | bounded conversion implementation test, diagnostic circuit evidence |
| Loss accounting | 意味契約確定 | device epoch内1秒半開window×channel。expected/attempted/valid/invalid/missingを計数。識別不能はUNATTRIBUTABLE、按分禁止。append-only correction。 | schedule fixture, boundary/gap/drop test vectors |
| Buffer | 所有権・overflow契約確定 | RX/TX各194B workspaceを単一所有。状態遷移と所有者のみ書込。TX busy中はqueue/overwrite禁止、batch dropはsequence/lossへ反映。 | ownership invariant, high-water, overflow and STOP congestion tests |
| RawLog companion | package契約確定 | transport-evidence-v1.jsonlをpackage root siblingとしてmanifest inventory/hashに列挙。schema変更禁止。manifest表現不能ならpackage incomplete、schema変更は310-1別承認。 | fixture against RawLog v2 validator; package hash/count roundtrip |
| fsync | fail-closed契約確定 | durable intent before nonzero TX; unknown/failure blocks continuation; STOP bypass writer. ARM前にD_intent/D_evidence等を測定し、D_stage < 10,000ms−D_STOP_reserveを確認。 | target host benchmark, fault injection, deadline and STOP tests |
| 20Hz | 未採用確定 | 25/75ms nonuniform scheduleはcandidate only。uniform 20HzやNyquist=10Hzと扱わない。 | high-rate reference and predeclared statistic qualification |

### 固定window・loss record contract
windowはdevice_elapsed_us基準のepoch内1,000,000µs半開区間。channelごとにscheduleからexpected_count、sample attemptからattempted_count、statusからvalid_count/invalid_countを算出。missing_count=expected−attempted。sample sequence gapだけでchannelを推測しない。channel/window不明はUNATTRIBUTABLEとしてepoch単位で保持する。batch lossとsample lossを二重計上しない。window確定後の修正は元recordを参照するappend-only correctionとする。

### ADC failure contract
PRECONDITION_INVALIDは取得前提不成立、CONVERSION_TIMEOUTはbounded routine timeout、NOT_ACQUIREDはschedule機会をdeviceが実行しなかったと特定できる場合のみ。失敗attemptもsequenceを進め、raw unavailableは0xFFFF+status。断線/短絡/浮遊は診断回路なしに断定しない。

### Buffer ownership contract
RX: FREE→FILLING→READY→PARSING→FREE。TX: FREE→FILLING→READY→TX_OWNED→FREE。workspace各1個、194B以下。TX_OWNED中は変更禁止。ADC_BATCHはTX内構築、次batchを別queueへ積まない。送信中に期限到来したbatchはdropし、sequence/loss accountingへ記録。STOPはoutput actionを即時実行し、ACKのみframe boundaryを待てる。

### RawLog package contract
transport-evidence-v1.jsonlはpackage rootのrecords.jsonl sibling。manifest既存artifact inventoryにpath/media type/byte_length/record_count/sha256を登録。既存manifestが表現できなければcomplete扱い禁止、schema拡張は310-1別承認。Evidence append-only、package complete前に全hash/count照合。

### fsync期限契約
ARM前に対象host fingerprintごとのD_intent、D_evidence、D_serial_write、D_ack、D_scheduler、margin M、D_STOP_reserveを測定・設定。D_stageの直列最悪経路合計は10,000ms−D_STOP_reserve未満。D_intent/D_evidenceは各10,000回以上、cold/warm・normal/max batch・storage contentionを含む測定のmaxとp99.9の大きい方を基礎とする。設定欠落・上限超過・fsync不明・stage deadline missはARM拒否またはfail-closed。STOPはwriter lock/queue/fsyncを待たない。数値msは測定前に捏造しない。


## 310-4 v0.5 production protocol contract adoption — 2026-11-04

**Authority decision:** The 310 command authority explicitly approved adoption of the communication protocol proposal in PR #183 / `docs/310/310-4-design-v0.5.md` v0.5 as the production implementation contract on 2026-11-04.

**Adopted contract scope:** The v0.5 message definitions and semantics are normative for implementation, including HELLO/HELLO_ACK identity and nonce correlation, full boot epoch identity, command_id correlation, stage-context token mapping, APPLY/STOP acknowledgement semantics, frame encoding/validation, and the state/sequence/loss/buffer rules specified by the v0.5 design and its linked acceptance-test document. Implementations must follow the exact field layouts, widths, byte order, validation rules, and state transitions in the v0.5 source documents; this decision does not authorize ad-hoc wire changes or incompatible host-only approximations.

**Authority and compatibility:** This approval supersedes the earlier statement that the v0.5 proposal was draft-only and not an accepted production wire contract. PR #183's GitHub Draft/Open state is a review/workflow state and does not negate this explicit command-authority decision. The v0.5 source documents remain the normative reference until superseded by a separately approved revision. Existing RawLog v2 schema and 310-1 through 310-3 accepted contracts remain unchanged unless a separately approved change explicitly says otherwise.

**Implementation status is separate:** Adoption authorizes implementation against this contract; it does not claim the codec, firmware, host integration, or acceptance tests are already complete. T04/T05 can now proceed against the adopted contract. T04/T05 remain NOT PASS until implementation and their required host/fault-injection tests are completed. Firmware identity, compiler/map/stack/SRAM evidence, physical STOP/cutoff, ADC reference qualification, EEPROM/BOD/fuse, and target-host fsync profile remain separate evidence gates.

**Safety boundary unchanged:** This approval is not authorization to upload firmware, open a physical serial connection, energize a motor, perform physical STOP/cutoff tests, interrupt EEPROM power, read/write fuses/ISP, or conduct the 310-second measurement. `HARDWARE_CURRENT_LIMIT_CONFIRMED=false` remains in force. Each such activity still requires explicit separate authorization.


## 2026-11-04 post-adoption implementation finding — wire constants

The command authority adopted v0.5 as the production implementation contract on 2026-11-04. During host codec implementation, a specification completeness issue was confirmed: v0.5 assigns the 16-bit `magic` and 8-bit `protocol_version` header field positions and widths, but does not assign their numeric values. The host codec therefore requires both values as explicit constructor inputs and has no defaults. Synthetic values appear only in isolated tests and are not production configuration.

This note does not change the adopted v0.5 contract or authorize an implementation-specific value. Before firmware/host interoperability or real serial use, the concrete firmware implementation/configuration must provide the exact two values and a matching build identity; the host must then pin and verify them. Until then, codec unit tests can validate algorithms and layout, but production-wire compatibility is **NOT QUALIFIED**. No firmware or physical device operation was performed.


## 2026-11-05 command-authority decision — production wire constants

**Decision:** Assign the previously unassigned v0.5 common-header values as:

- `magic`: uint16 `0x344D` (little-endian wire bytes `4D 34`, ASCII `M4`).
- `protocol_version`: uint8 `0x01`.

**Rationale:** v0.5 already defines a v1 message registry and fixes the header widths and byte order. A stable protocol magic and version are required to distinguish this protocol from legacy serial traffic and reject incompatible frames. The chosen magic has the visible wire signature `M4`; version 1 matches the adopted v1 message registry. These are protocol constants, not device identity values.

**Implementation rule:** Host and firmware must use these exact constants. The host codec may continue to require explicit constructor arguments; production composition must pass the named constants rather than inventing per-build values. A change to either value requires a separately approved protocol revision. Test fixtures must use the normative constants and must no longer label them synthetic.

**Boundary:** This decision resolves only the numeric header constants. It does not qualify a concrete firmware build, MCU identity, compiler/map/stack/SRAM, BOD, ADC timing/reference, STOP path, physical cutoff, or any hardware behavior. No firmware upload, physical serial connection, motor energization, EEPROM/fuse operation, or 310-second measurement is authorized.
