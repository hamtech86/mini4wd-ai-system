# 310-5 ソフトウェア受入試験ギャップ追補 — 2026-11-02

**対象:** 310-4 acceptance T01–T18 と現行Python候補実装のテストソース照合  
**位置付け:** host-side source review。試験実行結果ではない。仕様変更・PR merge・hardware authorizationを行わない。

## 確認したテストソース

- Python sequence: PR #185 HEAD `d2be96981673e250ba2cbd7f552f91a27a3016c7` の `tests/test_measurement_310.py`
- Transport: 同HEADの `measurement_310/transport.py`
- 受入基準: 310-4 acceptance test document HEAD `291e8b17d31c2c4590986a4615f9454b9be666ce`

## 試験要求と現行テストの境界

| 310-4要求 | 現行ソースで確認できる範囲 | 残る未検証・不足 |
|---|---|---|
| T04 partial write / ACK delay / missing / late ACK | ACK timeout、PWM mismatch、fragmented/coalesced frame、send完了後のmonotonic起点を扱うテストが存在 | 0-byte/partial writeの実装結果、wrong command_id/context/session/epoch、duplicate/late ACK、ACK後STOPの全条件を満たす検証は確認できない。具体codecも未提供 |
| T05 durable intent / fsync fault | RawLog append/finalize失敗時に停止・write-disableする試験が存在 | nonzero送信前intentが実装されていない。intent fsync failure、RX Evidence fsync failure、保存遅延deadline、crash境界の一式は未実装/未試験 |
| T09 STOP under TX blockage | PR #185でSTOP callbackをRawLog appendより先に試みる回帰テストが存在 | transport write/flushがblockした時のSTOP独立性、TX full/partial-frame atomic boundary、MCU STOP latch/output-zero、bounded service deadlineは未証明 |
| T10/T17 package closure | RawLog v2の既存2-file package finalize/recovery testsを既存PRで確認 | transport-evidence-v1 sibling artifactとmanifest inventory/hash/countの整合が未解決。validatorが第三artifactを完全検証する証拠なし |
| T11 loss accounting | ADC_SAMPLE記録に各sample timestamp/validity等を保持するPython APIあり | channel/window単位のexpected/attempted/valid/invalid/missing、batch lossとsample lossの重複防止、unattributable lossのpackage incomplete処理は未確認 |
| T14 SRAM / ownership | Python transportにreceive bufferとpending queuesがある | 対象FWのmap/sizeof/stack/heap/ownership計測は未実施。PythonソースではMCU SRAM予算を判定できない |
| T16 ADC acquisition | Python側ADC_SAMPLE record APIが存在 | firmware acquisition, conversion status, per-conversion timing, cadence/precision reference qualificationは未実装または未実施 |
| T18 fsync latency/deadline | send/ACKのhost monotonic timestampを記録する経路あり | intent/evidence commit latencyのprofile、10,000 commit分布、p99.9/max、STOP reserveを含むdeadline判定は未取得 |

## 新規動的試験の実施状況

本追補では新しいpytest/native testを実行していない。GitHub Actionsの過去のsuccessは該当HEAD・workflowに限定し、上記の不足試験のPASS証拠には流用しない。ローカルcheckoutが利用できず、ローカルpytest/native harnessは未実施。

## 維持する判定と制約

- 送信前durable TX intent欠落は独立FAILとして維持する。
- STOP先行化はRawLog append/fsyncとの順序改善であり、UART TX独立経路や物理停止の証明ではない。
- RawLog v2 schema/package契約を担当判断で変更しない。
- firmware wire codec / acquisition実装は担当の権限外として変更しない。
- 実機通電、Fuse操作、EEPROM電源断、ADC注入、STOP実機試験、310秒測定は未承認・未実施。
- 310-5完了申請および310-6移行は行わない。
