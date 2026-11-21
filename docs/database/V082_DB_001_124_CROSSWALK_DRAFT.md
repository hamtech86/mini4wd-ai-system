# V082-001〜053 ↔ DB-001〜124 クロスウォーク（初期台帳）

- 基準日: 2026-11-20
- 状態: **未完了・個別対応未確定（DB-001〜056の会話記録ベース定義を回収済み。CC-01 / CC-02 overlay追記）**
- 注記: V082-001〜053は旧v0.8.2の受入案を保存した履歴台帳。Issue #210後の現行規範は本書末尾のCC decision overlayを優先し、旧期待結果を現行要件として再利用しない。
- 関連: [DB-001〜124証拠台帳](./DB_001_124_EVIDENCE_LEDGER_DRAFT.md)
- v0.8.2: [共通DB論理設計 v0.8.2](https://github.com/hamtech86/mini4wd-ai-system/blob/docs/db-logical-design-v0.8.2-20261120/docs/database/COMMON_DB_LOGICAL_DESIGN_v0.8.2.md)
- v0.8.3修正案: [差戻し解消案](https://github.com/hamtech86/mini4wd-ai-system/blob/docs/db-logical-design-v0.8.3-remediation-20261120/docs/database/COMMON_DB_LOGICAL_DESIGN_v0.8.3_REMEDIATION_DRAFT.md)

## 判定ルール

- 対応: DB項目の原文とV082試験の事前条件・操作・期待結果が同じと一次資料で確認できた場合のみ。
- 部分: 要件の一部だけが重なると証拠で確認できた場合。
- 重複: 事前条件・操作・期待結果が実質同一と確認できた場合。
- 未対応付け: DB項目の個別本文または対応テストの証拠が未回収。
- 未カバー: DB項目の要求がV082のどの試験にも含まれないと確認できた場合。

DB-001〜056は過去会話記録から個別の短縮定義・期待結果を回収したが、元の正式要件書・当時の承認状態・完全な前提条件は未確認である。DB-057〜078 / DB-079〜109 / DB-110〜124は個別本文未回収（範囲履歴のみ既知）。このため、V082各試験との同一条件・操作・期待結果の一対一対応は依然確定できない。類似した旧SQLiteテスト名や意味の近い試験名から番号を推測しない。「未対応付け」は「重複なし」「未カバー」と同義ではない。

## クロスウォーク表

| V082 ID | 試験条件 | 期待結果 | DB-001〜124対応 | 判定理由 |
|---|---|---|---|---|
| V082-001 | Measurement 0件のSession | NOT_STARTED | 未対応付け | DB-001〜056は短縮定義を回収済みだが、正式原文・同一条件/操作/期待結果の証拠が不足。DB-057〜124の個別定義も未回収のため判定不能 |
| V082-002 | 全Measurement COMPLETED | COMPLETED | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-003 | COMPLETED + FAILED | PARTIAL | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-004 | COMPLETED + IN_PROGRESS | IN_PROGRESS | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-005 | 全Measurement FAILED | FAILED | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-006 | Anonymous Measurement COMPLETED | Sessionなしで状態保持 | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-007 | 後日ASSIGNED | 旧案: 既存MeasurementからSession Status導出 | 未対応付け（旧期待結果はCC-01で廃止） | 個別DB-ID原文未回収。Measurement OutcomeからSession Lifecycleを導出する旧案はIssue #210 CC-01と矛盾し、現行仕様ではない |
| V082-008 | Journal Intent前停止 | Operation未確定 | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-009 | Intent後Commit前停止 | 同じOperationで復旧 | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-010 | Commit後Receipt前停止 | Receipt再生成 | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-011 | Ordinal欠番 | 欠番維持・再利用禁止 | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-012 | CH1 / CH2同一Instance同時割当 | 拒否 | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-013 | Artifact複数Measurement入力 | 全入力Hash保持 | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-014 | CH1 / CH2 Pair Analysis | 個別Benchmark不変 | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-015 | Aggregate FAILED + INTERRUPTED | PARTIAL | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-016 | Aggregate再計算失敗 | Current Valid=NULL | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-017 | Revision 0→1 | Hash Chain一致 | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-018 | Snapshot Hash不一致 | QUARANTINED | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-019 | Model Profile欠落 | MISSING | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-020 | NONE→ASSIGNED | 過去Profile Snapshot不変 | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-021 | 測定中Profile更新 | 開始時Profile維持 | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-022 | 全Scope Anonymous | DB Run / Sessionなし | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-023 | 全Scope NONE | DB Run / Sessionなし | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-024 | Anonymous再構築 | 同一ID / Hash | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-025 | Anonymous→ASSIGNED | DB Run / Session生成 | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-026 | UUIDv5再生成 | 同一Nameで同一UUID | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-027 | RawLog保存途中停止 | DB / GitHub送信なし | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-028 | RawLog Hash不一致 | QUARANTINED | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-029 | Receipt Hash不一致 | QUARANTINED | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-030 | DB消失後再構築 | 外部正本から同一関係を復元 | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-031 | 初期NONE / ANONYMOUSのみ | DB Run / Sessionなし | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-032 | ASSIGNED後に全Scope NONE | DB Run / Session ID保持・Current Aggregate対象外 | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-033 | ASSIGNED→ANONYMOUS→ASSIGNED | ID維持・Anonymous期間測定は自動登録しない | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-034 | ASSIGNED Instance A→B | Session維持・A時代の測定をBのCurrent Aggregateへ含めない | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-035 | NONE中Measurement後にASSIGNED | 測定時State保持・Current Aggregate対象外 | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-036 | Receipt PREPARED後・DB Commit前クラッシュ | 同一Operation再開またはABORTED | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-037 | DB Commit後・Receipt DB_COMMITTED Event前クラッシュ | Marker検証後にReceipt補完 | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-038 | DB MarkerとReceipt Intent Hash不一致 | QUARANTINED | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-039 | Aggregate Request失敗・再試行 | Request不変・Attempt追加・Result Revisionなし | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-040 | 古いRequestの遅延成功 | 履歴保存・Current Validへ昇格しない | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-041 | Artifact自己参照 | 作成拒否 | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-042 | Artifact A→B→A循環 | 作成拒否・既存Artifact不変 | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-043 | 同一入力/Algorithmで再解析 | 新Artifact ID・旧Artifact不変 | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-044 | Input Artifact欠落/Hash不一致 | 生成拒否・依存を隔離 | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-045 | Canonical NULLと空文字 | 異なるbyte列 | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-046 | Canonical区切り/%/NUL | 長さ付きpayloadで一意 | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-047 | Unicode NFC / NFD | 正規化後同一byte列 | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-048 | Timestamp sub-nanosecond | 入力拒否 | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-049 | RestoreでReceiptがRawLog検証前に存在 | Phase A仮検査のみ・最終VERIFIED禁止 | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-050 | 全Anonymous/NONE外部正本のみRestore | DB Run / Session / MirrorなしでID/Hash再現 | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-051 | Source Commit後・DB Commit前クラッシュ | ABORTED禁止・同一OperationでDB Mirror再開 | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-052 | DB Commit後・DB_COMMITTED Event前クラッシュ | Marker / Source Hash照合後に同一Receipt Event補完 | 未対応付け | 個別DB-ID原文未回収のため判定不能 |
| V082-053 | Source Commit前のOperation中止 | ABORTED記録・Ordinal消費済み・再利用禁止 | 未対応付け | 個別DB-ID原文未回収のため判定不能 |

## CC-01 / CC-02 Decision Overlay（現行規範）

以下はV082旧試験の意味を改変せず、Issue #210決定を検証するために追加するv0.8.3補助受入ケース。V082-001〜053の番号・履歴とは別管理とする。

| Overlay ID | 条件 | 現行期待結果 | 状態 |
|---|---|---|---|
| CC-01-T01 | 同一Session内にCOMPLETE / STOP / ERROR等のOutcomeが混在 | Session LifecycleはOutcome集合・件数から導出されず、Measurement単位のOutcomeを保持 | 提案・未実行 |
| CC-01-T02 | STOP ACK / 最終Telemetry / アプリ終了 / プロセス消失 / 無通信のみ | SessionをCLOSEDにしない。Run管理側Close Operationと外部正本・依存参照の検証が必要 | 提案・未実行 |
| CC-01-T03 | Close受入時に対象Captureが未終端・未放棄・未保留、または参照不整合 | CLOSED拒否。OPEN維持またはQUARANTINED | 提案・未実行 |
| CC-02-T01 | NONE測定でDB利用可能、外部正本とDB管理Measurement記録が既存 | 明示Associationのみ設計対象。測定時Assignment=NONEを保持し、Actor/時刻/変更前後/理由を監査。自動Mirror生成なし、Current Aggregateへ自動算入なし | 提案・未実行 |
| CC-02-T02 | ANONYMOUS期間のMeasurement / RawLog | 後日DB取込・Mirror化・Instance再紐付けを拒否。明示操作による例外も不可 | 提案・未実行 |

## 集計

- V082項目数: 53
- DB-ID対応確定: 0（DB-001〜056の短縮定義は回収したが、個別正式原文・同一性証拠が不足）
- 部分対応確定: 0
- 重複確定: 0
- 未対応付け: 53
- 未カバー確定: 0（DB-001〜056の短縮定義のみ回収。DB-057〜124個別定義および正式原文未回収のため判定不能）

## 次の更新条件

1. DB-001〜056の会話記録ベース定義を正式原文と照合できたら、要求単位に分解してこの表を更新する。DB-057〜124は個別原文回収後に追加する。
2. 既存DBテストとの対応は、テストコードのassertionと個別DB項目の文言・期待結果を照合して証拠を添える。
3. V082-031〜053はv0.8.3差戻し解消案で追加提案した試験であり、統括承認・試験実装・実行前はPASSとして扱わない。
4. クロスウォークの確定は文書照合であり、テスト実行PASSとは別の進捗工程とする。
5. Issue #210 CC-01 / CC-02の現行期待結果は本書末尾のDecision Overlayを優先し、V082旧期待結果の誤再利用を防ぐ。

**本書は対応表の初期棚卸しであり、V082がDB-001〜124を置換・網羅・合格したことを意味しない。**
