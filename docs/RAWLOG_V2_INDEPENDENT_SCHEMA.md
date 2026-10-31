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

- `manifest.json`: 測定全体の識別、条件、開始/終了、機器・FW識別、記録件数、完了状態。
- `records.jsonl`: 1行1JSONオブジェクト。測定イベント、PWM段階、ADC取得、校正スナップショット、任意注釈、任意Derivedを時系列で記録する。
- JSONLの各行は独立してパース可能なUTF-8 JSONとする。空行は禁止。
- `record_seq` はPythonが付与するパッケージ内の単調増加整数。各レコードの書込み順を示すものであり、ADC取得時刻の代用ではない。
- `record_id` はパッケージ内で一意な文字列。UUID等を使用する。
- `log_id` と `measurement_session_id` は全レコードで同一の測定を指す。別概念として保持する。
- 保存後の原本レコードは変更しない。訂正が必要な場合は新規訂正イベントまたは新規ログを作り、既存レコードを上書きしない。
- `manifest.json` は測定終了時に確定する。中断・異常終了時も、得られた範囲を `aborted` / `incomplete` として保存する。

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

PWM 0～30の各段階について、段階ごとに1レコードを作る。予定31段階すべてを表現し、未到達段階も `not_started` として表現可能にする。

追加必須:
- `stage_id`: 一意な文字列（例 `PWM-00` ～ `PWM-30`）
- `stage_index`: 0～30
- `pwm_command`: 0～30
- `planned_duration_ms`: 10000
- `stage_status`: `not_started` / `running` / `completed` / `aborted` / `not_reached`
- `started_at_utc`, `ended_at_utc`: UTC時刻またはnull
- `start_host_monotonic_ns`, `end_host_monotonic_ns`: Python単調時計値またはnull
- `actual_duration_ms`: 実測経過時間。未開始ならnull
- `pwm_command_sent_at_utc`: コマンド送信時刻またはnull
- `pwm_acknowledged_at_utc`: Arduino応答を受信した時刻またはnull
- `output_state`: `reported_on` / `reported_off` / `unknown`
- `stage_context_id`: Pythonが発行する不透明な相関ID

段階開始・終了時刻はPythonの実際の遷移時刻を記録する。予定値を実測時刻として書かない。310秒は予定合計であり、実測が310000msと一致することを保証しない。遅延、欠落、中断があれば実際の値を残す。

Arduinoは `stage_context_id` をPWM指令に付随する不透明な識別子として保持し、当該指令後のサンプルにエコーする。ArduinoはIDを解釈せず、310秒の段階進行・時間管理を行わない。これによりUSB受信遅延が段階境界を跨いでも、サンプルの取得時点に対応する段階を識別できる。エコーがないサンプルは段階を推測せず `stage_id: null` とし、`stage_assignment: "unresolved"` とする。

PWM指令値は設定要求であり、実際の出力状態の証明ではない。ACK受信、出力状態報告、物理停止確認は別々に記録する。

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
- `device_timestamp_point`: `conversion_midpoint`。時刻取得ヘルパーが変換前後を記録する場合の中点
- `device_elapsed_us`: Pythonが同一デバイス起動区間内でunwrapした単調時刻（uint64相当）。算出不能ならnull
- `host_received_at_utc`: Pythonが当該データを受信したUTC時刻
- `host_received_monotonic_ns`: Python単調時計での受信時刻
- `stage_context_id`: Arduinoがエコーした相関ID。取得できなければnull
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

校正値の取得・適用区間を記録する。CAL受信行がある場合は、受信した原文を `raw_line` に一字一句そのまま保持する。CALを単なる外部メタデータへ移し、RawLog本文から消してはならない。

追加必須:
- `calibration_id`
- `source`: `firmware_CAL_line` / `host_calibration` / `manual_calibration`
- `raw_line`: CAL行原文。該当しないsourceではnull可
- `captured_at_utc`
- `effective_from_event_id` / `effective_until_event_id`: 適用区間を示すIDまたはnull
- `channels`: チャンネルごとの校正情報オブジェクト

A0とA1の校正情報は別々のchannel keyで保持する。A0のゼロオフセット・換算係数だけをA0電流換算に使用する。A1の基準値はA1独立観測用であり、A0の補正・換算に使用しない。A1の電流換算係数を作らない。A4/A5も別々の校正情報を持つ。

校正値が欠落・不明の場合、推定値で補完しない。該当する換算値を出さずraw ADCを保存する。駆動中に校正値が更新されたと仮定しない。測定中の適用校正が不明なら `calibration_id=null` とし、その旨を品質情報に残す。

### 5.5 EVENT

ユーザー注釈、目視観測、測定上の事象を任意に記録する。自動判定結果とユーザー目視報告は別のrecord_type/actorで識別する。

回転目視イベントの追加項目:
- `event`: `ROTATION_OBSERVED`
- `observation_method`: 固定値 `human_visual`
- `actor`: `user` または入力者識別子
- `observed_at_utc`: 目視確認を記録した時刻
- `host_monotonic_ns`
- `stage_id`: 対応段階。対応不能ならnull
- `pwm_value`: 回転開始と判断したPWM値（0～30）。回転開始の目視確認があった場合に必須
- `observation_label`: `ROTATION` / `NO_ROTATION` / `UNKNOWN`
- `note`: 任意のユーザー注記
- `external_rpm`: 任意の参考値。単位rpm、取得元・方法を併記する

回転開始PWMはユーザーの目視報告を正とする。自動センサー判定と混同しない。A2の磁気値やA3温度から回転イベントを生成しない。目視ラベルはIssue #170の2026-10-31合意に従い、必要な検証測定でのみ任意記録する。常設必須項目にはしない。回転ありログも削除・棄却しない。

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

- Pythonがstage_index 0から30を順に管理する。
- 各段階の予定時間は10,000ms。実際の開始・終了はPython単調時計で記録する。
- 段階境界は実際のPython遷移時刻を基準とする。予定経過時間だけから実測段階を推定しない。
- Pythonは各段階のPWM指令に一意の `stage_context_id` を付ける。Arduinoは現在の指令コンテキストをサンプルにエコーするだけで、段階のタイマーや進行ロジックを持たない。
- サンプルの `stage_context_id` がPWM_STAGEの `stage_context_id` と一致した場合のみ `stage_assignment="confirmed"` とする。
- コンテキストが欠落・不一致の場合は段階未解決とし、受信時刻だけで強制割当しない。
- 段階0（PWM 0）も10秒間の段階として記録する。
- 途中停止時は未到達段階を `not_reached`、実行中段階を `aborted` とし、存在しないサンプルを生成しない。

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

1. Arduino `device_timestamp_us_u32`: analogReadごとの取得時刻。32bit microsカウンタ値を保持。
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
