# Motor RawLog Correspondence Reference

**Purpose:** Shared reference for identifying what each known motor RawLog corresponds to. This file is a traceability index, not a calculation specification.
**Status:** Compiled on 2026-10-09 from the project's recorded context and current repository specifications. Entries are explicitly marked as known, tentative, or needing source-log verification.
**Authority:** The raw time-series and its linked Measurement Session are the source of truth. This index must not be used to invent missing session IDs, timestamps, or benchmark conditions.

## 1. How to interpret a motor RawLog

A RawLog should be read using the following identity chain:

```text
Motor Instance (individual physical motor)
  └─ Measurement Session (one execution)
       ├─ benchmark type / voltage-control mode (when available)
       ├─ purpose (benchmark, break-in/conditioning, etc., when available)
       └─ RawLog (original time-series data)
```

Keep these identities separate:

- **Motor model/type:** what kind of motor it is (master/reference data).
- **Motor Instance:** the individual physical motor being tested.
- **RawLog / log ID:** one acquired time-series record.
- **Measurement Session:** the execution that produced the record.
- **Nickname:** a human-readable name for the individual motor; it is not a unique ID.
- **Benchmark procedure:** the test recipe that produced the record.

Do not infer a missing session, motor instance, or benchmark procedure from a nickname alone. Do not treat estimated outputs as raw measurements.

## 2. Known correspondence index

| Instance / identity | RawLog or group | Correspondence | Confidence / notes |
|---|---|---|---|
| Instance 10 — SHINA-III | `MOTOR-000001`, LEG001 / open-new | Opening / newly opened motor condition. Prior mapping associates MOTOR-000001, pages/segments 1–46 with LEG001. | Recorded mapping; confirm against the actual RawLog body before quoting exact dates or session IDs. |
| Instance 10 — SHINA-III | LEG002 | Bearing-oil condition. | Recorded mapping; exact RawLog ID and session ID are not confirmed in this index. |
| Instance 10 — SHINA-III | LEG003 | Tune Basic condition. | Recorded mapping; exact RawLog ID and session ID are not confirmed in this index. |
| Instance 10 — SHINA-III | MOTOR-000007 | Later run after actual running/use. | Recorded mapping; exact benchmark recipe/session metadata should be checked in the source record. |
| Instance 7 — nickname FUKU2024 | Opening / newly opened data | An opening-condition record exists for this individual. | Recorded from prior analysis; exact RawLog ID and session ID need source-log verification. |
| Instance 7 — nickname FUKU2024 | TuneBasic run | A TuneBasic run had an abnormal sequence/position order, but this does **not** mean the motor's later Benchmark RawLog is invalid. | Important distinction: the anomaly concerns the TuneBasic run sequence, not the individual motor or all its RawLogs. Exact log ID needs verification. |
| Instance 7 — nickname FUKU2024 | Later Benchmark RawLog | A later Benchmark RawLog was assessed as normal and usable. | Recorded assessment; exact ID, recipe and session need source-log verification. |
| Instance 12 — motor model/type not specified here | Multiple test records | The user indicated that several test records likely exist for this individual and requested comparison across logs. | Candidate set not enumerated here; retrieve source records and map each ID/session before analysis. |

## 3. Known physical comparison context (not RawLog identity)

The following notes help interpret comparisons but must not be mistaken for fields read from a RawLog:

- **SHINA-III / Instance 10:** vehicle comparison context previously recorded as 111 g without battery, 3.5:1 gear ratio, and approximately 24 mm tires.
- **Instance 7 / FUKU2024:** vehicle comparison context previously recorded as 132 g without battery, 3.7:1 gear ratio, and approximately 24 mm tires.
- Same-condition smartphone no-load RPM observations were used only as a plausibility check, not as official RawLog sensor values or a replacement for the defined estimated-RPM calculation.
- The motor model's nominal values are master/reference information; they must not be substituted for individual measured or estimated results.

## 4. Benchmark labels and what they mean

The project's benchmark specification distinguishes the procedure from the individual motor:

- `STANDARD_3V30S`: fixed 2 s preparation interval, then a 30 s baseline measurement under the 3.00 V target-control condition. The 2 s interval is not a stability gate.
- `FULL_PACKAGE`: baseline 3.00 V measurement for 30 s, PWM +5% relative to baseline for 30 s, return/buffer for 10 s, PWM -5% relative to the same baseline for 30 s, return/buffer for 10 s, then stop.
- The project has also introduced voltage-control-mode distinctions:
  - `TERMINAL`: forward target is V4 − V5 = 3.00 V; reverse target is V5 − V4 = 3.00 V.
  - `INPUT`: forward input-side target is V4 = 3.00 V; reverse input-side target is V5 = 3.00 V.
- Where the source record does not contain the recipe or control mode, leave it **unknown**; do not retroactively label it as INPUT or TERMINAL by guesswork.
- The RawLog time-series format is intended to remain unchanged. The linked Session/metadata supplies procedure context where recorded.

## 5. RawLog field interpretation notes

Firmware defines the sensor-side meanings used by the current device:

- `voltage1`: A4 / VM1 / V4-side voltage.
- `voltage2`: A5 / VM2 / V5-side voltage.
- `motorVoltage`: `voltage1 - voltage2` in firmware; interpret direction/control-mode context before comparing forward and reverse conditions.
- `current1`: ACS712 #1, high-side current.
- `current2`: ACS712 #2, low-side return current.
- `pwm`: recorded PWM/control value.
- `elapsed_time`: elapsed acquisition time.
- Additional fields such as phase/state, power, ripple, peak current, magnetic input and temperature are available only where present in that RawLog/firmware version; do not assume every historic record contains every field.

For INPUT mode, the relevant input-side voltage is direction-dependent: forward uses V4 / voltage1, reverse uses V5 / voltage2. This does not change the meaning of terminal motor voltage.

## 6. Rules for future entries

For every newly verified RawLog mapping, add a row to Section 2 with:

1. Motor Instance ID and nickname (if any).
2. Exact RawLog/log ID and repository path.
3. Measurement Session ID.
4. Date/time from the record or linked session.
5. Benchmark type and voltage-control mode, if actually recorded.
6. Purpose/condition label (e.g. open/new, bearing oil, TuneBasic, benchmark, break-in).
7. Status: verified against source log, user-reported mapping, or unresolved.
8. Evidence pointer: source RawLog or Issue URL.

Never silently replace a prior mapping. If evidence contradicts it, record the discrepancy and resolve it through the command-center process.

## 7. Source specification references

- `docs/motor_benchmark_spec.md` — benchmark procedures and traceability requirements.
- `docs/motor_analysis_spec.md` — estimated outputs, inputs, and restrictions on nominal values.
- `docs/MOTOR_DEVICE_WIRING_REFERENCE.md` — firmware pin and sensor mapping.

**Open follow-up:** The known historical mappings above should be reconciled against the actual files in `hamtech86/mini4wd-raw-logs` so exact log IDs, session IDs, timestamps, recipe metadata, and source paths can be added without guesswork.
