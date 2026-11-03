# 310-5 T11 host-side loss-accounting model (candidate)

Status: design/test fixture definition only; NOT RUN; NOT ACCEPTED.
Authority: upper-command decision comment 6602410842.
Scope: deterministic host-side accounting only. No RawLog schema or firmware changes.

## Accounting invariants

1. Account independently per channel and full boot epoch; never merge across epoch boundaries.
2. Use half-open windows [start, end). A sample exactly at start belongs to the window; exactly at end does not.
3. Keep these quantities distinct: expected samples, receive attempts, valid samples, invalid samples, and missing samples.
4. Missing is derived only when an expected count is known: missing = max(0, expected - valid - invalid-attributable). Never infer expected count from observed data.
5. Duplicate sequence frames are not additional samples. Conflicting duplicates are unresolved/invalid and must not silently replace the first observation.
6. Sequence wrap is handled by the sequence-extension classification, not by timestamp sorting. Gaps can be counted only when sequence continuity is attributable to the same epoch/channel.
7. Samples with unknown channel, epoch, or window are unattributable; retain a separate count. Do not assign them to a convenient window.
8. Corrections are append-only evidence. A later correction must reference the prior accounting record and preserve its original values.
9. Totals are deterministic for identical ordered inputs. Input ordering is explicit; no wall-clock or host-local timezone dependency.
10. This accounting does not prove sensor acquisition, physical sampling, transport delivery, or MCU behavior.

## Required fixture matrix

| Fixture | Expected disposition |
|---|---|
| Known expected count; all valid | missing = 0; valid equals expected |
| One attributable sequence gap | one missing; no synthetic sample emitted |
| Exact duplicate frame | duplicate counter increments; valid sample count unchanged |
| Same sequence, conflicting payload | unresolved/invalid counter; no silent overwrite |
| uint16 wrap 65534, 65535, 0, 1 | continuous after epoch-aware extension |
| Gap across epoch boundary | never counted as one cross-epoch gap |
| Invalid timestamp or payload | invalid count; not valid |
| Frame outside half-open window | not assigned to that window |
| Unknown channel/epoch/window | unattributable bucket |
| Expected count unknown | missing remains unknown, not zero |
| Append-only correction | prior accounting snapshot remains recoverable |
| Identical fixture replay | byte-identical deterministic result |

## Exit evidence before T11 can be marked complete

- Implementation and tests for the above fixture matrix.
- Deterministic serialized result and independently recomputed totals.
- Explicit handling for unknown expected counts and unattributable records.
- Test execution evidence on the candidate branch.
- Review confirming no RawLog schema, firmware, or accepted 310-4 document changed.

Formal T01–T18 acceptance remains the upper command's decision. This note does not authorize hardware or 310-6.
