# 310-5 T09/T15 ambiguous STOP outcome fixture (2026-11-03)

Candidate-only host regression note. This is not a protocol specification, firmware decision, hardware test, or acceptance record.

## Covered behavior

A deterministic host test wires `SequenceController.abort()` to
`ProtocolClient.send_stop()` backed by `MockTransport(fail_send=True)`.
The test verifies that:

- the STOP send error propagates through the protocol client;
- the controller latches `FAULT`;
- an abort event is retained with `stop_transmission_attempted=true`;
- the recorded device state remains `unknown`;
- the failure text is retained as host fault evidence; and
- no automatic retry is issued by this path.

## Interpretation and limits

A transport exception is an ambiguous delivery outcome. Depending on where a real
serial write/flush failed, zero, some, or all bytes may already have been accepted
by the operating system, adapter, UART, or device. The mock fixture proves only
host error propagation and fail-closed bookkeeping; its empty sent list does not
model physical wire delivery.

The conservative host behavior is one attempt followed by a latched fault and
unknown device state. This is not a final retry policy decision. Whether retrying
STOP is safe depends on firmware duplicate handling, command semantics, and the
transport topology, none of which this fixture establishes. No retry or duplicate
STOP behavior is authorized by this test.

No physical hardware, CI dispatch, energized output, or 310-second measurement
was used. Test execution status: NOT RUN. T09/T15 remain NOT PASS; T01-T18 formal
PASS count remains zero.
