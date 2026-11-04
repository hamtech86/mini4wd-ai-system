# 310-5 host integration decisions and remaining gates — 2026-11-04

## 1. T10/T17 RawLog manifest compatibility — read-only finding

### Verified existing contract

The 310-2 RawLog v2 implementation and its documentation explicitly define the public package as exactly:
- `manifest.json`
- `records.jsonl`

The writer's final package publication allows only those two public files (plus its temporary staging names while publishing). The validator's record type set is fixed to `SESSION_EVENT`, `PWM_STAGE`, `ADC_SAMPLE`, `CALIBRATION`, `EVENT`, and `DERIVED`. The private `.work` and `.recovery` trees are recovery implementation state, not public package extensions.

### Compatibility conclusion

Under the current authorization (no RawLog schema, writer, or validator changes), a third `transport-evidence.jsonl` file cannot be placed inside the RawLog package and claimed as a valid v2 package. Adding a new public record type or a new manifest inventory field would also require a contract decision and is not performed here.

A non-mutating external-sibling concept can be described, but it does **not** satisfy T17's requirement that the RawLog manifest inventory/hash/count the transport Evidence artifact:

- Keep the RawLog package byte-for-byte as the existing two-file package.
- Store transport Evidence in a separate sibling evidence bundle, not inside the RawLog package.
- The sibling bundle would need its own manifest containing the exact `log_id`, `measurement_session_id`, RawLog `manifest.json` SHA-256, RawLog `records.jsonl` SHA-256, Evidence file inventory/hash/count, and a versioned relationship identifier.
- Consumers must treat the two artifacts as separate objects and reject missing, mismatched, or untrusted cross-links. The RawLog package alone must never imply that companion Evidence exists or is valid.

This is only a compatibility proposal. Without a higher-level collection manifest or a separately approved RawLog contract revision, the sibling is not cryptographically inventoried by the RawLog manifest and cannot be represented as a completed T17 package.

### Decision

- Do not add a third file to a RawLog v2 package.
- Do not change `manifest.json`, the writer, validator, or record types.
- Keep L04/T17 **FAIL / unresolved contract mismatch**.
- Request a separate design-authority decision on whether a versioned outer collection manifest is acceptable or whether a future RawLog contract revision is required. Neither option is implemented or assumed.

## 2. T04/T05 production-path integration — protocol boundary

The current `SequenceController` production interface accepts `send_pwm(pwm)` and receives a two-field ACK result `(pwm, ack_utc)`. It does not expose a trustworthy command ID, session identity, full device boot epoch, or stage-context echo in the ACK path. The existing T04/T05 primitives can persist a host intent and compare a full five-field identity, but they cannot manufacture missing device-side identity.

Required integration sequence once the protocol authority supplies the concrete identity contract:
1. Allocate a unique command ID and bind it to the active measurement session, confirmed full device boot ID, and stage context.
2. Durably append and fsync the intent before entering the transport send callback.
3. Record the actual write/flush result, preserving UNKNOWN for partial/uncertain delivery.
4. Accept only an ACK that echoes and exactly matches the full identity tuple.
5. Durably append ACK Evidence before advancing the stage.
6. Keep the independent actuation re-arm gate latched on uncertain delivery, missing/mismatched ACK, Evidence failure, or unknown terminal state.

Until the firmware/wire contract provides a real full boot identity and matching ACK fields, production integration must not substitute a constant, zero, truncated boot ID, PWM-only ACK, or host-generated token as proof of device identity. No firmware or wire change is made in this branch. T04/T05 primitives remain candidate building blocks, not production-path PASS.

## 3. T18 host fsync profile — execution plan

The required measurement is host/storage-specific and must be collected on the actual approved host and storage target, not inferred from a cloud or development environment.

Minimum profile:
- At least 10,000 samples per measured operation.
- Separate file-fsync and directory-fsync latency distributions.
- Report p50, p95, p99, p99.9, maximum, sample count, and failures.
- Record OS/kernel, Python version, filesystem type/mount, storage device identity where available, mount options, and test path.
- Report the measured sequence's combined durability budget and compare it against the 10,000ms stage interval after reserving the approved STOP/abort budget.
- Preserve raw sample output and a SHA-256 digest of the report and sample file.

No measurement is reported here: the full repository/target host and approved storage profile are not available in the current execution context. T18 remains **NOT RUN**. A profile from a different host must not be substituted.

## 4. Verification and acceptance boundary

- The R01 source and tests are on the independent host-integration candidate branch.
- R01 tests are authored but NOT RUN; full repository test execution is still unavailable.
- T04/T05 production integration remains blocked by missing concrete ACK/device-epoch identity.
- T10/T17 remains FAIL pending a design-authority decision; no RawLog mutation was made.
- T18 remains NOT RUN pending a 10,000-sample profile on the approved host/storage.
- No CI dispatch, PR merge, firmware modification, RawLog schema/writer/validator change, hardware operation, or stage transition was performed.
- Formal T01–T18 PASS remains 0. R01 remains FAIL. 310-5 acceptance remains pending.
