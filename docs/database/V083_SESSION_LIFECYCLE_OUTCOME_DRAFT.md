# v0.8.3 Session Lifecycle / Measurement Outcome分離案

- 基準日: 2026-11-21
- 状態: CC-01統括判断反映対象の論理設計補助資料・全体設計は未承認
- 関連: v0.8.3 §1.2 / §1.4 / §6 / §7、Issue #35、Issue #201、Issue #77
- 目的: 統括判断CC-01に従い、Session LifecycleとMeasurement Outcomeを分離する規則を本文・状態遷移資料と同期する。
- 本書はDBスキーマ、DDL、実装、匿名RawLogの後日DB取込を承認しない。

## 1. 問題と基本判断

v0.8.3 §1.4の「Session StatusはHistorical SessionのMeasurement集合から導出する」は、SessionがScope / Physical Run単位の履歴コンテナであることと整合しない。1つのSession内に複数Measurementがあり、個々のMeasurementはCOMPLETE / STOP / ERROR / CANCEL等の異なる終端結果を持ち得る。これらの結果を1つのSession Statusへ単純集約すると、正常完了と中断・異常が混同される。

**統括決定（Issue #210）: Session LifecycleとMeasurement Outcomeを完全に分離する。**
- Session Lifecycleは、そのScopeのPhysical Run内での履歴コンテナの存続状態。
- Measurement Outcomeは、個々のMeasurementの終了結果。
- Measurement Outcomeの混在からSession Lifecycleを算出しない。
- Session LifecycleはNOT_CREATED / OPEN / CLOSED / QUARANTINEDとする。NOT_CREATEDはSessionレコードではなく未生成状態。
- Sessionの存在・状態はCurrent Assignmentを意味しない。
- DB unavailable / Anonymous ModeではDB Sessionを作らず、外部正本上のRun / Capture情報を保全する。Issue #201の匿名RawLogをDBへ後日取込・再紐付けすることは本案に含めない。

## 2. Session Lifecycle

### 2.1 状態

| State | 意味 | 生成・遷移条件 |
|---|---|---|
| NOT_CREATED | 当該ScopeにSessionが存在しない | Scopeが一度も確定ASSIGNEDになっていない |
| OPEN | 当該ScopeのHistorical Sessionが作成され、Physical Runが終了していない | 最初の確定ASSIGNED Operationで一度だけ作成 |
| CLOSED | Physical Runの終了が外部正本で確定し、Sessionを閉じた | 検証済みPHYSICAL_RUN_CLOSED Eventを確認 |
| QUARANTINED | Run終端証拠またはSession参照の競合・Hash不一致等で自動確定できない | Restore / Integrity検査で矛盾を検出 |

NOT_CREATEDはSessionレコードのStatusではなく、Session未生成状態を表す論理状態である。Session生成後にNOT_CREATEDへ戻らない。CLOSEDからOPENへ戻さない。QUARANTINEDは通常遷移で解除せず、新しいRecovery Operationで扱う。

### 2.2 Sessionを閉じる条件

1. SessionはMeasurementごとに開閉しない。
2. AssignmentがASSIGNED→NONE / ANONYMOUS / 別Instanceへ変化してもSessionを閉じない。
3. MeasurementがCOMPLETE / STOP / ERROR / CANCELとなってもSessionを閉じない。
4. SessionはPhysical Run全体の終了を示す外部正本のPHYSICAL_RUN_CLOSED Eventが検証された場合にのみCLOSEDとする。
5. DB Mirrorが停止・消失・利用不可でも、外部正本にPHYSICAL_RUN_CLOSED EventがなければCLOSEDと推測しない。
6. アプリ終了、プロセス消失、PC再起動、ファイル末尾時刻、一定時間の無通信だけをPhysical Run終了の証拠にしない。
7. Run終端が不明な場合、SessionはOPENのまま保持し、必要ならRecovery Required / QUARANTINEDを別のIntegrity状態として記録する。未確認を正常終了に読み替えない。

### 2.3 Physical Run終端証拠

PHYSICAL_RUN_CLOSED Eventは外部正本側のRun Manifest / Journalで不変記録され、少なくとも以下を持つ必要がある。
- Physical Run ID
- Event ID / Event Ordinal
- Closed At（時刻は記録値。時刻のみで終了を判定しない）
- Termination Class
- Termination Reason
- Initiating Operation IDまたはRecovery Operation ID
- Final Scope / Assignment / Measurement / Capture reference set
- Canonicalization Version / Payload Hash / Event Hash

Issue #210は、PHYSICAL_RUN_CLOSEDを機器プロトコル上の既存Eventではなく、Run管理側の明示的Close Operationが外部正本へ記録する論理イベントとして定義する方針を決定した。イベント名・Schema・永続化形式は本論理案で定義してよいが、Motor/BatteryのSTOP ACK、最終Telemetry、アプリ終了等の既存機器Eventから推定・代用してはならない。Close Operationの実行主体・UI・具体的なCapture終端契約は、Motor/Battery正式契約との照合を経て別途確定する。

## 3. Measurement Outcome

### 3.1 MeasurementごとのOutcome案

| Outcome | 意味 | 必要な証拠 |
|---|---|---|
| COMPLETE | 規定の測定手順が正常に完了 | 正常終了条件を満たす終端Event / Finalization record |
| STOP | 明示的なSTOPにより測定が終了 | STOP Event / command evidence。STOP ACKだけを物理停止証明としない |
| ERROR | エラーにより測定が終了 | Error Event / Error Code / 利用可能な診断証拠 |
| CANCEL | ユーザー等の明示的Cancelで測定が終了 | Cancel Event / Actor Intent |
| INCOMPLETE | 開始証拠はあるが、規定の正常終端条件を満たさず未完了と確定 | Recovery判定または明示中断記録と、その根拠 |
| UNKNOWN | 終端Outcomeを証拠から確定できない | 欠落・競合・不確実性を示すIntegrity情報 |

STOP / ERROR / CANCELをCOMPLETEへ読み替えない。INCOMPLETEとUNKNOWNを区別し、証拠不足を推測で埋めない。

### 3.2 STOPの細分類

STOPは測定結果の終端分類であり、停止原因の完全な分類ではない。必要な場合は別フィールドTermination Reasonで次を区別する。
- USER_STOP
- SAFETY_STOP / EMERGENCY_STOP
- OPERATOR_ABORT
- DEVICE_STOP
- OTHER（理由コード必須）

Issue #35のMotor安全契約ではSTOP後の再始動ラッチ、ARM要件、通信不明時の安全条件が別に規定されている。DB Outcomeはこれらの制御安全条件を置き換えず、STOP ACKを物理停止の証拠として扱わない。

### 3.3 INCOMPLETE / UNKNOWNの判定境界

- 開始記録が存在し、終了記録が欠けているだけでは、ただちにERRORまたはCOMPLETEにしない。
- 正本の全範囲を検証し、正常終端条件を満たす証拠がなく、Recovery規則により未完了と確定できる場合に限りINCOMPLETE。
- RawLog / Telemetryの一部欠損だけで、制御・測定全体の終了Outcomeを推定しない。Issue #35は初期段階のTelemetry欠損を許容し、欠損頻度と解析影響を記録する方針。
- 終端Eventそのものの欠落、Manifest競合、正本検証不能などでOutcomeを決められない場合はUNKNOWNまたはQUARANTINEDとし、正常終了・異常終了のいずれにも推測しない。
- どの条件でINCOMPLETEを確定できるかは、Motor/Batteryの正式Measurement Capture契約とRecovery手順を受領して確定する。

## 4. SessionとMeasurementの関係

| Session Lifecycle | Measurement Outcome | 許可される関係 |
|---|---|---|
| OPEN | COMPLETE | 許可。Sessionは継続OPEN |
| OPEN | STOP / ERROR / CANCEL | 許可。Sessionは継続OPEN |
| OPEN | INCOMPLETE / UNKNOWN | 許可。Sessionは継続OPEN。Integrity情報を保持 |
| CLOSED | 既存MeasurementのいずれのOutcome | 許可。履歴不変 |
| CLOSED | 新しいMeasurement開始 | 拒否。新しいPhysical Run / Scopeが必要 |
| QUARANTINED | 新規Measurement Mirror登録 | 拒否または保留。自動修復しない |
| NOT_CREATED | NONE / ANONYMOUS期間のMeasurement | 外部正本のみ。DB Session / DB Measurementを作らない |
| NOT_CREATED | 初回ASSIGNED後のMeasurement | DB Run / Sessionを生成後、測定時Assignmentに従い登録 |

Sessionの表示用サマリーを設ける場合も、Measurement Outcome別件数や最終MeasurementのOutcomeなど、元データを保持した派生値に限る。Session StatusそのものにCOMPLETE / STOP / ERROR / CANCELを割り当てない。

## 5. Issue契約との整合

### Issue #201
- Anonymous ModeではDB Sessionを作らない。
- Motorのin-memory SessionはDB Sessionとは別物。
- 匿名RawLogはローカル保全し、COMPLETE / STOP / ERROR / CANCEL等を区別する。
- ANONYMOUS期間のRawLog / Measurementは現行範囲で後日DB取込・Mirror化・Instance再紐付けを禁止する。将来変更は別設計と統括の明示承認を要する。
- CH1 / CH2はそれぞれ独立した匿名RawLogとして扱う既承認方針を維持する。

### Issue #35
- Motor接続・制御・RawLog契約をDB側から変更しない。
- STOP / ARM / 再始動ラッチ等の安全制御状態とMeasurement Outcomeを混同しない。
- RawLog v2の項目・形式を旧RawLog v1から推測しない。
- Telemetry欠損許容方針と、Measurementの正常完了判定を分離する。
- DB Session LifecycleはMotor制御・Measurementの実行状態を指示しない。

## 6. 状態遷移受入テスト案

| Test ID | 初期条件 / Event | 期待結果 |
|---|---|---|
| SES-001 | 初期NONE / ANONYMOUSのままRun終了 | Sessionなし |
| SES-002 | 初回ASSIGNED確定 | Sessionを1回生成しOPEN |
| SES-003 | ASSIGNED→NONE | Session ID / OPENを維持 |
| SES-004 | ASSIGNED→ANONYMOUS | Session ID / OPENを維持 |
| SES-005 | ASSIGNED A→B | Session ID / OPENを維持 |
| SES-006 | Measurement COMPLETE | Measurement COMPLETE。Session OPEN |
| SES-007 | Measurement STOP | Measurement STOP。Session OPEN |
| SES-008 | Measurement ERROR / CANCEL | 個別Outcomeを保持。Session OPEN |
| SES-009 | 複数MeasurementにCOMPLETEとSTOPが混在 | Sessionを単一COMPLETE/STOPへ集約しない |
| SES-010 | Run管理側の明示Close Operationが外部正本へ記録され、依存参照の検証成功 | SessionをCLOSED。これは論理Run管理Eventであり機器Event / STOP ACKではない |
| SES-011 | プロセス終了のみ、Run Close Eventなし | SessionをCLOSEDにしない |
| SES-012 | Run Close Event Hash不一致 | Session / RunをQUARANTINED |
| SES-013 | CLOSED後にMeasurement開始要求 | 拒否 |
| SES-014 | 開始証拠あり、終端Event欠落、正本検証可能 | Recovery規則に従いINCOMPLETEまたはUNKNOWN。自動COMPLETE禁止 |
| SES-015 | RawLog Telemetry欠損のみ | Telemetry欠損を記録。Measurement Outcomeを自動ERROR/INCOMPLETEにしない |
| SES-016 | Anonymous Measurement | DB Session / DB Measurementを作らず、外部正本と匿名RawLogを維持 |

| SES-017 | 初回ASSIGNED後、Measurement 0件 | Session OPEN。NOT_STARTED等へ変化しない |
| SES-018 | Session OPEN、全Measurement COMPLETE | Session OPENを維持 |
| SES-019 | Session OPEN、全Measurement ERROR / STOP | Session OPENを維持 |
| SES-020 | COMPLETE / STOP / ERROR / CANCEL混在 | 各Measurement Outcomeを保持。Session LifecycleはOPEN |
| SES-021 | STOP ACK / 最終Telemetry / app exit / inactivityのみ | 明示Close OperationなしではCLOSEDにしない |
| SES-022 | 明示Close Operation + Capture終端/明示放棄/保留 + 参照検証成功 | CLOSED許可 |
| SES-023 | Close時に未終端Capture / 参照不整合 | CLOSED拒否。OPEN維持またはQUARANTINED |
| SES-024 | Close Operationの外部正本欠落 / Hash不一致 | CLOSED拒否。OPEN維持またはQUARANTINED |

これらは提案テストIDであり、既存V082-001〜053との対応・採番統合は未実施。合格実行済みを意味しない。

## 7. 未解決事項

1. Run管理側Close Operationの実行主体・起動UI・取消不可条件・監査Actorの定義。
2. Measurement単位の正式な開始・終端EventとCOMPLETE / STOP / ERROR / CANCELの判定根拠。
3. INCOMPLETEを確定するRecovery規則とUNKNOWN / QUARANTINEDの境界。
4. Motor / Batteryで共通化可能なOutcome語彙と、機器固有Termination Reason。
5. DB Run / Sessionの終端Operationと、Physical Run終端の順序、および全ScopeのCaptureが終端または明示放棄・保留となる受入条件。
6. DB unavailable中にPhysical Run終端をどの外部正本へ記録するか。匿名RawLogの後日DB取込を意味しない。
7. v0.8.3 §1 / §6 / §7 / §12 / V082受入表への反映時に、既存Motor/Battery正式契約を上書きしないこと。

## 8. 結論

Issue #210のCC-01統括判断に従い、Session Lifecycle（NOT_CREATED / OPEN / CLOSED / QUARANTINED）とMeasurement Outcome（COMPLETE / STOP / ERROR / CANCEL / INCOMPLETE / UNKNOWN）を完全に分離する。Measurement Outcomeの混在からSession Lifecycleを導出しない。

CLOSEDはRun管理側の明示的Close Operationが外部正本に記録され、その記録と依存参照を検証できた場合に限る。これは論理Run管理イベントであり、機器プロトコル・STOP ACK・最終Telemetry・アプリ終了等を変更・代用する指示ではない。Close Operationの詳細とMeasurement Capture終端契約は引き続き照合対象である。

本資料はCC-01の判断反映案であり、v0.8.3全体の承認、物理設計、DDL、DB生成、Migration、実装を許可しない。


補足: V082-001〜005 / 007にあるNOT_STARTED / COMPLETED / PARTIAL / IN_PROGRESS / FAILED等のSession集約期待値は、Issue #210 CC-01で現行Lifecycleとして廃止された旧案である。これらの語彙をSession Lifecycleへ再導入しない。現行受入ケースはSES-017〜024を含む本書のCC-01契約を優先する。
