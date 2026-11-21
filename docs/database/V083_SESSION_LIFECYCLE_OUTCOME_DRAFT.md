# v0.8.3 Session Lifecycle / Measurement Outcome — 決定版

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
- DB unavailable時はIssue #201に従いAnonymous Modeとして扱い、新規DB Run / Session Mirror / Measurement Mirrorを作らない。ただしCC-01に従い、初回ASSIGNED時の論理Session identityはDB availabilityにかかわらず外部Run Manifestへ生成・保持する。障害期間中のCapture / Measurement / RawLogは復旧後もDBへ取込・Mirror化・再紐付けしない。障害前から存在するDB Run / Session Mirrorは削除せず履歴として保持する。 論理Session identityが存在するScopeの障害期間中Captureは外部Manifest上のSession membershipとして保全できるが、DB Session Mirror membershipには追加せず、復旧後の遡及追加もしない。

## 2. Session Lifecycle

### 2.1 状態

| State | 意味 | 生成・遷移条件 |
|---|---|---|
| NOT_CREATED | 当該ScopeにSessionが存在しない | Scopeが一度も確定ASSIGNEDになっていない |
| OPEN | 当該ScopeのLogical Session identityが外部Run Manifestに作成され、Physical Runが終了していない | 初回確定ASSIGNED OperationでDB availabilityにかかわらず一度だけ生成。DB Session MirrorはDB正常利用可能時のみ作成 |
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
| NOT_CREATED | NONE / ANONYMOUS / DB unavailable期間のMeasurement | 外部正本のみ。DB Session / DB Measurementを作らない。DB unavailable期間はAssignment StateにかかわらずAnonymous Mode扱い |
| NOT_CREATED | 初回ASSIGNED後のMeasurement | 初回ASSIGNEDで外部ManifestにLogical Session identityを生成してOPEN。DB正常利用可能時のみDB Run / Session Mirrorを作成し、Measurementを登録 |

Sessionの表示用サマリーを設ける場合も、Measurement Outcome別件数や最終MeasurementのOutcomeなど、元データを保持した派生値に限る。Session StatusそのものにCOMPLETE / STOP / ERROR / CANCELを割り当てない。

## 5. Issue契約との整合

### Issue #201
- Anonymous ModeではDB Session Mirrorを作らない。初回ASSIGNEDがAnonymous Mode期間中に発生した場合も、論理Session identityは外部Run Manifestへ生成し、DB Mirrorは作らない。
- Motorのin-memory SessionはDB Sessionとは別物。
- 匿名RawLogはローカル保全し、COMPLETE / STOP / ERROR / CANCEL等を区別する。
- ANONYMOUS期間およびDB unavailable期間のRawLog / Measurementは現行範囲で後日DB取込・Mirror化・Instance再紐付けを禁止する。DB unavailableはIssue #201によりAnonymous Modeとして扱い、Assignment-at-MeasurementがASSIGNEDであっても例外にしない。将来変更は別設計と統括の明示承認を要する。
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
| SES-025 | NONE期間の既存DB管理Measurementを明示Association | Assignment-at-Measurement=NONEを維持し、Actor / 時刻 / 変更前後 / 理由を監査。Current Aggregateへ自動算入しない |
| SES-026 | ANONYMOUS期間のMeasurement / RawLogを後日関連付け要求 | 後日取込・Mirror化・Instance再紐付けを拒否 |
| SES-027 | DB利用可能時にSession生成前のNONE Measurementを登録し、後に初回ASSIGNED | MeasurementはSessionへ遡及所属しない。既存記録を保持し、後日の明示AssociationはInstance関連付け履歴のみ |
| SES-028 | 既存SessionがあるScopeでDB利用可能時にNONE Measurementを登録 | 初回登録時に同一Scope Sessionへmembershipを固定。後日のAssociationはInstance関連付けのみでmembershipを変更しない |
| SES-029 | DB unavailable中にAssignment=ASSIGNEDのCapture / Measurementを取得し、DB復旧 | 論理Session identityは外部Manifestに存在するがDB Session / Measurement Mirrorなし。障害期間データのBootstrap / DB取込 / Mirror化 / Associationを拒否 |

これらは提案テストIDであり、既存V082-001〜053との対応・採番統合は未実施。合格実行済みを意味しない。

## 7. 決定済み処置

Issue #210 CC-01 / CC-02およびMain §14により、以下をv0.8.3の確定処置とする。

1. Session LifecycleはNOT_CREATED / OPEN / CLOSED / QUARANTINED。初回ASSIGNED時に生成し、Measurement Outcomeから独立する。
2. Measurement OutcomeはCOMPLETE / STOP / ERROR / CANCEL / INCOMPLETE / UNKNOWN。COMPLETEは機器固有Capture契約が正常終端を証明した場合のみ。終端欠落はINCOMPLETE、開始・終端の存在や順序が不明または矛盾する場合はUNKNOWN。
3. Run CloseはRun Manager発行のPHYSICAL_RUN_CLOSED Operationだけで成立。Actor / UI / Operation evidenceが未提供ならCloseを拒否し、SessionをOPEN維持。終端矛盾・Hash不一致はQUARANTINED。
4. Close時は全ScopeをTERMINAL / ABANDONED / HELDのいずれかに分類。ABANDONED / HELDにはActor・Reason・時刻を必須とし、未確定MeasurementをCOMPLETEに読み替えない。
5. DB unavailable期間はIssue #201のAnonymous Modeとして扱い、Assignment-at-MeasurementにかかわらずDB Run / Session Mirror / Measurement Mirrorを生成しない。ただし初回ASSIGNED時の論理Session identityは外部Run Manifestへ生成し、Lifecycleを外部正本で保持する。障害期間中のCapture / Measurement / RawLogは外部正本に保全するが、復旧後の明示Bootstrap・DB取込・Mirror化・Associationを禁止する。障害前から存在するDB Run / Session Mirrorは削除せず保持する。初回ASSIGNED前のNONE Measurementも外部正本のみであり、後日Session membershipへ遡及追加しない。Session生成後、DB正常利用可能時に登録された同一ScopeのMeasurementは、測定時AssignmentがNONEであってもSession membershipを登録時点で固定できる。NONE AssociationはInstance関連付け履歴のみであり、Session membershipを変更しない。他ScopeのASSIGNEDによるDB Run生成は未ASSIGNED ScopeのNONE MeasurementをDB管理対象へ昇格させない。ANONYMOUS / outage期間の将来取込は別設計・統括の明示承認が必要。

NONE Association Historyは独立UUID EntityではなくOperation Journal Eventで記録する。AssociationOrdinalはMeasurementごとに1から連続増加し、Event Identityは(OperationID, EventOrdinal)、History Recordの論理Identityは(MeasurementID, AssociationOrdinal)。Event RegistryにはNONE_ASSOCIATION_CREATEDとNONE_ASSOCIATION_CLOSEDを登録する。Created EventはTargetInstanceID / AssignmentSnapshotID・Revision / ActorID / OccurredAtUTC / Reasonを保持し、Closed EventはPreviousCreatedEventRef / ClosedAtUTC / CloseReason / ActorIDを保持する。ActiveはCreated後にClosedされていない状態、Closedは対応するClosed Eventが検証済みで存在する状態とし、MeasurementごとActive最大1件。Reassignmentは1 Operation内で旧AssociationをCloseしてから次OrdinalをCreateする。必要Event集合の欠落・順序違反・部分Tail・Hash不一致はOperation / ScopeをQUARANTINEDとし、元Eventを補修しない。Source Commitは必要Event全体を束ね、DB Mirror更新とMarkerは同一DB Transactionとする。Session membershipとAssignment-at-Measurementは変更しない。
6. Current AggregateはAssignment-at-MeasurementがASSIGNEDかつ現在Instanceと一致し、Outcome=COMPLETEのMeasurementだけを対象とする。NONEはHistorical Analysisに明示指定された場合のみRETROSPECTIVE_NONEとして扱い、Current Aggregateへ入れない。
7. 機器固有Termination Reasonは原形保存。正式Mappingがない値をDB側で推測分類しない。

## 8. Decision Baseline

この文書の旧「未解決」表現はMain §14の決定により置換された。残っているのはRun Manager / Motor / Batteryの正式契約受領と実証試験だけであり、設計判断は未決定として扱わない。未契約・未実証時の固定動作はClose拒否、UNKNOWN / INCOMPLETE、OPEN維持、QUARANTINED、Current Aggregate除外のいずれかとする。
