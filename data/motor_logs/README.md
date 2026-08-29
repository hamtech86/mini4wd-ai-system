# Motor Raw Log Library

## Purpose

Motor measurement raw logs are stored here as the single source for repeated analysis. The same raw log must not need to be pasted into individual analysis chats repeatedly.

## Rules

- Raw logs are preserved as received; do not overwrite or normalize the original data.
- Analysis must use the raw log as the source of truth.
- Derived values are estimates unless explicitly identified as measured values.
- If the calculation definition changes, re-analysis is performed from the preserved raw log.
- Each log should have a stable identifier and, where known, motor name, test conditions, voltage basis, PWM, direction, and measurement date.
- Do not delete an old raw log merely because a newer interpretation or calculation method exists.

## Recommended naming

`<motor>_<test-type>_<YYYYMMDD>_<sequence>.log`

Example:

`atomic-tune_breakin_20260829_001.log`

## Management

The司令塔/management chat should treat this directory as the canonical raw-log library and reference log IDs instead of repeatedly requesting the same log contents from the user.
