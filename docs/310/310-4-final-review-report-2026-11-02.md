# 310-4 最終審査報告 — 2026-11-02

## 1. 対象と作業時点の確認

- Repository: hamtech86/mini4wd-ai-system
- PR: #183
- Branch: docs/310-4-design-v0.5
- 作業開始時HEAD: f10674de5ba329a69900546778b0bb9e5be10145
- 作業開始時PR: Open / Draft / Unmerged
- 作業開始時対象文書blob: aefa1cd5ea47655aff48d9d9cf762a4020dcbcb7
- 作業開始時点で既存A9を取得し、再提出要求せずに作業を開始した。

310-1/2/3の基準文書・PRを照合した。310-1 PR #180 HEAD 5db3314ddf1efc2c068330ac333367662542ae5c、310-2 PR #181 HEAD e10d06bd1c5baf16df253792483bc4902582fdba、310-3 PR #182 HEAD d9e718b607a873759fffd58fc75bf950af499095。いずれもPRはOpen/Draft/Unmergedであり、PR #183から見た仕様整合性の基準として参照した。受入済み契約として扱われている仕様を変更せず、Issue #35の正本性を維持した。

## 2. 更新成果物

対象ブランチに以下を追加・更新した。

1. 成果物1 — docs/310/310-4-design-v0.5.md  
   既存本文・A9を保持し、F1〜F4を追加。承認要求、技術計算、未確定理由、責務境界、310-1〜3整合を統合。
2. 成果物2 — docs/310/310-4-decision-register-2026-11-02.md  
   既存審査指摘と今回の残存事項を分類表に統合。
3. 成果物3 — docs/310/310-4-implementation-acceptance-tests-2026-11-02.md  
   T01〜T12の前提・操作・期待結果・合格条件・証跡を定義。
4. 成果物4 — docs/310/310-4-final-review-report-2026-11-02.md  
   本報告。

## 3. 技術整理結果

- EEPROM: 36,600 boot eventsを設計budgetとして反映。16-slot journalなら約2,288 generation/slot、marker約4,576 write operations/slotの概算。MCU/fuse/BOD/電源条件が未提示のため寿命保証・BOD値は確定していない。
- 20Hz: 明示的に未採用。ATmega328P標準条件のADC conversion timeは概算できるが、実機設定・sensor bandwidth・filter・settling・threshold statisticを確認できず、妥当性は確定しない。
- ADC: 1変換1 ADC_SAMPLE、個別midpoint timestamp、A0/A1/A4/A5/A2/A3順の候補を整理。analogRead単体で断線検出できるとはしない。
- UART: 57600 8N1で理論5,760B/s、平均候補負荷1,973.5B/s（約34.3%）、194B frame約33.7msを計算。平均値はworst-case latency保証ではない。
- SRAM: 650B static planning + 384B stack + 256B marginを保持。compiler/map/sizeof/stack証跡なしのためfit判定はしていない。
- fsync: intent-before-send、failure後nonzero PWM禁止、可能ならSTOP、deadline超過時incompleteを明文化。数値latency budgetはtarget storage測定待ち。
- Evidence: 10年以上、独立検証済みbackup最低1系統、channel/time-window loss、no-undetected-loss、manifest/hash/recovery条件を反映。

## 4. 310-1〜310-3整合

確認した境界:
- ADC_SAMPLEは1変換1レコード。12-sample batchは12件に展開。
- device_timestamp_point=conversion_midpointを維持。
- device_epoch_idはfull identityを正とし、32-bit tagでepoch確定しない。
- device_sample_sequenceは既存RawLog v2 field内でhost expansion。schema変更なし。
- stage_context_idは取得時点で固定し、受信時のactive stageで再割当しない。
- Pythonが31 stageを管理し、Arduinoは明示指令を実行する。
- command sent、ACK received、device-reported state、physical stateを区別。
- 310-2 public package manifest.json + records.jsonlとappend-only recoveryを維持。Evidenceはcompanion artifact。

## 5. 検証実施・未実施

**実施:** GitHub上のPR #183、対象branch文書、Issue #35/#170/#174、PR #180/#181/#182の文書と仕様内容を取得・照合。設計計算・byte/time arithmetic・journal wear-count estimateを実施。4文書をPR branchへcommitした。

**未実施:** Python/FW変更、unit/integration test、CI再実行、コンパイル、map/sizeof、スタック測定、実機serial、EEPROM電源断、ADC参照測定、UART/STOP実機試験、310秒測定。未実施項目はPASSとしていない。既存CI成功を今回の更新成果物のCI成功や実機安全性証明として扱っていない。

## 6. 更新後Git状態

全4成果物の反映後にGitHubから再取得したHEAD: 91d86a0117836bdc141935ac80b6d0ca4b6b7618。設計文書blob: 95408fa2a8cc3b081488d8588cfbe33b699bfc6e。決定表blob: ba243d950edce1d659130c7dfd391135d9b3999f。受入試験仕様blob: adeb9620dfc98ea107bc43ccadafe29e943367f9。本報告blob: f5399e5de625bb5079fa2e0f70f47bf57b91a8db（本更新前の値。更新後のblob/HEADは次のGitHub再照合で確定する）。PRはDraft/Open/Unmergedを維持し、マージ操作は行わない。

## 7. 設計受入判断

**正式な設計受入可能とは判定しない。**

理由:
1. EEPROMの正確なMCU/BOD/fuse/電源条件が不足。
2. 20Hzの測定品質は参照実験なしに確定できない（現状は未採用）。
3. fsync latency budgetとloss window durationが未確定。
4. 実装後のSRAM/stack/TX STOP/EEPROM recovery/Evidence crash test証跡がない。
5. 310-4 wire protocolは詳細候補を定義したが、Python/FW concrete implementation・test evidenceは未取得。

ただし、司令塔指示の範囲で確定可能な技術計算、承認済み要求、残存事項分類、実装後受入試験仕様は一式に整理した。残存事項を理由に作業を停止・小分け提出せず、完成一式として提出する。

## 8. 権限・PR

- 310-4設計: 最終審査資料提出。正式受入は未判定。
- Python/FW実装: 未許可。
- コンパイル/アップロード/serial/モーター通電/310秒実測: 未許可。
- 310-5移行: 未許可。
- PR #183: Draft / Open / Unmergedを維持。
- HARDWARE_CURRENT_LIMIT_CONFIRMED=false。

本報告は設計審査資料の完成報告であり、実装許可・実機許可・PRマージ許可ではない。
