# DB RawLog v2 実装準備・統合候補計画（2026-11-26）

- 発行: DB部門
- 対象指示: [Issue #207 comment #7176255354](https://github.com/hamtech86/mini4wd-ai-system/issues/207#issuecomment-7176255354)
- 文書状態: **IMPLEMENTATION READINESS PLAN / NOT AN IMPLEMENTATION**
- 実施範囲: GitHub上のsource / test / docs読取と計画文書作成のみ。コード・DDL・DB・Migration・Restore・PR・main・実機は変更していない。

## 0. Decision Baseline / 禁止事項

既決定のDB v0.8.3 Decision Baseline、CC-01〜05、DB-RV-01〜08、DB-LR-01〜04を再審議しない。特に次を実装入力として固定する。

- RUN_SCOPE = (PhysicalRunID, ScopeKey)。ScopeKeyは MOTOR / BATTERY_CH1 / BATTERY_CH2。
- MeasurementはRUN_SCOPEへ直接属し、Sessionへの直接FK / membership / session_idを持たない。Session Lifecycleは独立。
- Measurement Outcomeは COMPLETE / STOP / ERROR / CANCEL / INCOMPLETE / UNKNOWN。COMPLETEはOwner正式Capture Contractの正常終端・必須Sample完全性・参照/hash整合が検証できた場合だけ。
- ANONYMOUS / DB unavailable期間のCaptureは外部正本のみ。後日DB取込・Mirror化・Instance再紐付け禁止。NONE Associationは既存DB管理Measurementへの明示Operationだけで、Session membershipを作らない。
- RawLog Objectは原本byte全体のSHA-256。RawLog Object / Reference / Sample Reference / Measurement Sample Linkは別Entity。IDはUUIDv4、Issuer RoleはGL-01 Registryに従う。
- Structured HashはM4W-JCS-1 / SHA-256。UUIDv5は新規Identity方式として不採用。
- Operation Journal / Receipt / Source Commit / DB Markerは別Artifact。冪等・Hash・Ordinal・QUARANTINED規則を維持。
- RawLog v1は原本保全のみ。v1→v2自動変換・推測変換・再分類禁止。CH1 / CH2は独立し、平均・合算・代替値推定禁止。
- 旧DB-001〜124の個別追跡を再開しない。Motor/Batteryへ既回答Field Mappingを再照会しない。

**今回の禁止境界:** DDL / schema変更、DB生成、Migration、Restore実行、実装コード変更、実装PR作成/merge、main反映、実機通電・放電・物理測定を行わない。PR #216 / #218をmergeしない。未実施の検証をPASSと記載しない。

## A. 既存実装Gap（path / symbol / test / commit根拠）

### A-1. 比較対象・現在地

| 対象 | HEAD / 状態 | 読取結果 |
|---|---|---|
| main | 6d075213d4bdf8f5382805daeec4945e2a6c1146（2026-11-22） | v1中心のSerial→RawLog Library経路と旧DB schema |
| Motor 310 integration | integration/310-5-unified-candidate HEAD 9365e43b66470bc550e82186323e1cf821c61fd5 | RawLog v2 / Protocol V2 / Evidence bundle / Winding Sweep UIあり |
| PR #198 | CLOSED / MERGED、merge commit 1161b8fac86dec7cbb9a8fdd1fdadd9e32b7ef41 | baseはmainではなくintegration/310-5-unified-candidate |
| integration vs main | 498 ahead / 30 behind | branch全体のmerge/cherry-pick不可。必要fileだけ別途監査 |
| Battery PR #218 | OPEN / DRAFT / UNMERGED、branch HEAD 91c635dd5c129633898566adf929a8dc2f7386ab | Battery側是正は別branch。main未統合。5A実測E2E / 実機放電NOT RUN |
| DB Draft | db/v0.8.3-followup-remediation-20261121 HEAD 4bf7f49abc79fe4b84820e86ebcc13d2d08c9b29 | §14 Decision Baseline確定。全体承認・実装許可とは別 |

根拠: [PR #198](https://github.com/hamtech86/mini4wd-ai-system/pull/198)、[mainと310 integrationの比較](https://github.com/hamtech86/mini4wd-ai-system/compare/main...integration/310-5-unified-candidate)、[PR #218](https://github.com/hamtech86/mini4wd-ai-system/pull/218)、[DB Decision Baseline](https://github.com/hamtech86/mini4wd-ai-system/blob/4bf7f49abc79fe4b84820e86ebcc13d2d08c9b29/docs/database/COMMON_DB_LOGICAL_DESIGN_v0.8.3_REMEDIATION_DRAFT.md)。

### A-2. mainの現行保存経路

1. **Motor Serial受信:** communication/serial_manager.py の SerialReader.run() は readline().decode("utf-8", errors="ignore") でbyte列を文字列化し、制御応答を除外して RawLogCollector.append(raw_line) へ渡す。デコード不能byteはこの時点で失われる。Collectorは文字列保持であり、原byteの完全保存境界ではない。
2. **Motor保存:** controllers/local_raw_log_breakin_controller.py の finalize_benchmark_raw_log() / _register_raw_log() が文字列snapshotを作り、RawLogLibrary.register() を呼ぶ。v1 Library IDとSession/Instance metadataを使う。
3. **Library書込:** main raw_log_library/manager.py の RawLogLibrary.register() は連番 MOTOR-000001 / BATTERY-000001 を採番し、write_text()で本文、metadata JSON、CSV indexを順に書く。Object UUIDv4、原byte SHA-256、temp/fsync/read-back/atomic publicationはこの経路にない。複数ファイル一括commit点もない。
4. **GitHub送信:** main raw_log_library/github_export.py の GitHubRawLogExporter.register() はRawLogとmetadataを個別PUTする。失敗時はFAILEDを保存するが、PUT済みpathを同一内容としてno-opにする仕組みはない。_put_file(... allow_update=False) は既存pathをduplicate拒否するため、途中失敗後に未送信分だけ再送できることは証明できない。
5. **Battery capture:** main battery_system/serial.py は受信byteを decode(... errors="replace") して文字列化する。CRLF等は保持するが不正byteは置換される。main ui/battery_tab_ui.py のAnonymous RawLog保存はローカルLibraryへ保存する一方、通常DB register_results() はSession / Measurement / Benchmark Resultを直接INSERTし、共通RawLog Object / Reference / Sample Link / Measurement Envelopeとの結合がない。
6. **旧DB構造:** main database/schema/create_tables.sql の measurement.session_id NOT NULL + FOREIGN KEY(session_id) は旧schemaの直接Session所属モデル。CC-03の新論理設計とは一致しない。旧DBを移行してよい根拠ではなく、将来の別承認schema工程で扱う。
7. **Measurement Manager:** main measurement/measurement_manager.py の start_session() / create_measurement() はMeasurementへSession IDを付ける旧実装であり、RUN_SCOPE / Assignment Snapshot / Measurement Outcome / Receiptの共通論理モデルを実装していない。

根拠:
- [SerialManager](https://github.com/hamtech86/mini4wd-ai-system/blob/6d075213d4bdf8f5382805daeec4945e2a6c1146/communication/serial_manager.py#L56-L90)
- [RawLogCollector](https://github.com/hamtech86/mini4wd-ai-system/blob/6d075213d4bdf8f5382805daeec4945e2a6c1146/communication/raw_log_collector.py#L11-L45)
- [LocalRawLogBreakinController](https://github.com/hamtech86/mini4wd-ai-system/blob/6d075213d4bdf8f5382805daeec4945e2a6c1146/controllers/local_raw_log_breakin_controller.py#L52-L149)
- [RawLogLibrary.register](https://github.com/hamtech86/mini4wd-ai-system/blob/6d075213d4bdf8f5382805daeec4945e2a6c1146/raw_log_library/manager.py#L68-L115)
- [GitHubRawLogExporter](https://github.com/hamtech86/mini4wd-ai-system/blob/6d075213d4bdf8f5382805daeec4945e2a6c1146/raw_log_library/github_export.py#L22-L87)
- [BatteryTab](https://github.com/hamtech86/mini4wd-ai-system/blob/6d075213d4bdf8f5382805daeec4945e2a6c1146/ui/battery_tab_ui.py#L220-L276)
- [Battery DB registration](https://github.com/hamtech86/mini4wd-ai-system/blob/6d075213d4bdf8f5382805daeec4945e2a6c1146/ui/battery_tab_ui.py#L424-L481)
- [Legacy measurement schema](https://github.com/hamtech86/mini4wd-ai-system/blob/6d075213d4bdf8f5382805daeec4945e2a6c1146/database/schema/create_tables.sql#L38-L102)
- [MeasurementManager](https://github.com/hamtech86/mini4wd-ai-system/blob/6d075213d4bdf8f5382805daeec4945e2a6c1146/measurement/measurement_manager.py#L315-L339)

### A-3. integration branchにあるRawLog v2

Motor 310 integration branchには次の実装がある。mainへ統合済みという意味ではない。

- raw_log_v2/storage.py: RawLogV2Writer.begin()、RawLogV2Session.append_many()、finalize()、recover_incomplete()。appendごとのrecords fsync、work-state checkpoint、staging + hard-linkによるimmutable file publish、manifest-last completion、recovery original保存、partial JSONL tail保持、再試行時hash照合がある。
- raw_log_v2/validator.py: mini4wd.rawlog v2.0.0 manifest / record validation。31段階PWM_STAGE、ADC_SAMPLE、SESSION_EVENT等のOwner固有形式を検証する。
- measurement_310/evidence_bundle.py: manifest / records / Transport Evidence sidecarを個別hashで束ねるbundle manifestと検証器。
- measurement_310/protocol_v2_session.py / protocol_v2.py: Protocol V2 HELLO/ACK、ADC_BATCH、uint64 sequence、device epoch、loss accounting。
- measurement_310/engine.py + ui/winding_sweep_panel.py: SequenceControllerとWinding Sweep UI。専用workerでRawLog v2 packageを作る。
- integration branch raw_log_library/manager.py の register_v2_reference() は既存連番Library IDで .v2ref placeholderを登録し、package source referenceをmetadataに記録する。これはDB Decision BaselineのUUIDv4 RawLogObjectIDそのものではない。
- integration branch raw_log_library/github_export.py はpackage / Evidence bundleを検証して複数ファイルを順次PUTするが、途中失敗後に既存remote fileを同一hashとしてskipし、残りだけ再送する明示的resume protocolは未確認。allow_update=Falseのduplicate拒否が残る。

既存試験根拠:
- tests/test_raw_log_v2.py: normal finalize、sequence gap拒否、crash recovery、partial tail、idempotent recovery、conflict、manifest commit後の再確認、fsync failure後のretry等。
- tests/test_3106_rawlog_v2_current_contract.py: Library v2 reference、GitHub export bundle、未回復workのexport拒否、Serial startup delay、UI tick queue。
- PR #198記録: Host/UI 661 passed / 2 xfailed、ATmega328PB compile PASS、T18 production-path workflow PASS。記録されたtested source HEADのsoftware/compile evidenceであり、main統合・実機PASSではない。

根拠:
- [RawLog v2 storage](https://github.com/hamtech86/mini4wd-ai-system/blob/9365e43b66470bc550e82186323e1cf821c61fd5/raw_log_v2/storage.py)
- [RawLog v2 validator](https://github.com/hamtech86/mini4wd-ai-system/blob/9365e43b66470bc550e82186323e1cf821c61fd5/raw_log_v2/validator.py)
- [V2 library reference](https://github.com/hamtech86/mini4wd-ai-system/blob/9365e43b66470bc550e82186323e1cf821c61fd5/raw_log_library/manager.py#L91-L136)
- [V2 GitHub exporter](https://github.com/hamtech86/mini4wd-ai-system/blob/9365e43b66470bc550e82186323e1cf821c61fd5/raw_log_library/github_export.py#L24-L130)
- [Winding Sweep UI](https://github.com/hamtech86/mini4wd-ai-system/blob/9365e43b66470bc550e82186323e1cf821c61fd5/ui/winding_sweep_panel.py#L282-L430)
- [RawLog v2 tests](https://github.com/hamtech86/mini4wd-ai-system/blob/9365e43b66470bc550e82186323e1cf821c61fd5/tests/test_raw_log_v2.py)
- [PR #198](https://github.com/hamtech86/mini4wd-ai-system/pull/198)

### A-4. Decision Baselineとの差分

| 領域 | 現状分類 | 差分 / 暫定扱い |
|---|---|---|
| RawLog v2 writer / validator | integration branchに実装、main未統合 | branch全体はmainと498 ahead / 30 behind。丸ごとmergeしない |
| Byte-exact producer boundary | PARTIAL / OWNER DEPENDENT | main Serial経路はdecode時点で原byteを失う。v2 JSONL保存はあるがproducer wire bytes / package / EvidenceのObject境界は別々 |
| RawLog Object UUIDv4 / ContentHashSHA256 | DB Entityとして未実装 | Library log_idは連番。v2 hashはrecords/manifest等のfile単位。DB RawLogObjectIDとObject byte boundaryを結ぶ契約・実装なし |
| RawLogReference / SampleReference / MeasurementSampleLink | 未実装 | Owner packageのlog_id / record_id / sample_idとDB Reference ID / Locatorの正式対応なし |
| Measurement Envelope / RUN_SCOPE / Assignment Snapshot | runtime未実装 | Motor v2 measurement_session_idはOwner capture session ID。DB Session IDやMeasurement→Session FKへ読み替えない |
| UUIDv4 Issuer Registry / CSPRNG | PARTIAL | UUIDv4利用箇所はあるが、GL-01 Entity Type別Issuer Role / Principal Registry / fail-closed issuanceなし |
| M4W-JCS-1 | DB Structured Hashとして未実装 | RawLog JSON serialization / per-file SHAはJCS適合証明ではない |
| Operation Journal / Receipt / Source Commit / DB Marker | runtime未実装 | generic DB transaction wrapperはあるがIntent / Receipt chain / same-transaction Marker / hash verificationなし |
| Anonymous / NONE / ASSIGNED / Session Lifecycle | PARTIAL / legacy model | Anonymous local captureあり。DB共通Run/Scope/Assignment/Session lifecycleとの連携なし。旧session_id FKが残る |
| CH1 / CH2 | PARTIAL / Owner branch未merge | Battery branchで保存・restart・0.0 fail-closed等を是正中。PR #218 OPEN/DRAFT。Common Scope / Reference integration未完 |
| GitHub send-only retry | PARTIAL | v2 package verification/uploadあり。partial uploadからmissing artifactsだけ再送するidempotent resume未証明 |
| DB path fail-closed | 既存範囲で実装・テストあり | resolverは既存絶対path・ro/rwを使い暗黙DB生成を避ける。新Decision Baseline schema validation・Markerは別 |
| SQLite transaction / crash / Restore | PARTIAL / 新モデル未検証 | generic transaction wrapperと旧backup copy/restoreあり。Receipt Marker atomicity、Phase A/B Restoreなし |

## B. 対象ファイル・責任境界

### B-1. 将来の変更候補（今回変更なし）

| 区分 | 対象候補 | 責任・予定 |
|---|---|---|
| V2 Producer / Owner | raw_log_v2/storage.py、raw_log_v2/validator.py、measurement_310/*、ui/winding_sweep_panel.py | Motor Ownerがpackage / Capture semanticsを所有。DBは既存契約のconsumer |
| Shared RawLog Library | raw_log_library/manager.py | legacy log_id / metadataと新DB RawLogObjectID / Reference identityを混同しないadapter境界 |
| External Evidence Storage（新規候補） | DB-side storage adapter / object manifest verifier | byte objectのhash、Object ID、immutable publish、read-back、Path collision、QUARANTINED。package byte boundary確定前は実装不可 |
| DB identity / references（新規候補） | UUID issuer adapter、Envelope / RawLogReference / SampleReference / Link repository | GL-01、RUN_SCOPE、CC-03、CC-04 cardinality、M4W-JCS-1 |
| Journal / Receipt（新規候補） | Operation Journal / Receipt / Source Commit / DB Marker | DB-RV-03の正規順序、冪等性、same transaction marker、read-back |
| DB connection / transaction | database/path_resolver.py、database/manager/connection.py、database/manager/database_manager.py、database/manager/transaction.py | fail-closed path維持。transaction / locking / schema version validationは別Gate |
| DB schema（別承認） | database/schema/* | 現行旧schemaを直接改変しない。DDL / version / table / FKは独立承認後 |
| Backup / Restore（別承認） | database/backup/backup.py | 現行copy2 restoreを新BaselineのRestoreとして流用しない。Phase A/B設計・隔離試験後に別承認 |
| GitHub exporter | raw_log_library/github_export.py | send-only retry、remote same-hash no-op / different-hash conflict、partial upload resume |
| Battery Owner | PR #218 branchのui/battery_tab_ui.py、analysis/battery_benchmark*.py、database/repository/battery_repository.py | Battery Owner責任。DBはScope / Reference consumerを照合するだけ |

### B-2. 変更不要 / 今回触れない対象

- database/path_resolver.pyの既存fail-closed動作は今回変更不要。新schemaのrequired-table/version validationは別承認後。
- firmware/motor/*、Protocol V2 wire schema、ADC sensor semantics、Battery firmware / serial protocolはDB部門の変更対象外。
- PR #198 integration branch全体をmainへmergeしない。498 ahead / 30 behindの全差分をDB工程に混載しない。
- database/mini4wd.db等の運用候補DB、PR63保全DB、runbook、ユーザーPCの実行環境にはアクセス・変更しない。
- app/main_pr63_baseline.py等の保護baselineは変更しない。
- RawLog v1本文、既存ID、既存DB rowは変換・再採番・削除しない。

## C. 実装順序案・各段階の完了条件

以下は依存順序の提案であり、実行許可ではない。

| Stage | 内容 | 依存 / 完了条件 |
|---|---|---|
| 0. Source baseline freeze | main / Motor integration / Battery PR / Decision BaselineのHEAD・blob・test evidence固定。main基点の統合候補branchのfile allowlist作成 | 統括が対象branchと取り込み単位を承認。integration branch全体merge禁止 |
| 1. Owner package contract gate | Motor v2 package（manifest + records）、Transport Evidence sidecar、bundle manifest、Battery raw evidenceのbyte boundary / identity / retention / outcome境界整理 | 既存回答を再照会しない。未定義はUNKNOWN/opaque。packageを1 Objectとするか複数Objectとするか推測しない |
| 2. RawLog v2 producer integration | 承認されたRawLog v2 producer / validator / recovery moduleだけをmain基点候補branchへ取り込む | PR #198と必要依存のfile-level audit、branch ancestry / conflict / tests確認。Owner CIを候補HEADで再実行 |
| 3. External Evidence Storage | byte objectを変換せず保存。RawLogObjectID発行、SHA-256、same ID/same hash no-op、same ID/different hash quarantine、Path collision、fsync/read-back/atomic publish | Object byte boundary・Issuer Authority・supported filesystem確定。RawLog save失敗時はDB/GitHubへ進まない |
| 4. Reference / Envelope integration | Measurement Envelope、RUN_SCOPE、RawLog Reference、Sample Reference、Measurement Sample Linkを既決Field mappingで接続 | PhysicalRunID + ScopeKey、OwnerReference、UUIDv4 identity、0..1 RawLogReference / Measurement、0..N Link、sharing禁止、hash equality、unknown Locator opaque |
| 5. UUID / Structured Hash | GL-01 Issuer Registry、CSPRNG UUIDv4、M4W-JCS-1、Golden Vector、独立実装比較 | Principal / Service registry登録。全Golden Vector / independent implementation一致 |
| 6. Operation / Receipt / DB Mirror | Journal Intent→Receipt PREPARED→Source Commit→DB Marker + Mirror同一transaction→DB_COMMITTED→VERIFIED | Writer/Epoch authority、Receipt Authority、Manifest Commit chain、SQLite transaction / isolation実証。Commit結果不明はQUARANTINED |
| 7. Assignment / Session / Outcome / Aggregate | ANONYMOUS / NONE / ASSIGNED、Scope Snapshot、Session lifecycle、Measurement Outcomeを分離 | Run Manager / Owner Capture Contract受領。Motor package completedをDB COMPLETEへ直結しない。Battery未知項目はopaque |
| 8. GitHub export / retry | 各remote artifact hash照合。same hashはno-op、different hashはconflict、未存在pathだけPUT | Local RawLogとDB Receiptを再生成しない。partial PUT crash matrix PASS |
| 9. Schema / DDL（別承認Gate） | 最小SQL schema / unique / FK / transaction boundary / versioning | 独立した統括・ユーザー承認が必要。今回着手禁止 |
| 10. Migration / Restore（別承認Gate） | legacy DBの取扱い、Phase A structural / Phase B cross-evidence validation、quarantine / rollback | 自動旧DB recovery・暗黙Migration禁止。隔離コピー試験と独立承認が必要。今回着手禁止 |
| 11. PR / merge / main（別承認Gate） | 実装PR・CI・レビュー・統合 | 今回PR作成/merge/main反映禁止。別途明示許可が必要 |
| 12. Physical Owner Gate | Motor / Battery実機Captureとphysical Benchmark | ユーザーの明示指示、Owner手順、安全条件が必要。DB部門では実行しない |

## D. テスト・検証計画（新DB統合ではNOT RUN）

### D-1. Unit

- byte-exact object保存: CRLF/LF、UTF-8/invalid byte、NUL、empty bytes、binary payload、大容量。decode前bytesと保存後bytes一致。
- RawLog ContentHash: original byte全体SHA-256、read-back一致、改行変換・Unicode normalization・metadata追加の検出。
- Structured Hash: M4W-JCS-1 Golden Vector、duplicate key、invalid Unicode、NaN/Infinity、Decimal表現、timezone-aware UTC固定、自己Hash除外、未知schema reject。
- Identity: UUIDv4 canonical form、CSPRNG、Entity Type別Issuer Authority、未登録Issuer拒否、global collision quarantine。
- Reference: Object↔Reference Hash一致、SampleReference単一RawLogReference、Locator opaque保持、空Locator拒否、Link複合Identity、Role/Ordinal/Required、0..1 / 0..N cardinality、sharing禁止。
- Outcome: Owner package statusとDB Outcomeの非同一性。unknown / partial / loss / required sample欠落でCOMPLETE拒否。
- CH1/CH2: Scope / Measurement / RawLog / Aggregate分離、平均・合算・fallback禁止。

### D-2. Integration / transaction

- Motor v2 finalized package → Evidence bundle verify → Object storage → Reference / Sample / Link → Measurement Envelope → Operation Journal / Receipt → SQLite Marker / Mirror。
- Batteryは正式Capture Contractが揃うまでopaque storageのみ。PR #218のOwner変更をDB branchへ無断取り込みしない。
- SQLite: BEGIN IMMEDIATE、同時Writer、UNIQUE/FK/RESTRICT、rollback、MarkerとMirror同一transaction、commit結果不明時のconsistent read。
- Anonymous / NONE / ASSIGNEDとSession lifecycleを分離し、Measurement→Session FKを生成しない。
- Aggregate: COMPLETE条件、Assignment-at-Measurement、Current Assignment、same Instance条件、CH1/CH2独立Owner。

### D-3. Idempotency / concurrency

- 同一OperationID + 同一PlanHash / PayloadHash: no-op。再発行・二重rowなし。
- 同一OperationID + 異Hash: conflict / QUARANTINED。既存正本・DB row不変。
- 同一RawLogObjectID + 同一ContentHash: no-op。異Hash: quarantine。
- 同一Path + 同Hash: 既存Object参照。異Hash: 上書き禁止。
- GitHub artifact: 既存remote同一hashはskip、異hashはconflict、未送信分だけretry。
- 2 Writer / 2 process / same PhysicalRun / different PhysicalRun競合、Epoch fencing、Ordinal欠番・再利用、duplicate Event、fork、last-write-wins禁止。

### D-4. Crash / failure injection / filesystem

- raw file write中、file fsync前後、read-back、staging、hardlink/rename、parent directory fsync、final read-back、completion Eventの各停止点。
- manifest-last publish、partial JSONL tail、work-state stale、recovery original staging、同じrecovery再実行、destination collision。
- RawLog保存後・Journal commit前、Source Commit後・DB transaction前、DB commit直後・Receipt Event前、VERIFIED前の停止点。
- OS/filesystem/mount/device cache別にsupported environmentを限定。fsync / hardlink / directory fsync非対応はfail-closed。software testを電源断耐性の証明へ読み替えない。

### D-5. SQLite / backup / restore / fail-closed

- DB transaction: atomicity、busy/locked、crash recovery、foreign_keys、unique constraints、read-back、marker/mirror一致。
- Backup: consistent snapshot、backup hash、integrity_check、backup manifest。
- Restore: isolated temporary DBのみでPhase A structural validation、Phase B cross-evidence / receipt / marker / external Object validation、quarantine。運用DBへRestoreしない。
- Path resolver: missing / relative / symlink / nonexistent / incomplete schema / read-only / read-write / no implicit create。既存 tests/database/test_path_resolver_integration.pyを維持し、新schema gateは別テスト。
- 現行 BackupManager.create_backup() / restore_backup() はshutil.copy2であり、新BaselineのRestore Phase A/B実装とは扱わない。

### D-6. 既存テスト資産と未実行の区別

- main既存: tests/test_raw_log_library.py、tests/test_raw_log_github.py、tests/test_anonymous_mode.py、tests/database/test_path_resolver.py、tests/database/test_path_resolver_integration.py。
- Motor integration既存: tests/test_raw_log_v2.py、tests/test_3106_rawlog_v2_current_contract.py、tests/test_measurement_310_evidence_bundle.py、tests/test_measurement_310_protocol_v2_session.py、native Protocol V2 tests。
- Battery PR branch: tests/test_battery_tab_safety.py、Benchmark Service / Repository / UI tests。PR #218 exact HEADのCI成功はOwner branch上の証拠であり、mainやDB統合のPASSではない。
- 本作業ではテストコマンド・CI workflowを起動していない。新DB統合、SQLite Marker/Receipt、JCS conformance、DB restore、filesystem crash injectionはすべて **NOT RUN**。

## E. Rollback / Failure Isolation

### E-1. RawLog保存失敗

- DB transaction / DB Marker / GitHub送信へ進まない。
- Producer buffer / .work / recovery originalを保持し、同じObject ID + Expected HashでStorage処理だけ再試行。
- Partial file、hash mismatch、Path conflict、unknown package / schemaはQUARANTINED。原本を削除・上書き・再生成しない。
- RawLog v2 writerのwork/recovery安全性をconsumer側で壊さない。DB adapterは未完了packageを完成扱いしない。

### E-2. DB commit失敗 / 結果不明

- RawLog Object / package / Evidenceは改変・再生成しない。
- 同じOperationID / PlanHash / ReceiptIDでDB処理のみ再試行。新Operationを勝手に発行しない。
- Commit結果不明時はDB Marker・Mirror・Receipt・Source Commitをread-back。完全一致ならcommit済み、証拠不足・不一致ならQUARANTINED。検索0件だけで未commitを断定しない。
- rollback対象は未commit transactionだけ。既存正本RawLog・既存DB row・既存Receiptを破壊しない。

### E-3. GitHub送信失敗

- DB / RawLog / Receiptを再生成しない。GitHub送信だけ再試行する。
- 各remote artifact pathを取得し、同一ContentHashなら送信済みとしてskip、異HashならConflict / QUARANTINED、未存在pathだけPUTする方式を候補とする。
- 送信済みartifactと未送信artifactの状態を記録し、multi-file upload途中停止でも既存remote fileを上書きしない。
- 現行Exporterの「途中PUT済みpathを次回duplicate拒否する」問題は実装候補で修正対象。今回は変更しない。

### E-4. Rollback原則

- append-only正本・Source Commit・Receipt Eventを編集・削除しない。
- 失敗Operationは履歴を残し、必要な復旧は別Recovery Operationで記録する。v0.8.3のQUARANTINEDを自動解除しない。
- temp / staging削除は、所有・内容・commit pointが検証され、正本と誤認されない場合だけ。
- DB schema / Migration / Restoreをrollback手段として流用しない。

## F. 残る外部条件・回収可能性

| 条件 | 現状 / 根拠 | 回収可能性 | 担当 / 解除条件 | 解除前の暫定動作 |
|---|---|---|---|---|
| Motor Capture Contract | Issue #35 M-01〜M-09 Evidence Matrix [#7120818752](https://github.com/hamtech86/mini4wd-ai-system/issues/35#issuecomment-7120818752)。Host identity/start、v2 framing、channel semantics、software recoveryは証拠あり。一方Capture event / CANCEL taxonomy / ADC completeness / DB MeasurementID・ObjectID・SampleReference mapping等はUNKNOWN | RECOVERABLE（software証拠） + NO_CURRENT_BASIS（Owner未定義意味） + CONDITIONALLY_RECOVERABLE（実機精度・loss） | Motor Owner / Issue #35。既存回答の再照会なし | 未定義項目opaque。Owner package completedをDB COMPLETEへ直結しない |
| Battery Capture Contract | Issue #16 Evidence Matrix [#7105933799](https://github.com/hamtech86/mini4wd-ai-system/issues/16#issuecomment-7105933799)。CANCEL/INTERRUPTED、COMPLETE必須sample、byte/hash、sequence/wrap、Outcome mapping、通常DB RawLog linkが未完 | CONDITIONALLY_RECOVERABLE（Owner契約・実装） / NO_CURRENT_BASIS（未定義物理意味） | Battery Owner / Issue #16・#208。DBから既回答mappingを再照会しない | Raw原文保持のみ。UNKNOWN/opaque、COMPLETE / Current Aggregate除外 |
| Battery code readiness | PR #218 branch HEAD 91c635dd5c129633898566adf929a8dc2f7386ab、OPEN/DRAFT/UNMERGED。V1/V2・A1〜A7 CI証跡あり。5A E2E/実機放電NOT RUN | RECOVERABLE（branch code review/CI） / CONDITIONALLY_RECOVERABLE（実機E2E） | Battery Owner・統括のPR review / merge判断 | DB側でbranchを取り込まずmainとの差を維持 |
| UUIDv4 / CSPRNG / Issuer Registry | UUIDv4利用箇所はあるが、GL-01 Entity Type別Issuer Role / Principal登録・失効・監査はruntime未実装 | CONDITIONALLY_RECOVERABLE | 統括 / Identity Authority Owner。Principal・Service・Role mapping登録、CSPRNG検証 | 未登録Issuerから発行拒否 |
| M4W-JCS-1 | Decision Baseline §5.2は確定。独立適合実装・Golden Vector全件PASSは未確認。RawLog JSON compact serializationはJCS適合証明ではない | RECOVERABLE（仕様から実装・Golden Vector作成） | DB実装担当 + 独立検証担当。全Golden Vector・independent implementation一致 | Structured Hash発行 / Receipt VERIFIED禁止 |
| OS / filesystem durability | docs/310/310-5-target-host-t18-results-2026-11-11.md: Linux Mint target-host T18 profile PASS。sequence_complete観測1回 max 9.36s、p99.9 NOT MEASURABLE。Network/removable/Windows/電源断保証なし | CONDITIONALLY_RECOVERABLE | 対象OS/filesystem/mount/storageごとprofile、crash/power-loss試験、supported environment登録 | 未実証環境でDurable / VERIFIEDを宣言しない |
| SQLite transaction / crash recovery | mainにgeneric transaction wrapper / foreign_keys / path resolverあり。DB Marker / Receipt / isolation / crash proofなし | CONDITIONALLY_RECOVERABLE | DB実装担当。隔離DBでBEGIN IMMEDIATE、lock、commit結果不明、crash/reopen、read-back証拠 | Marker / Mirror整合を証明できなければQUARANTINED |
| Backup / Restore | BackupManagerはcopy2 backup/restoreとintegrity_check。新Baseline Phase A/B未実装 | RECOVERABLE（isolated design/test） | DB担当 + 統括。隔離DBでbackup/restore/Phase A/B/rollback試験 | 運用DBへのRestore・Migration禁止 |
| Motor physical Benchmark | Issue #172。PR #198 software/host acceptedと実機測定は別。HARDWARE_CURRENT_LIMIT_CONFIRMED=false | CONDITIONALLY_RECOVERABLE | User explicit instruction + Motor Owner + approved operating conditions | 実機操作禁止、physical outcome NOT RUN |
| Battery physical 5A E2E | Issue #16 / #208。PR #218 software branchとは別gate | CONDITIONALLY_RECOVERABLE | User explicit instruction + Battery Owner + approved conditions | 実機放電禁止、Outcome UNKNOWN |

## G. 承認境界・現在の5軸

### G-1. 今回可能なこと

- GitHub source / test / docsのread-only review。
- Decision Baselineに沿ったGap Register / implementation candidate planの文書化。
- 既存DB work branchに計画文書のみを追加し、Issue #207へ統合報告。

### G-2. 別途明示承認が必要なこと

- 実装コード変更、RawLog producer / DB adapter / Exporter retry変更。
- DDL / schema変更、DB generation、Migration、Restore実行、運用DB接続・書込み。
- 実装PR作成 / Ready化 / merge / main反映。
- Motor / Battery実機接続、通電、放電、物理測定、Firmware upload。
- RawLog packageを単一DB Objectへ束ねる具体的byte boundary、Owner未定義のCapture意味・必須Sample・Outcomeを決めること。

### G-3. 5軸状態

| 項目 | DECISION_STATUS | DOCUMENT_STATUS | IMPLEMENTATION_STATUS | VERIFICATION_STATUS | APPROVAL_STATUS |
|---|---|---|---|---|---|
| DB v0.8.3 Decision Baseline / CC-01〜05 / DB-RV-01〜08 / DB-LR-01〜04 | DECIDED | REFLECTED（既存Draft） | NOT_STARTED | NOT_RUN | 全体APPROVAL PENDING |
| RawLog v2 DB integration plan | DECIDED inputを使用 | REFLECTED（本計画） | NOT_STARTED | NOT_RUN | 統括の工程1実装着手判断待ち |
| Motor RawLog v2 producer | Owner software範囲は既存受入 | integration branchに存在 / main未統合 | Owner branch上実装済み | CI証跡あり、DB統合NOT RUN、hardware NOT RUN | DB実装許可とは別 |
| Battery RawLog / DB integration | Capture contract PARTIAL | Evidence Matrixあり | PR #218 branchの一部是正あり、main未統合 | Owner CIあり、5A E2E NOT RUN | Owner/統括判断待ち |
| DDL / schema / Migration / Restore | Decision Baselineあり | 現行legacy schemaとの差分のみ | NOT_STARTED | NOT_RUN | 明示承認待ち |

## H. DB部門の完了宣言

統括指示の7項目（既存Gap、対象ファイル・責任境界、実装順序、テスト計画、rollback/failure isolation、外部条件、承認境界）を、現在のmainとMotor/Battery owner branchを分けて根拠付きで整理した。

**本成果物の完了は、工程1「DB RawLog v2実装準備」の計画・実装候補セット提出完了を意味する。コード実装・DB schema変更・Migration・Restore・PR/merge・main反映・実機検証の完了を意味しない。**

統括が次に判断する事項:
1. main基点のRawLog v2統合候補branchを作る許可。
2. Motor integration branchから取り込むfile allowlist / dependency auditの範囲。
3. Object package byte boundaryとOwner Capture Contract不足項目をUNKNOWN/opaqueのままconsumer integrationへ進める条件。
4. 実装コード変更の承認範囲。
