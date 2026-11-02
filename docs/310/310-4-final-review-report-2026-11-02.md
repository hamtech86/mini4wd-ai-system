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

修正済み。100,000 write/erase cyclesはEEPROM**セル単位**のデータシート耐久値であり、800,000回をセル耐久値とは記載しない。16-slot輪番、36,600 boot eventsの設計予算では、marker各セル最大4,575 write、payload各セル最大2,288 write。全16 markerセル合計73,200 write操作はaggregateであり、per-cell ratingとは明確に分離した。800,000 boot eventsは per-cell enduranceを輪番に換算した理想的なシステム上限の算術値で、寿命保証ではない。電源・温度・BOD・中断書込みの実証は未実施。

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
