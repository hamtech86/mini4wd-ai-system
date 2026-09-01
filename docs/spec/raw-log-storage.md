# Raw Log Storage Specification

Status: PLANNED

## Scope
This document defines storage of raw motor measurement logs. It is separate from Motor Analysis and Battery Analysis calculation logic.

## Saved record
Each save operation creates exactly one raw-log record containing:

1. Date/time
2. Motor instance nickname
3. Optional memo
4. Raw log

## Rules
- Date/time is recorded automatically when the save operation occurs.
- The nickname is the nickname of the motor instance at the time of saving.
- Memo is optional and may contain labels such as "opening" or "after Tune Basic".
- The raw log is stored exactly as received from the measurement device; its original text is not rewritten or mixed with analysis values.
- Analysis values and estimated values must never be inserted into the raw-log payload.
- One save operation equals one managed raw-log record.

## Relationship to analysis
A memo such as "after Tune Basic" describes the history of the verification sample only. It does not create a calculation dependency between the break-in recipe and Motor Analysis.

## Relationship to current raw-log library
The existing six-log correspondence is treated as a management/reference set for ongoing verification. It is not a calculation formula or benchmark by itself.
