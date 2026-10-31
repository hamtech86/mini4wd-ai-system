# RawLog v2 独立スキーマ仕様（310-1）

- 文書状態: 310-1設計案（司令塔受入前）
- スキーマ: `rawlog.v2`
- 対象: PWM 0～30を各10秒間実行する310秒実測
- 正本: Issue #35。Issue #170は実装契約の補足。両者が矛盾する場合はIssue #35を優先する。
- 旧RawLog: v1 legacy。v2への自動変換・再分類・列互換は行わない。

## 1. 設計原則

1. v2はv1の26列CSVとは独立した名前付きJSONスキーマとする。
2. Raw ADC値、取得時刻、校正情報、換算値、Derived値、ユーザー注釈を別の情報として保持する。
3. A0とA1は物理的意味・raw値・取得時刻・校正・解析を完全に分離する。平均、代用、補間は禁止。
4. A2/A3は参考観測として隔離し、制御・停止/継続・異常・品質・採否・Derived推定の入力にしない。
5. 個々のADC変換に個別timestampを持たせる。同一サンプル時刻を仮定しない。
6. 310秒の進行・PWM段階・段階時刻はPythonが管理する。Arduinoは指令されたPWMと不透明な相関IDを扱い、310秒のスケジュールを独自に進めない。
7. 欠損を0、前回値、他チャンネル値で補完しない。
8. コマンド送信成功を物理出力状態確認とみなさない。

## 2. パッケージ構成

1測定につき1つのRawLogパッケージを作る。

```text
<log_id>/
  manifest.json
  records.jsonl
```

- manifest.json: 測定全体の識別、条件、開始/終了、機器・FW識別、レコード件数、最終状態。
- records.jsonl: 1行1JSONオブジェクト。全レコードは追記専用で、保存済み行を更新・削除・置換しない。
- record_seqはPythonが付与するパッケージ内の単調増加整数。書込順であり、ADC取得時刻の代用ではない。
- record_idはパッケージ内で一意。log_idとmeasurement_session_idは全レコードでmanifestと一致させる。
- JSONLはUTF-8、空行禁止、1行1個の完全なJSONオブジェクトとする。
- PWM_STAGEは状態更新型レコードではない。1段階につき最終状態を表すPWM_STAGEレコードを1件だけ、段階終了または中断が確定した後に追記する。runningの暫定レコードは保存しない。
- 測定開始時に31件のPWM_STAGEを先行生成しない。到達した段階は完了/中断確定後に追記し、未到達段階は正常終了または制御された中断処理でnot_reachedと確定した後に追記する。
- 電源断・プロセスクラッシュ等で追記できなかった段階は、存在しないPWM_STAGE行を後から推測生成しない。manifestをincompleteとし、欠落段階は「未記録・状態不明」とする。存在しないレコードをnot_reachedと読み替えてはならない。
- manifestは測定終了時に一度確定する。測定中の暫定manifestは正本として扱わない。確定後に訂正が必要なら既存ファイルを上書きせず、訂正履歴を持つ新規ログを作成する。
- record_countsは確定したrecords.jsonlの全行を種別ごとに数えた値であり、抜粋数や予定数ではない。


## 3. manifest.json

### 3.1 必須項目

| field | type | 意味 |
|---|---|---|
| `schema_name` | string | 固定値 `mini4wd.rawlog` |
| `schema_version` | string | 固定値 `2.0.0` |
| `log_id` | string | RawLog一意ID |
| `measurement_session_id` | string | 310秒実測セッションID |
| `measurement_type` | string | 固定値 `PWM_START_SWEEP_310S` |
| `created_at_utc` | ISO-8601 UTC string | パッケージ確定時刻 |
| `started_at_utc` | ISO-8601 UTC string | 測定開始時刻 |
| `ended_at_utc` | ISO-8601 UTC string or null | 終了時刻。未終了ならnull |
| `status` | enum | `completed` / `aborted` / `incomplete` |
| `planned_stage_count` | integer | 固定値31 |
| `planned_stage_duration_ms` | integer | 固定値10000 |
| `planned_total_duration_ms` | integer | 固定値310000 |
| `motor_instance_id` | string or null | 対象Motor Instance。不明/未紐付けならnull |
| `device` | object | Arduino機器識別 |
| `measurement_conditions` | object | 方向、電圧制御モード等 |
| `record_counts` | object | レコード種別ごとの実件数 |

### 3.2 device

必須: `type`、`model`、`firmware_version`、`firmware_build`、`firmware_id`、`adc_resolution_bits`。

INFO応答に含まれる識別値を記録する。INFO行そのものはRawLog本文へ混入させない。値が取得できない場合は推測せずnullとし、manifestの `metadata_warnings` に理由を記録する。ADC raw値の上限は `adc_resolution_bits` から求める。

### 3.3 measurement_conditions

必須キー:
- `direction`: `FWD` / `REV` / `UNKNOWN`
- `voltage_control_mode`: `INPUT` / `TERMINAL` / `NOT_APPLICABLE` / `UNKNOWN`
- `sweep_pwm_min`: 0
- `sweep_pwm_max`: 30
- `stage_duration_ms`: 10000
- `schedule_owner`: 固定値 `PYTHON`

方向・制御モードは実際に設定した値を記録する。UNKNOWNを既定値として推定解釈してはならない。V4/V5の意味は方向とINPUT/TERMINALの組合せを保持したうえで、後段Python解析で解釈する。RawLog保存時にV4/V5を入れ替えたり差分へ潰したりしない。

## 4. records.jsonl 共通エンベロープ

すべてのレコードに以下を必須とする。

| field | type | 意味 |
|---|---|---|
| `schema_version` | string | `2.0.0` |
| `record_type` | string | 下記のレコード種別 |
| `record_id` | string | パッケージ内一意ID |
| `record_seq` | integer | Python付与の書込順 |
| `log_id` | string | manifestと一致 |
| `measurement_session_id` | string | manifestと一致 |
| `recorded_at_utc` | ISO-8601 UTC string | Pythonがレコード化した時刻 |

時刻はUTC表記（末尾Z）とする。Arduinoの `micros()` とPythonの時計を同一時計とみなさない。時刻の対応付けには後述の個別デバイス時刻とホスト受信時刻を併記する。

## 5. レコード種別

### 5.1 SESSION_EVENT

測定開始・終了・中断・異常等のライフサイクルイベント。

追加必須:
- `event`: `SESSION_STARTED` / `SESSION_COMPLETED` / `SESSION_ABORTED` / `COMMUNICATION_LOST` / `STOP_REQUESTED` / `DEVICE_STATE_REPORTED` / `OTHER`
- `host_monotonic_ns`: Pythonの単調時計値
- `details`: object。イベント固有情報。不要なら空object

コマンド送信・ACK・デバイス状態報告は区別して記録する。STOP_REQUESTEDは物理停止確認を意味しない。停止状態の確認結果が得られた場合のみ、別のDEVICE_STATE_REPORTED等でその根拠を記録する。

### 5.2 PWM_STAGE

PWM 0～30の各段階について、段階ごとに最終状態のレコードを1件だけ追記する。暫定runningレコードを作成・更新する方式は禁止する。

追加必須:
- stage_id: 一意。規則PWM-00～PWM-30
- stage_index: 整数0～30
- pwm_command: 整数0～30。stage_indexと同値
- planned_duration_ms: 固定値10000
- stage_status: completed / aborted / not_reached のいずれか。保存されるPWM_STAGEにrunning / not_startedは存在しない
- started_at_utc, ended_at_utc: Pythonが段階の実行開始/終了を認識したUTC時刻。未到達段階は両方null
- start_host_monotonic_ns, end_host_monotonic_ns: 同じPython単調時計ドメインの値。未到達段階は両方null
- actual_duration_ms: 実行段階の実経過時間。未到達段階はnull。abortedでは中断までの実経過時間
- pwm_command_sent_at_utc: 指令送信時刻。未到達段階はnull
- pwm_applied_ack_received_at_utc: Arduinoから当該PWMとcontextの適用ACKをPythonが受信した時刻。ACKなしならnull
- output_state: reported_on / reported_off / unknown。コマンドACKだけから物理出力状態を推定しない
- stage_context_id: Pythonが段階ごとに生成する一意な不透明ID
- termination_reason: duration_elapsed / user_stop / safety_stop / communication_lost / process_interrupted / not_started_after_abort / other。実行段階の理由。completedではduration_elapsed、not_reachedではnot_started_after_abort

**段階レコードの確定・追記手順**
1. Pythonは段階開始前に一意なstage_context_idを生成し、そのPWM指令と一緒にArduinoへ送る。
2. ArduinoがPWM指令とstage_context_idを適用したことをACKし、PythonがACKを受信した時点をPython側の段階開始認識時刻とする。ACKが得られない場合、段階開始・出力適用を確定扱いせず、測定を中断側へ倒す。コマンド送信時刻とACK受信時刻は別々に保持する。
3. PythonはACK受信時刻を基準に予定10,000msを計時し、段階終了指令または停止要求を発行する。次段階へ移るときも新しいcontext IDを発行する。実測時間はPythonの単調時計で実際に計測した値を記録し、10,000msに丸めない。
4. 段階の終了/中断が確定した後、PythonがPWM_STAGE最終レコードを1件だけJSONL末尾へ追記する。保存後に同じstage_idの状態を更新する行は追加しない。
5. 正常完了時は31段階すべてをcompletedとして記録する。制御された中断時は実行中段階をaborted、以降の未開始段階をそれぞれnot_reachedとして追記する。既に完了した段階は変更しない。
6. クラッシュ等で中断処理・未到達段階の追記ができなかった場合は、manifest.status=incompleteとし、存在しないstageレコードを補作しない。検証側は31件不足を検出し「未記録・状態不明」と報告する。

段階時刻の意味:
- started_at_utc / start_host_monotonic_nsは、適用ACKをPythonが受信した時刻であり、Arduino内部のPWM更新時刻そのものではない。
- pwm_applied_ack_received_at_utcはArduinoがPWM指令とcontext IDを適用した旨を返したACKのホスト受信時刻。ACKの意味は「FW内部の指令・context更新完了」であり、負荷端子の物理出力を計測・証明した意味ではない。
- ended_at_utc / end_host_monotonic_nsはPythonが次段階への切替または停止を認識した時刻。実際の電気的な出力変化時刻と同一と断定しない。
- 予定310,000msはスケジュール値であり、実測合計が310,000msと一致する保証はない。遅延・ACK待ち・中断を実値で残す。


### 5.3 ADC_SAMPLE

**ADC_SAMPLE 1レコードにつきADC 1変換のみ**を記録する。A0/A1/A4/A5を1つの同時刻サンプルへ束ねない。A2/A3を記録する場合も同じ形式を使用する。

追加必須:
- `sample_id`: 一意な取得ID
- `channel`: `A0` / `A1` / `A2` / `A3` / `A4` / `A5`
- `sensor`: センサー識別子
- `signal_role`: `winding_current` / `brush_stability_observation` / `magnetic_reference` / `thermistor_reference` / `voltage_v4` / `voltage_v5`
- `adc_raw`: ADC整数値。取得失敗時はnull
- `adc_resolution_bits`: ADC分解能
- `raw_unit`: 固定値 `count`
- `device_timestamp_us_u32`: 当該analogRead変換の個別時刻（uint32、Arduino micros基準）。取得失敗時はnull
- `device_timestamp_point`: `conversion_midpoint`。analogRead開始直前と終了直後のmicros値から中点を求める。取得実装が中点を保証できない場合は実際のtimestamp_pointを明示する
- `device_epoch_id`: デバイス起動区間ID。再起動・時刻リセット時に新しいIDとする
- `device_elapsed_us`: Pythonが同一device_epoch内でunwrapした単調時刻（uint64相当）。算出不能ならnull
- `device_sample_sequence`: Arduinoが付与する単調増加サンプル連番。FWが提供しない場合はnull
- `host_received_at_utc`: Pythonが当該データを受信したUTC時刻
- `host_received_monotonic_ns`: Python単調時計での受信時刻
- `stage_context_id`: ADC変換開始直前にArduinoがactive contextからローカルへスナップショットした相関ID。取得できなければnull。後続送信時に現在IDで上書き禁止
- `stage_id`: 対応するPWM_STAGEのID。解決できなければnull
- `stage_assignment`: `confirmed` / `unresolved`
- `calibration_id`: 適用可能な校正スナップショットID。なければnull
- `validity`: `valid` / `invalid` / `unavailable`
- `invalid_reason`: 無効・欠損理由。validならnull

センサー定義:

| channel | sensor | signal_role | rawの意味 | 換算 |
|---|---|---|---|---|
| A0 | ACS712 #1 | winding_current | 巻線電流測定用ADC raw | A0専用校正情報が揃う場合のみAへ換算可 |
| A1 | ACS712 #2 | brush_stability_observation | ブラシ安定性の独立観測raw | 電流Aへ換算しない。A0と平均・代用しない |
| A2 | magnetic_sensor | magnetic_reference | 磁気センサーraw | 参考値。換算する場合も参考値として明示 |
| A3 | thermistor | thermistor_reference | サーミスタraw | 参考値。校正済み温度換算がなければADC countのみ |
| A4 | voltage_input_v4 | voltage_v4 | V4電圧入力ADC raw | A4専用校正情報が揃う場合のみVへ換算可 |
| A5 | voltage_input_v5 | voltage_v5 | V5電圧入力ADC raw | A5専用校正情報が揃う場合のみVへ換算可 |

`converted_value` と `converted_unit` は任意。記録する場合は、同じレコードの `calibration_id` と校正レコードを必ず参照し、計算式・係数・単位を明示する。A0電流換算はA0 rawとA0校正だけを使う。A1を電流へ換算しない。A2/A3の換算値は参考値属性を保持し、判定や制御へ流用しない。A4/A5は各チャンネル個別の換算値を保持し、差分電圧等の派生値で置き換えない。

各チャンネルの取得周期は実装・実機で確定した値を記録する。固定周期を仮定しない。周期情報を持たせる場合は `sampling_profile_id` または測定条件の `sampling_observed` に実測周期・測定方法を保存する。取得順序が逐次である場合も、各変換の個別timestampを保持する。

欠損/異常表現:
- 取得成功: `validity="valid"`、整数 `adc_raw`、timestampあり。
- 取得失敗: `validity="unavailable"`、`adc_raw=null`、timestamp=null、理由必須。
- 範囲外/形式不正: `validity="invalid"`、raw値は取得した原値を保持できる場合のみ保持し、理由必須。
- ADC raw=0は有効な数値になり得るため欠損表現に使わない。
- 欠落チャンネルを別チャンネル・前回値で補完しない。任意のA2/A3欠落を測定全体の失敗条件にしない。

### 5.4 CALIBRATION

CALIBRATIONは校正・基準情報の取得記録であり、未確認のCAL行フォーマットを独自に解析・命名しない。FWからCAL行を受信した場合は、受信原文をraw_lineに一字一句そのまま保存する。

必須フィールド:
- calibration_id: パッケージ内一意ID
- source: firmware_CAL_line / host_calibration / manual_calibration
- raw_line: FW CAL行の原文。firmware_CAL_lineでは必須。その他sourceではnull可
- captured_at_utc: Pythonが当該校正情報を受信/取得したUTC時刻
- captured_host_monotonic_ns: 同時点のPython単調時計値
- effective_from_event_id: 適用開始を示すイベントID。未確定ならnull
- effective_until_event_id: 適用終了を示すイベントID。未確定ならnull
- channels: 固定キーA0/A1/A4/A5を持つobject。値が不明でもキーは省略せず、状態を明示する

channelsのv2構造（現時点でraw-only）:

```json
{
  "A0": {
    "signal_role": "winding_current",
    "calibration_role": "winding_current_zero_reference",
    "parameter_status": "raw_only_unparsed",
    "parameters": null
  },
  "A1": {
    "signal_role": "brush_stability_observation",
    "calibration_role": "brush_observation_reference",
    "parameter_status": "raw_only_unparsed",
    "parameters": null
  },
  "A4": {
    "signal_role": "voltage_v4",
    "calibration_role": "voltage_input_reference",
    "parameter_status": "raw_only_unparsed",
    "parameters": null
  },
  "A5": {
    "signal_role": "voltage_v5",
    "calibration_role": "voltage_input_reference",
    "parameter_status": "raw_only_unparsed",
    "parameters": null
  }
}
```

- parameter_statusは現行CAL原文の実フィールド構造と単位を確認できていないため、310-1では固定値raw_only_unparsedとする。parametersはnull。数値・係数・単位を推測して入れてはならない。
- A0は巻線電流のゼロ基準情報の対象であることだけを示す。実際のゼロオフセット値・換算係数・算出式は、現行FWのCAL出力仕様を照合して司令塔が確定するまで構造化しない。
- A1はブラシ安定性の独立観測基準だけを示す。A1に電流換算係数、A単位の値、A0補正値を持たせない。A1基準値をA0に適用しない。
- A4/A5は個別の電圧入力参照情報として区別する。未確認の分圧比・係数・オフセットは記録しない。
- CAL行がチャンネル別か複数チャンネルを含むかを確定できない場合、raw_lineはCAL行全体を保持し、個別チャンネルへの原文割当は推測しない。4チャンネルのparameter_statusはraw_only_unparsedのままとする。
- 将来CAL構造を解析可能になった場合はschema_versionを変更するか、後方互換性を検証した上で明示的なschema改訂を行う。既存raw_lineを消去・上書きしない。
- 校正情報が欠落・不明の場合、推定値で補完しない。ADC_SAMPLEのcalibration_idはnullとし、raw ADCだけを保存する。校正未確認を理由にraw取得値を削除しない。


### 5.5 EVENT

EVENTはユーザー注釈・目視観測・測定上の事象を記録する。自動判定と人による観測を別のevent値・methodで識別する。

**回転開始を目視確認したイベント**
- event: 固定値ROTATION_START_CONFIRMED
- observation_method: 固定値human_visual
- actor: userまたは入力者識別子
- observed_at_utc: 人が回転を確認したと判断した時刻
- reported_at_utc: Python UI等へ報告を入力した時刻
- host_monotonic_ns: reported_atに対応するPython単調時計値
- stage_id: 回転開始と判断したPWM段階ID
- stage_index: 0～30
- pwm_value: 回転開始と判断したPWM値。対応するPWM_STAGEのpwm_commandと一致必須
- note: 任意注記
- external_rpm: 任意の参考RPM object。値・単位rpm・取得方法・取得元を含む。推定や自動回転判定の根拠にはしない

このイベントは「回転開始を確認した」という肯定イベントであり、NO_ROTATION / UNKNOWNラベルを持たない。回転開始を確認できていない観測を記録する場合は別event ROTATION_NOT_OBSERVED_AT_STAGEとし、observed_at_utc、reported_at_utc、stage_id、stage_index、pwm_value（観測時点の段階PWM）、actor、observation_method=human_visual、任意noteを記録する。この否定観測は回転開始PWMを意味せず、後から肯定イベントへ読み替えない。

ROTATION_START_CONFIRMED.pwm_valueは「報告入力時の現在PWM」ではなく、ユーザーが回転開始と判断したPWM段階の指令値である。stage_idとstage_indexは同一のPWM_STAGEを指し、pwm_valueはそのpwm_commandと一致しなければならない。観測時刻と報告時刻が異なる場合も両方を保持し、報告時刻からstageを逆算しない。stageを確定できない場合はstage_id/stage_index/pwm_valueをnullとし、回転開始PWMが未確定であることを保持する。

目視ラベルは任意記録であり、測定の必須条件ではない。A2/A3からEVENTを自動生成しない。外部RPMは参考値で、正式なRPM入力・回転自動判定には使用しない。


### 5.6 DERIVED（任意・将来用）

310-1では計算式や推定アルゴリズムを確定しない。将来Derived値を保存する場合のみ使用する。

必須: `metric`、`algorithm_id`、`algorithm_version`、`input_sample_ids`、`value`、`unit`、`valid`、`invalid_reason`。無効値はnullと理由を持つ。生データへDerived値を混ぜない。A2/A3を入力に含めることは禁止（用途別に司令塔承認されるまで）。

## 6. PWM段階とサンプルの対応

| stage_index | pwm_command | planned duration | planned elapsed |
|---:|---:|---:|---:|
| 0 | 0 | 10 s | 0–10 s |
| 1 | 1 | 10 s | 10–20 s |
| … | … | … | … |
| 30 | 30 | 10 s | 300–310 s |

### 6.1 context IDの発行・有効化境界

1. Pythonが段階ごとに新しい一意のstage_context_idを発行し、PWM指令と同じコマンド単位でArduinoへ送る。IDは段階開始後に再利用しない。
2. Arduinoは指令を受理しただけではactive contextを変更しない。指令の検証後、PWM出力レジスタ/指令値を更新する処理とactive stage_context_idの更新を、同一のコマンド処理境界で連続して実行し、その処理完了後にACKする。ACKは「FW内部でPWM指令値とIDを適用した」ことを示す。
3. ここでいう出力更新はFW内部のPWM指令値の更新を指す。負荷端子で物理的に所定電圧・電流が成立したことの証明ではない。物理出力状態は別の測定・状態報告として扱う。
4. Arduinoは各ADC変換の直前、analogRead開始前にactive stage_context_idをローカル変数へコピーする。その後にADC変換を行い、raw値・ADC timestamp・コピー済みIDを1つのsample recordとして確定する。
5. sample recordのIDはADC変換開始時にスナップショットし、変換終了後・送信キュー投入後・シリアル送信時にグローバルactive IDを再参照してはならない。送信待ちバッファ内のサンプルは、後続段階のPWM指令・ID更新によって変更されない。
6. PWM/context更新とADC開始が同一処理境界で競合しないよう、FW内で直列化する。ADC変換開始が更新処理より前なら旧ID、更新処理完了後なら新IDを固定する。中間状態やPWMとIDの不一致状態をサンプルに付与しない。
7. PWM 0の段階も同じ規則で新しいcontext IDを適用する。起動時/段階前など、段階に属さないサンプルはcontext ID=null、stage_id=null、stage_assignment=unresolvedとする。
8. Pythonは受信サンプルのIDとPWM_STAGEのIDを照合する。一致時のみstage_assignment=confirmed。未知ID、欠落、不一致はunresolvedとし、受信時刻や予定elapsedから段階を推測しない。

### 6.2 310秒段階進行と時間

- Pythonだけがstage_index 0～30を順番に進める。Arduinoに310秒タイマーや自動段階進行を実装しない。
- 各段階の予定時間は10,000ms。Pythonは適用ACKを受信した時刻を段階開始認識時刻として計時する。
- Pythonが10,000ms経過後に次段階の指令を発行する。実際の段階時間はACK待ち・ホスト遅延・停止処理等により予定値と異なり得るため、実測値をそのまま保存する。
- 段階の境界はcontext IDで識別する。ホスト受信時刻だけでADC_SAMPLEの所属段階を決定しない。
- 正常完了時はPWM_STAGE 31件すべてcompleted。制御された中断時は完了済み段階を保持し、実行中段階をaborted、後続をnot_reachedとして各1件追記する。
- プロセスクラッシュ等で最終状態レコードを追記できなかった段階は状態不明として欠落のまま残し、manifest.status=incompleteとする。not_reachedは実際にPythonが未開始を確定して追記できた段階に限る。


## 7. 回転前後の比較

比較はEVENTで記録された目視回転開始PWMとPWM_STAGE/ADC_SAMPLEの関連から後段で行う。

- 回転開始前: `stage_index < rotation_start_stage_index`
- 回転開始段階: `stage_index = rotation_start_stage_index`
- 回転開始後: `stage_index > rotation_start_stage_index`

段階内の比較が必要な場合は、ADC_SAMPLEの個別デバイス時刻とPythonの段階開始/終了時刻、およびstage_context_idを使う。回転イベント時刻とADC取得時刻を混同しない。イベントが記録されていない測定は、回転開始PWMを推測しない。自動判定アルゴリズムは本仕様の範囲外。

## 8. 校正・換算・品質

- Raw ADC値は常に第一級データとして保存する。
- 換算値は校正ID・式・係数・単位が追跡可能な場合のみ保存する。
- A0換算はA0だけ、A4換算はA4だけ、A5換算はA5だけで行う。
- A1は独立観測rawとして保存し、A0電流値と混合しない。
- A2/A3はreferenceとして明示し、参考値以外の用途に使わない。
- 取得失敗、パース失敗、時刻unwrap失敗、校正欠落、段階紐付け不能はそれぞれ理由を記録する。
- ログの品質・採否をA2/A3の存在・値・妥当性に依存させない。
- ADC値の上限・単位・換算式が未確定ならrawだけを保存し、確定値を捏造しない。

## 9. 時刻モデル

3つの時計を区別する。

1. Arduino `device_timestamp_us_u32`: analogReadごとの取得時刻。32bit microsカウンタ値を保持し、`device_epoch_id` で起動区間を識別する。
2. Python `host_received_monotonic_ns`: USB受信時刻。段階開始/終了と同じPython単調時計ドメイン。
3. Python `*_at_utc`: 外部表示・監査用のUTC壁時計。

Arduino microsは約71.6分でwrapする。Pythonは同一デバイス起動区間でのみwrapをunwrapし、元のuint32値を必ず残す。デバイス再起動や時刻逆行が検出された場合は新しいdevice_epochとして区別し、時刻を連続していたかのように補正しない。ホスト受信時刻はADC取得時刻ではない。受信時刻を個別ADC timestampの代替にしない。

## 10. JSONサンプル

### 10.1 manifest.json

```json
{
  "schema_name": "mini4wd.rawlog",
  "schema_version": "2.0.0",
  "log_id": "MOTOR-310-000001",
  "measurement_session_id": "310S-20261101-0001",
  "measurement_type": "PWM_START_SWEEP_310S",
  "created_at_utc": "2026-11-01T01:10:10.000Z",
  "started_at_utc": "2026-11-01T01:05:00.000Z",
  "ended_at_utc": "2026-11-01T01:10:10.000Z",
  "status": "completed",
  "planned_stage_count": 31,
  "planned_stage_duration_ms": 10000,
  "planned_total_duration_ms": 310000,
  "motor_instance_id": "7",
  "device": {
    "type": "MOTOR",
    "model": "MOTOR_BREAKIN_V3",
    "firmware_version": "3.x",
    "firmware_build": "build-id-from-INFO",
    "firmware_id": "000001",
    "adc_resolution_bits": 10
  },
  "measurement_conditions": {
    "direction": "FWD",
    "voltage_control_mode": "INPUT",
    "sweep_pwm_min": 0,
    "sweep_pwm_max": 30,
    "stage_duration_ms": 10000,
    "schedule_owner": "PYTHON"
  },
  "record_counts": {
    "SESSION_EVENT": 2,
    "PWM_STAGE": 31,
    "ADC_SAMPLE": 124,
    "CALIBRATION": 1,
    "EVENT": 1
  }
}
```

### 10.2 records.jsonl（抜粋。各JSONオブジェクトを1行で保存）

```json
{"schema_version":"2.0.0","record_type":"PWM_STAGE","record_id":"rec-stage-00","record_seq":2,"log_id":"MOTOR-310-000001","measurement_session_id":"310S-20261101-0001","recorded_at_utc":"2026-11-01T01:05:10.000Z","stage_id":"PWM-00","stage_index":0,"pwm_command":0,"planned_duration_ms":10000,"stage_status":"completed","started_at_utc":"2026-11-01T01:05:00.000Z","ended_at_utc":"2026-11-01T01:05:10.000Z","start_host_monotonic_ns":5000000000,"end_host_monotonic_ns":15000000000,"actual_duration_ms":10000,"pwm_command_sent_at_utc":"2026-11-01T01:05:00.000Z","pwm_acknowledged_at_utc":"2026-11-01T01:05:00.010Z","output_state":"unknown","stage_context_id":"ctx-000"}
{"schema_version":"2.0.0","record_type":"ADC_SAMPLE","record_id":"rec-a0-001","record_seq":3,"log_id":"MOTOR-310-000001","measurement_session_id":"310S-20261101-0001","recorded_at_utc":"2026-11-01T01:05:00.025Z","sample_id":"sample-a0-001","channel":"A0","sensor":"ACS712 #1","signal_role":"winding_current","adc_raw":512,"adc_resolution_bits":10,"raw_unit":"count","device_timestamp_us_u32":12345678,"device_timestamp_point":"conversion_midpoint","device_elapsed_us":12345678,"host_received_at_utc":"2026-11-01T01:05:00.025Z","host_received_monotonic_ns":5025000000,"stage_context_id":"ctx-000","stage_id":"PWM-00","stage_assignment":"confirmed","calibration_id":"cal-a0-01","validity":"valid","invalid_reason":null}
{"schema_version":"2.0.0","record_type":"ADC_SAMPLE","record_id":"rec-a1-001","record_seq":4,"log_id":"MOTOR-310-000001","measurement_session_id":"310S-20261101-0001","recorded_at_utc":"2026-11-01T01:05:00.026Z","sample_id":"sample-a1-001","channel":"A1","sensor":"ACS712 #2","signal_role":"brush_stability_observation","adc_raw":509,"adc_resolution_bits":10,"raw_unit":"count","device_timestamp_us_u32":12346700,"device_timestamp_point":"conversion_midpoint","device_elapsed_us":12346700,"host_received_at_utc":"2026-11-01T01:05:00.026Z","host_received_monotonic_ns":5026000000,"stage_context_id":"ctx-000","stage_id":"PWM-00","stage_assignment":"confirmed","calibration_id":"cal-a1-01","validity":"valid","invalid_reason":null}
{"schema_version":"2.0.0","record_type":"ADC_SAMPLE","record_id":"rec-a4-001","record_seq":5,"log_id":"MOTOR-310-000001","measurement_session_id":"310S-20261101-0001","recorded_at_utc":"2026-11-01T01:05:00.027Z","sample_id":"sample-a4-001","channel":"A4","sensor":"voltage_input_v4","signal_role":"voltage_v4","adc_raw":620,"adc_resolution_bits":10,"raw_unit":"count","device_timestamp_us_u32":12347800,"device_timestamp_point":"conversion_midpoint","device_elapsed_us":12347800,"host_received_at_utc":"2026-11-01T01:05:00.027Z","host_received_monotonic_ns":5027000000,"stage_context_id":"ctx-000","stage_id":"PWM-00","stage_assignment":"confirmed","calibration_id":"cal-v4-01","validity":"valid","invalid_reason":null}
{"schema_version":"2.0.0","record_type":"ADC_SAMPLE","record_id":"rec-a5-001","record_seq":6,"log_id":"MOTOR-310-000001","measurement_session_id":"310S-20261101-0001","recorded_at_utc":"2026-11-01T01:05:00.028Z","sample_id":"sample-a5-001","channel":"A5","sensor":"voltage_input_v5","signal_role":"voltage_v5","adc_raw":101,"adc_resolution_bits":10,"raw_unit":"count","device_timestamp_us_u32":12348900,"device_timestamp_point":"conversion_midpoint","device_elapsed_us":12348900,"host_received_at_utc":"2026-11-01T01:05:00.028Z","host_received_monotonic_ns":5028000000,"stage_context_id":"ctx-000","stage_id":"PWM-00","stage_assignment":"confirmed","calibration_id":"cal-v5-01","validity":"valid","invalid_reason":null}
{"schema_version":"2.0.0","record_type":"EVENT","record_id":"rec-rotation-01","record_seq":100,"log_id":"MOTOR-310-000001","measurement_session_id":"310S-20261101-0001","recorded_at_utc":"2026-11-01T01:05:42.500Z","event":"ROTATION_OBSERVED","observation_method":"human_visual","actor":"user","observed_at_utc":"2026-11-01T01:05:42.500Z","host_monotonic_ns":47500000000,"stage_id":"PWM-04","pwm_value":4,"observation_label":"ROTATION","note":"目視で回転開始を確認","external_rpm":null}
```

上記は構造例であり、raw ADC値・時刻・motor instance・FW識別値は実測結果を表さない。manifestのrecord_countsも構造説明用の例示値であり、サンプリング周期・実際の取得件数を規定しない。record_seq 1のSESSION_EVENT、CALIBRATION本体、残り段階・サンプルは説明簡略化のため省略している。

## 11. 旧RawLog v1との互換性境界

- v1はlegacyとして原本を不変保全する。
- v2は独立形式。26列、列順、旧列名、旧derived値を引き継がない。
- v1からv2への自動変換・推測変換・再分類・互換レイヤーは作らない。
- `current1`、`current2`、`current_avg`、`magnetic_level`、`motor_temperature`、`brush_peak_current`等は、現行の意味を保証しないためv2の必須項目にしない。
- 旧ログを解析に使う場合は、取得当時の仕様・配線に基づくlegacyデータとして別扱いにする。現行センサー意味を遡及適用しない。
- v2の `schema_version` とv1の識別は明示し、ファイル名や列数だけで推測しない。

## 12. Issue #35との整合・判断理由

| 設計判断 | 根拠・理由 |
|---|---|
| v1と独立したJSONLパッケージ | Issue #35 3.4。具体的な保存形式・レコード分割は本設計で定義 |
| A0とA1を別ADC_SAMPLEに分離 | Issue #35 3.1。意味・時刻・校正・解析の独立、平均/代用禁止 |
| A4とA5を別サンプル・raw値で保持 | Issue #35 3.1/3.2。方向・INPUT/TERMINALによる意味解釈を後段へ残す |
| A2/A3をreferenceとして任意記録 | Issue #35 3.1。承認前は制御・判定・品質・採否・Derived推定に不使用 |
| 個別ADC timestamp | Issue #35 3.2、Issue #170追補、PR #169の取得時刻設計を参照。PR #169は部品であり統合済みとはみなさない |
| Python管理の31 PWM段階 | Issue #35 3.3。Arduinoに310秒の進行管理を持たせない |
| stage_context_idを相関キーに採用 | USB受信遅延時もサンプル取得時点の段階を確定するため。Arduinoは不透明IDをエコーするだけ |
| 目視回転イベントを任意EVENTにする | Issue #35 3.2およびIssue #170の2026-10-31合意。常設必須項目・自動判定としない |
| CAL原文をCALIBRATION recordに保持 | Issue #35 6。受信原文をRawLog本文内に保持し、A0/A1校正を分離 |
| Derivedは任意の別record | Issue #35 3.2。生データに推定値を混入せず、計算式未確定のため310-1では算出しない |

## 13. 310-2向け実装要件（設計からの要求）

1. manifestとrecords.jsonlを上記必須フィールド・型・enumに従って保存・再読込できること。
2. log_id/session ID不一致、record_id重複、record_seq逆行、JSON不正、型・範囲不正を拒否すること。
3. PWM_STAGEを0～30の31段階として扱い、各段階の予定10,000msと実際の経過時間を分離すること。
4. ADC_SAMPLEは1変換1レコードで、A0/A1/A4/A5の各raw値とtimestampを独立保持すること。
5. stage_context_idによる確定紐付けを行い、欠落時に受信時刻だけで推測割当しないこと。
6. 欠損・invalidを0や前回値で埋めないこと。A2/A3の欠落を必須測定欠損として扱わないこと。
7. CAL原文とチャンネル別校正値を保持し、A0/A1の校正・換算を混同しないこと。
8. 任意の目視EVENTを保存できること。イベントがない測定も正常なRawLogとして保存できること。
9. v1の読み込み・保存経路を破壊せず、v1をv2へ自動変換しないこと。
10. Pythonの段階管理とArduinoの指令実行を分離し、コマンド送信を出力確認と扱わないこと。

## 14. 310-1の範囲外・未確定

- Python保存処理、バリデーター、310秒シーケンス、FW、UI、回転自動判定、巻線抵抗算出、実機通電試験は本工程では実装しない。
- Arduinoの通信フレーム詳細（区切り文字、wire field名、シリアルレコード頻度）は本設計のRawLog保存形式とは別契約であり、310-2/後続FW工程でIssue #35に従い定義する。
- `stage_context_id` のFWエコーは段階とサンプルを確実に結び付けるための必要な通信要件である。現行FWで実装済みとはみなさない。
- A2/A3の実用換算式、A1の電流換算、未承認の電流/電圧換算係数、サンプリング周期、許容skew、回転判定式は確定しない。
- 独立ハードウェア電流制限・物理OFFの確認はRawLog設計では代替できない。実機通電可否は司令塔の別判断とする。

---

**310-1担当の状態:** 設計案。司令塔の受入確認前。  
**実装・テスト:** 未実施。  
**実機確認:** 未実施。
