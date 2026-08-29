# Motor raw log index

## MOTOR-000001
- Motor type: アトミックチューン
- Raw log file: `MOTOR-000001.txt`
- Handling: raw log; do not alter contents

## MOTOR-000002
- Motor type: トルクチューン
- Condition: チューンベーシック後、一晩着磁
- Raw log file: `MOTOR-000002.txt`
- Handling: raw log; do not alter contents
- Important: the embedded `MOTOR_BREAKIN_V3` record ID in this raw log is `000001`. This is retained as-is because the raw log must not be rewritten. For library management, this file is explicitly assigned to MOTOR-000002 / トルクチューン by the index above.

## Management rule
- Filename / library assignment is the motor-instance identifier.
- Raw serial log contents are immutable evidence and must not be rewritten merely to make the embedded record ID match the library identifier.
- Analysis/derived values are not stored in these raw log files.
