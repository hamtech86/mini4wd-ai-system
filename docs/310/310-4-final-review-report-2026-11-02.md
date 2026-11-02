# 310-4 最終修正審査報告（5指摘対応）

> 状態：Draft / 司令塔再審査待ち。設計受入・実装許可・実機試験許可ではない。

## 1. 審査対象と基準

- Repository: `hamtech86/mini4wd-ai-system`
- PR: #183
- Branch: `docs/310-4-design-v0.5`
- 修正対象ベースHEAD（4成果物の内容を確定した時点）: `b32bc015fd18be4ef3f5c4c538e30dd1d030943c`
- PR状態：Open / Draft / Unmerged（更新後の最終HEADはPR APIで確認し、PR本文に併記）
- Issue #35を上位仕様権限、Issue #170およびPR #180の `docs/RAWLOG_V2_INDEPENDENT_SCHEMA.md` をRawLog v2 schema authorityとして照合。
- 310-1 PR #180、310-2 PR #181、310-3 PR #182の受入済み契約を変更しない。

## 2. 5指摘への修正結果

### 指摘1 — EEPROM耐久計算

修正済み。100,000 write/erase cyclesはEEPROM**セル単位**のデータシート耐久値であり、800,000回をセル耐久値とは記載しない。16-slot輪番、36,600 boot eventsの設計予算では、marker各セル最大4,576 write、payload各セル最大2,288 write。全16 markerセル合計73,200 write操作はaggregateであり、per-cell ratingとは明確に分離した。800,000 boot eventsは per-cell enduranceを輪番に換算した理想的なシステム上限の算術値で、寿命保証ではない。電源・温度・BOD・中断書込みの実証は未実施。

### 指摘2 — ADC候補周期

修正済み。T/T+25ms/T+100msの繰返しは、同一channelで25ms/75msが交互となる非等間隔取得である。長期平均20 conversions/s/channelと表現できるが、uniform 20Hz samplingではなく、通常のNyquist=10Hzを適用しない。20Hz採用は引き続き未承認。受入試験T07も非等間隔スケジュールとreference比較を判定するよう修正した。

### 指摘3 — RawLog v2互換性

設計上のmappingを明確化。Issue #170/PR #180の `ADC_SAMPLE.device_sample_sequence` は整数型で、device epoch内の単調増加値と定義されており、uint16幅の制約はない。wire uint16をhost側でepoch-scoped uint64 monotonic integerへ拡張し、既存integer fieldに格納する。既存schema field/type/versionは変更しない。元wire uint16、batch_sequence、loss_counter、stage_context_tokenはRawLog recordsへ追加せず、別artifact `transport-evidence-v1.jsonl` に保存する。Issue #35 §3.4に従いpackage-level sibling artifactとしてinventory/manifestからhash参照し、records.jsonlへ混在させない。manifest validatorとの実装互換性はT10で検証し、未確認の実装済み扱いはしない。

### 指摘4 — HEAD/blobの記録

旧報告に残っていた不一致値と「更新前blob」の記載を置換。今回の報告書は4成果物の内容確定ベースHEADを明記し、各ファイルの実blob SHAをPR本文の最終状態記録と照合する。報告書自身のblob SHAはGitHub更新後のPR treeから独立して確認する（自己参照するSHAを本文に埋め込むことはしない）。

### 指摘5 — CI結果

対象HEAD `a21d22b944754674d2e7db9be960063f554a4b5b` に紐づくGitHub Actionsを再取得。2 workflow runs、5 jobsすべてsuccess。

| Workflow run | Job | Result |
|---|---|---|
| 41443507381 | isolated-database-tests | success |
| 41443507345 | test-full-suite | success |
| 41443507345 | test-breakin | success |
| 41443507345 | test-battery | success |
| 41443507345 | test-raw-log-and-sequence | success |

これらは前回提出HEADのCI結果であり、今回5指摘修正後のHEADのCI結果ではない。修正後HEADのCIは別途取得・記録する。CI成功を実機安全性の証明とはしない。

## 3. 更新した4成果物

1. `docs/310/310-4-design-v0.5.md` — EEPROMセル/aggregate耐久数、非等間隔ADC、RawLog sequence/Evidence mappingを修正。
2. `docs/310/310-4-decision-register-2026-11-02.md` — 5指摘の決定分類と残る実装境界を追加。
3. `docs/310/310-4-implementation-acceptance-tests-2026-11-02.md` — T07を25/75ms非等間隔検証に修正。
4. `docs/310/310-4-final-review-report-2026-11-02.md` — 本報告。

## 4. 310-1〜310-3整合性

- ADC_SAMPLEは1変換1レコード。
- `device_timestamp_point=conversion_midpoint` を維持。
- `device_epoch_id` はfull boot identity。32-bit epoch tagを代用しない。
- `stage_context_id` は変換直前に固定したcontextを保持。
- Pythonが31段階のsequenceを所有し、Arduinoは指令適用・取得・報告を担当。
- command sent、ACK received、物理出力状態を同一視しない。
- RawLog v2 recordsとtransport Evidence sibling artifactを分離。
- 不明・欠落・復旧不能な範囲はunresolved/incompleteとし、合成・推測しない。

## 5. 実施・未実施

**実施:** GitHub PR/branch/Issue #35/Issue #170/PR #180のschema確認、4文書更新、EEPROM耐久回数のセル別算術、ADC取得間隔の算術、既存CI結果のjob単位再確認。

**未実施:** 修正後HEADのCI（再取得後に追記）、Python/FW実装、unit/integration tests、compile、SRAM map/stack測定、EEPROM電源断、ADC参照取得、UART/STOP実機試験、serial、motor energization、310秒測定。いずれもPASS扱いしない。

## 6. 残存事項

- 20Hz/非等間隔取得の測定妥当性はreference captureと事前定義基準が必要。
- manifest validatorがcompanion artifact inventoryを受け入れるか、実装前のschema fixtureと実装後T10で確認する。
- MCU/BOD/fuse/電源条件、EEPROMの電源断実証は未完了。
- fsync latency、loss window granularity、compiler-backed SRAM/stack、TX詰まり時STOPは実装後検証待ち。

## 7. 判断と権限

今回の5指摘に対する**文書修正は完了**。ただし、設計受入の正式判断は司令塔に留保する。PR #183はDraft / Open / Unmergedを維持する。

Python/FW変更、compile、upload、serial接続、motor energization、310秒測定、310-5移行は引き続き未許可。  
`HARDWARE_CURRENT_LIMIT_CONFIRMED=false` を維持する。


# 2026-11-02 最終自己審査報告（最終完遂指示対応）

## 対象・権限
Repository hamtech86/mini4wd-ai-system、PR #183、branch docs/310-4-design-v0.5。文書更新のみ。Python/FW変更、compile/upload、serial、motor energization、310秒測定、310-5移行は未実施。PR Draft/Open/Unmerged、HARDWARE_CURRENT_LIMIT_CONFIRMED=falseを維持。

## 5課題の判断
1. MCU/EEPROM: ATmega328P reference baseline、1KB EEPROM、≥100k write/erase cycles/cell。16-slot計算marker4,576/cell、payload2,288/cell、aggregate marker73,200。CPU write typical3.3ms。実chip/全条件寿命は未確認。
2. BOD/fuse/power: 16MHz VCC min4.5V。4.3V BOD min4.1Vで単独不十分。external supervisor+hold-up必須。適合しなければEEPROM-only identity禁止。
3. SRAM/STOP: static≤650B、stack≤384B、reserve≥256B、single194B TX workspace、40B RX parser。STOP latch→PWM0→direction LOW→ARM invalidation/STOP_LATCHEDをTXから独立。
4. ADC: channel roles unchanged、10-bit ±2LSB ADC contribution、sensor/reference/filter/offset/settling/noiseを含むtraceable reference comparison。20Hz未採用、25/75ms nonuniform。
5. fsync: durable TX intent before nonzero PWM、failure fail-closed、STOP best-effort、mean/p50/p95/p99/p99.9/max測定、worst-case sum+margin<deadline。根拠ない固定ms値なし。

## 公式根拠・計算
Atmel-42735B-ATmega328/P Datasheet Complete, 11/2016. https://docs.arduino.cc/resources/datasheets/Atmel-42735-8-bit-AVR-Microcontroller-ATmega328-328P_Datasheet.pdf §§2,12.4–12.4.2,15.5,31.2,32.3,32.5,28.1–28.5.
ceil(36,600/16)=2,288 visits; marker=2×2,288=4,576; payload=2,288; aggregate marker=2×36,600=73,200; margins=100,000/4,576=21.85x and /2,288=43.71x. VREF5.000V example: LSB4.8828mV, ±2LSB=±9.7656mV (ADC only).

## 変更ファイル
1. docs/310/310-4-design-v0.5.md
2. docs/310/310-4-decision-register-2026-11-02.md
3. docs/310/310-4-implementation-acceptance-tests-2026-11-02.md
4. docs/310/310-4-final-review-report-2026-11-02.md

## CI・試験
前回HEAD a21d22b944754674d2e7db9be960063f554a4b5bで2 workflow runs/5 jobs success（isolated-database-tests、test-full-suite、test-breakin、test-battery、test-raw-log-and-sequence）。これは前回HEADの結果であり最終修正HEADのCIではない。最終HEADに紐づくrunsを別途再取得する。新HEADで未起動/未完了ならPASSとしない。T01–T18、compile、map/stack、power/EEPROM、ADC reference、STOP hardware、storage benchmarkは未実施。

## 自己審査
4文書の数値・判断・未実施・合否条件を同期。marker4,576/cellとaggregate73,200を分離し旧4,576を訂正。4.3V BOD単独で16MHz保証としない。650/384/256は上限で実証値でない。STOP ACKはphysical stop証明でない。ADC精度を未測定保証値としない。fsync固定遅延値を作らない。310-1〜310-3/RawLog v2 schemaを変更しない。文書設計判断を完了し、司令塔の一括正式受入審査へ提出可能。ただし実装適合・実機安全・測定精度の証明は未取得。


# 310-4 最終完遂提出 — 2026-11-02

## 最終判断
4文書を同じ技術判断・数値・合否条件で更新した。設計文書は完遂したが、MCU実装同定・基板電源・センサー型番・host storageの実測完了とは異なる。実測していない精度・物理停止・電源断耐性は保証しない。

## 5技術課題の結論
1. EEPROM: 1KB, 100,000 cycles/cell. 36,600 events/16 slots: max slot visits 2,288; marker 4,576 writes/cell; payload 2,288; aggregate marker 73,200; headroom 95,424; ratio 21.86×. 17×3.4ms=57.8ms typical. Marker-last+CRC alone does not prove arbitrary power-loss atomicity; early warning, external supervisor and measured hold-up required.
2. BOD: 4.3V nominal range 4.1–4.5V; 16MHz requires VCC≥4.5V. 4.3V BOD alone insufficient. External supervisor/hold-up requirement is explicit; installed fuse/chip not verified.
3. SRAM/STOP: static≤650B, stack≤384B, reserve≥256B; RX/TX 194B each; STOP latch/PWM0/direction LOW/ARM invalidation before ACK; TX/fsync/batch cannot block. Software cannot protect frozen MCU or failed power stage.
4. ADC: A0/A1/A2/A3/A4/A5 roles unchanged; 10-bit, 5V ideal 4.883mV/LSB; ACS712 quantization examples 26.4/48.8/74.0mA/count only. 20Hz unadopted; 25/75ms nonuniform. Uref≤Uallow/3, ≥30 windows/level/channel, abs(bias)+Uref≤Uallow. No numeric accuracy claim; Uallow/risk limits need approval.
5. fsync: durable intent before nonzero TX; fail-closed on uncertainty; STOP bypass; deadline miss abort; ≥10,000 commits/type and mean/max/p50/p95/p99/p99.9. No arbitrary fixed ms; host-specific budget and benchmark not yet measured.

## Official datasheet and sections
- Atmel-42735B-ATmega328/P Datasheet Complete (11/2016), official hosted PDF https://docs.arduino.cc/resources/datasheets/Atmel-42735-8-bit-AVR-Microcontroller-ATmega328-328P_Datasheet.pdf. §§12.3–12.4 SRAM/EEPROM/endurance/low-VCC corruption; §12.6.4 Table 12-1 3.4ms atomic erase+write and EEMPE/EEPE sequence; §15.5/Table 32-8 BOD ranges; §28.3–28.5 ADC timing/MUX; §32.3 16MHz supply boundary; §32.8 ADC characteristics.
- Allegro ACS712 Datasheet Rev.22 (2024-02-13): https://www.allegromicro.com/-/media/files/datasheets/acs712-datasheet.pdf. Family bandwidth/filter/sensitivity context only; installed suffix unknown.

## Calculation evidence
36,600/16=2,287.5→2,288; 2×2,288=4,576; 100,000−4,576=95,424; 100,000/4,576≈21.86; 36,600×2=73,200; 100,000×16/2=800,000 idealized; 17×3.4ms=57.8ms typical; 16MHz/128=125kHz; 13 ADC cycles=104µs; 25 cycles=200µs; 5,000/1,024=4.883mV/LSB; current quantization 4.883/185=26.4mA, /100=48.8mA, /66=74.0mA per count; 2,048−650−384−256=758B.

## CI / implementation status
Previous HEAD a21d22b944754674d2e7db9be960063f554a4b5b had two workflow runs/five successful jobs (41443507381, 41443507345); these are historical and not final HEAD CI. Final HEAD CI must be fetched after last write; absent run means not run, never success. No Python/FW implementation, compile, upload, serial, motor energization, 310s measurement, fuse read/write, EEPROM interruption, ADC reference, compiler SRAM/stack or fsync benchmark performed.

## Self-review and authority
Four requested paths updated; all five technical topics have explicit design judgments and test gates; 310-1..310-3 and RawLog v2 schema remain unchanged; unknown physical inputs and application tolerances are not claimed verified. PR #183 remains Draft/Open/Unmerged. No merge, 310-5 or prohibited hardware action. HARDWARE_CURRENT_LIMIT_CONFIRMED=false.


## 公式資料
- Atmel-42735B-ATmega328/P Datasheet Complete, 11/2016: https://docs.arduino.cc/resources/datasheets/Atmel-42735-8-bit-AVR-Microcontroller-ATmega328-328P_Datasheet.pdf — §§12.3–12.4 (SRAM/EEPROM), §12.6.4 Table 12-1 (EEPROM write sequence/time), §15.5 and Table 32-8 (BOD), §28.3–28.5 (ADC timing/MUX), §32.3 (speed grade), §32.8 (ADC characteristics).
- Allegro MicroSystems ACS712 Datasheet Rev.22 (2024-02-13): https://www.allegromicro.com/-/media/files/datasheets/acs712-datasheet.pdf — family bandwidth, FILTER pin and variant sensitivity; exact installed suffix/module remains unknown.
- Microchip ATmega328P product page: https://www.microchip.com/en-us/product/ATMEGA328P
