from pathlib import Path

import pytest

from measurement_310.engine import SequenceController, SequenceError, SequenceState
from measurement_310.transport import MockTransport
from raw_log_v2 import RawLogV2Writer


class FakeClock:
    def __init__(self):
        self.ns = 1_000_000_000

    def monotonic_ns(self):
        return self.ns

    def utc_now(self):
        return "2026-11-01T00:00:00.000Z"

    def advance_ms(self, value):
        self.ns += value * 1_000_000


class FakeCodec:
    def encode_pwm(self, pwm):
        return f"PWM:{pwm}".encode()

    def encode_stop(self):
        return b"STOP"

    def decode(self, payload):
        return payload


def manifest(root):
    return {
        "log_id": "TEST-310", "measurement_session_id": "SESSION-310",
        "started_at_utc": "2026-11-01T00:00:00.000Z",
        "motor_instance_id": None,
        "device": {"type": None, "model": None, "firmware_version": None,
                   "firmware_build": None, "firmware_id": None, "adc_resolution_bits": None},
        "measurement_conditions": {"direction": "UNKNOWN", "voltage_control_mode": "UNKNOWN",
            "sweep_pwm_min": 0, "sweep_pwm_max": 30, "stage_duration_ms": 10000,
            "schedule_owner": "PYTHON"},
    }


def test_recovery_is_mandatory_before_start(tmp_path):
    clock = FakeClock()
    ctl = SequenceController(RawLogV2Writer(tmp_path), manifest(tmp_path),
        lambda pwm: clock.utc_now(), lambda: None, lambda: None, clock)
    with pytest.raises(SequenceError):
        ctl.start()
    ctl.startup_recover()
    ctl.start()
    assert ctl.state == SequenceState.WAITING_ACK


def test_ack_required_and_stage_clock_starts_at_ack(tmp_path):
    clock = FakeClock()
    acks = []
    sent = []
    ctl = SequenceController(RawLogV2Writer(tmp_path), manifest(tmp_path),
        lambda pwm: sent.append(pwm) or clock.utc_now(), lambda: None,
        lambda: acks.pop(0) if acks else None, clock, ack_timeout_ms=500)
    ctl.startup_recover()
    ctl.start()
    clock.advance_ms(400)
    ctl.poll()
    assert ctl.state == SequenceState.WAITING_ACK
    acks.append((0, clock.utc_now()))
    ctl.poll()
    assert ctl.state == SequenceState.RUNNING
    assert ctl.stage_start_ns == clock.monotonic_ns()
    clock.advance_ms(10_000)
    ctl.poll()
    assert sent == [0, 1]
    assert ctl.state == SequenceState.WAITING_ACK


def test_ack_timeout_fails_closed_and_does_not_advance(tmp_path):
    clock = FakeClock()
    stops = []
    sent = []
    ctl = SequenceController(RawLogV2Writer(tmp_path), manifest(tmp_path),
        lambda pwm: sent.append(pwm) or clock.utc_now(), lambda: stops.append(True),
        lambda: None, clock, ack_timeout_ms=100)
    ctl.startup_recover()
    ctl.start()
    clock.advance_ms(100)
    ctl.poll()
    assert ctl.state == SequenceState.FAULT
    assert sent == [0]
    assert stops == [True]


def test_mock_transport_never_opens_hardware():
    transport = MockTransport()
    transport.connect()
    transport.send(b"TEST")
    assert transport.sent == [b"TEST"]
    transport.disconnect()
    assert not transport.connected


def test_transport_failure_raises():
    transport = MockTransport(fail_connect=True)
    with pytest.raises(Exception):
        transport.connect()


def test_complete_31_stage_sweep_creates_schema_valid_package(tmp_path):
    from raw_log_v2 import validate_package
    clock = FakeClock()
    pending = []
    ctl = SequenceController(RawLogV2Writer(tmp_path), manifest(tmp_path),
        lambda pwm: clock.utc_now(), lambda: None,
        lambda: pending.pop(0) if pending else None, clock)
    ctl.startup_recover()
    ctl.start()
    for pwm in range(31):
        pending.append((pwm, clock.utc_now()))
        ctl.poll()
        assert ctl.state == SequenceState.RUNNING
        clock.advance_ms(10_000)
        ctl.poll()
    assert ctl.state == SequenceState.COMPLETED
    package = tmp_path / "TEST-310"
    import json
    mf = json.loads((package / "manifest.json").read_text())
    records = [json.loads(line) for line in (package / "records.jsonl").read_text().splitlines()]
    assert validate_package(mf, records, raise_on_error=False) == []
    stages = [r for r in records if r["record_type"] == "PWM_STAGE"]
    assert [r["pwm_command"] for r in stages] == list(range(31))


def test_recovery_failure_blocks_start(tmp_path, monkeypatch):
    writer = RawLogV2Writer(tmp_path)
    clock = FakeClock()
    ctl = SequenceController(writer, manifest(tmp_path), lambda pwm: clock.utc_now(),
                             lambda: None, lambda: None, clock)
    def fail():
        raise OSError("recovery fsync failed")
    monkeypatch.setattr(writer, "recover_pending", fail)
    with pytest.raises(OSError):
        ctl.startup_recover()
    with pytest.raises(SequenceError):
        ctl.start()


def test_adc_channels_are_independent_and_keep_device_timestamps(tmp_path):
    import json
    clock = FakeClock()
    ctl = SequenceController(RawLogV2Writer(tmp_path), manifest(tmp_path),
        lambda pwm: clock.utc_now(), lambda: None, lambda: None, clock)
    ctl.startup_recover()
    ctl.start()
    ctl.record_adc_sample("A0", 123, 10, 1001, "adc_conversion_complete",
                          "boot-1", device_sample_sequence=1)
    ctl.record_adc_sample("A1", 456, 10, 1008, "adc_conversion_complete",
                          "boot-1", device_sample_sequence=2)
    ctl.record_adc_sample("A4", 700, 10, 1012, "adc_conversion_complete",
                          "boot-1", device_sample_sequence=3)
    ctl.record_adc_sample("A5", 650, 10, 1019, "adc_conversion_complete",
                          "boot-1", device_sample_sequence=4)
    records = [json.loads(line) for line in
               (tmp_path / ".work" / "TEST-310" / "records.jsonl").read_text().splitlines()]
    samples = [r for r in records if r["record_type"] == "ADC_SAMPLE"]
    assert [(r["channel"], r["adc_raw"], r["device_timestamp_us_u32"]) for r in samples] == [
        ("A0", 123, 1001), ("A1", 456, 1008), ("A4", 700, 1012), ("A5", 650, 1019)]
    assert samples[0]["signal_role"] == "winding_current"
    assert samples[1]["signal_role"] == "brush_stability_observation"
    assert "converted_value" not in samples[1]
    assert samples[2]["signal_role"] == "voltage_v4"
    assert samples[3]["signal_role"] == "voltage_v5"
    ctl.abort("test_end")


def test_visual_event_is_human_reported_and_not_adc_timestamp(tmp_path):
    import json
    clock = FakeClock()
    ctl = SequenceController(RawLogV2Writer(tmp_path), manifest(tmp_path),
        lambda pwm: clock.utc_now(), lambda: None, lambda: (0, clock.utc_now()), clock)
    ctl.startup_recover()
    ctl.start()
    ctl.poll()
    ctl.record_visual_event("ROTATION_START_CONFIRMED", "operator",
                            "2026-11-01T00:00:01.000Z")
    records = [json.loads(line) for line in
               (tmp_path / ".work" / "TEST-310" / "records.jsonl").read_text().splitlines()]
    event = next(r for r in records if r["record_type"] == "EVENT")
    assert event["observation_method"] == "human_visual"
    assert event["stage_id"] == "PWM-00"
    assert event["observed_at_utc"] != event["reported_at_utc"] or event["host_monotonic_ns"] > 0
    ctl.abort("test_end")


def test_protocol_client_uses_injected_codec_and_mock_only():
    from measurement_310.transport import ProtocolClient
    class Codec:
        def encode_pwm(self, pwm):
            return f"opaque-command-{pwm}".encode()
        def encode_stop(self):
            return b"opaque-stop"
        def decode(self, payload):
            return {"kind": "PWM_ACK", "pwm": 7}
    mock = MockTransport()
    client = ProtocolClient(mock, Codec())
    client.connect()
    sent_at = client.send_pwm(7)
    assert sent_at.endswith("Z")
    assert mock.sent == [b"opaque-command-7"]
    mock.queue(b"opaque-ack")
    ack = client.poll_ack()
    assert ack[0] == 7
    assert ack[1].endswith("Z")
    client.send_stop()
    assert mock.sent[-1] == b"opaque-stop"
    client.disconnect()


def test_ack_mismatch_stops_without_advancing_or_auto_restarting(tmp_path):
    clock = FakeClock()
    sent, stops = [], []
    acks = [(1, clock.utc_now())]
    ctl = SequenceController(RawLogV2Writer(tmp_path), manifest(tmp_path),
        lambda pwm: sent.append(pwm) or clock.utc_now(), lambda: stops.append(True),
        lambda: acks.pop(0) if acks else None, clock)
    ctl.startup_recover()
    ctl.start()
    ctl.poll()
    assert ctl.state == SequenceState.FAULT
    assert sent == [0]
    assert stops == [True]
    # A later apparent communication recovery is not polled into a restart.
    acks.append((0, clock.utc_now()))
    assert ctl.poll() == SequenceState.FAULT
    assert sent == [0]


def test_startup_recovery_checks_every_discovered_work_item(tmp_path):
    writer = RawLogV2Writer(tmp_path)
    previous = manifest(tmp_path)
    previous["log_id"] = "PENDING-OLD"
    previous["measurement_session_id"] = "SESSION-OLD"
    writer.begin(previous)  # Simulate an interrupted prior process.
    clock = FakeClock()
    ctl = SequenceController(writer, manifest(tmp_path), lambda pwm: clock.utc_now(),
                             lambda: None, lambda: None, clock)
    recovered = ctl.startup_recover()
    assert [item["log_id"] for item in recovered] == ["PENDING-OLD"]
    assert writer.list_incomplete_work() == []
    ctl.start()
    assert ctl.state == SequenceState.WAITING_ACK


@pytest.mark.parametrize("method,args", [
    ("record_adc_sample", ("A0", 111, 10, 10, "adc_conversion_complete", "boot-fail")),
    ("record_visual_event", ("ROTATION_START_CONFIRMED", "operator", "2026-11-01T00:00:01.000Z")),
])
def test_observation_append_failure_fails_closed_and_attempts_stop(
    tmp_path, monkeypatch, method, args
):
    clock = FakeClock()
    stops = []
    ctl = SequenceController(RawLogV2Writer(tmp_path), manifest(tmp_path),
        lambda pwm: clock.utc_now(), lambda: stops.append("STOP"),
        lambda: (0, clock.utc_now()), clock)
    ctl.startup_recover()
    ctl.start()
    ctl.poll()

    def fail_append(record):
        raise OSError("injected append failure")

    monkeypatch.setattr(ctl.session, "append", fail_append)
    with pytest.raises(SequenceError):
        getattr(ctl, method)(*args)
    assert ctl.state == SequenceState.FAULT
    assert stops == ["STOP"]


def test_finalize_failure_does_not_append_to_work_after_finalize_started(tmp_path, monkeypatch):
    import json
    clock = FakeClock()
    stops, acks = [], []
    ctl = SequenceController(RawLogV2Writer(tmp_path), manifest(tmp_path),
        lambda pwm: clock.utc_now(), lambda: stops.append("STOP"),
        lambda: acks.pop(0) if acks else None, clock)
    ctl.startup_recover()
    ctl.start()
    for pwm in range(30):
        acks.append((pwm, clock.utc_now()))
        ctl.poll()
        assert ctl.state == SequenceState.RUNNING
        clock.advance_ms(10_000)
        ctl.poll()
    acks.append((30, clock.utc_now()))
    ctl.poll()
    assert ctl.state == SequenceState.RUNNING

    appended = []
    original_append = ctl.session.append

    def track_append(record):
        appended.append(record["record_type"] + ":" + str(record.get("event", "")))
        return original_append(record)

    monkeypatch.setattr(ctl.session, "append", track_append)

    def fail_finalize(*args, **kwargs):
        raise OSError("injected publication failure")

    monkeypatch.setattr(ctl.session, "finalize", fail_finalize)
    clock.advance_ms(10_000)
    ctl.poll()
    assert ctl.state == SequenceState.FAULT
    assert ctl._finalization_started
    assert appended == ["PWM_STAGE:", "SESSION_EVENT:SESSION_COMPLETED"]
    assert stops == ["STOP"]
    records = [json.loads(line) for line in
        (tmp_path / ".work" / "TEST-310" / "records.jsonl").read_text().splitlines()]
    session_events = [r.get("event") for r in records if r["record_type"] == "SESSION_EVENT"]
    assert session_events[0] == "SESSION_STARTED"
    assert session_events[-1] == "SESSION_COMPLETED"
    assert session_events.count("OTHER") == 31


def test_protocol_client_retains_fragmented_ack_until_frame_complete():
    from measurement_310.transport import IncompleteMessage, ProtocolClient

    class PartialCodec:
        def encode_pwm(self, pwm):
            return bytes([pwm])

        def encode_stop(self):
            return b"!"

        def decode(self, payload):
            if payload != b"ACK:07":
                raise IncompleteMessage()
            return {"kind": "PWM_ACK", "pwm": 7}

    mock = MockTransport()
    client = ProtocolClient(mock, PartialCodec())
    client.connect()
    mock.queue(b"ACK:")
    assert client.poll_ack() is None
    assert bytes(client._receive_buffer) == b"ACK:"
    assert client.poll_ack() is None
    mock.queue(b"07")
    assert client.poll_ack()[0] == 7
    assert client._receive_buffer == bytearray()
    client.disconnect()


def test_protocol_client_preserves_multiple_frames_in_one_serial_read():
    from measurement_310.transport import DecodedFrame, ProtocolClient
    class MultiFrameCodec:
        def encode_pwm(self, pwm): return bytes([pwm])
        def encode_stop(self): return b"!"
        def decode(self, payload):
            if len(payload) < 2:
                from measurement_310.transport import IncompleteMessage
                raise IncompleteMessage()
            return DecodedFrame({"kind": "PWM_ACK", "pwm": payload[1]},
                                consumed_bytes=2)
    mock = MockTransport()
    client = ProtocolClient(mock, MultiFrameCodec())
    client.connect()
    mock.queue(b"A\x05B\x06")
    assert client.poll_ack()[0] == 5
    assert bytes(client._receive_buffer) == b"B\x06"
    assert client.poll_ack()[0] == 6
    assert client._receive_buffer == bytearray()
    client.disconnect()


@pytest.mark.parametrize(
    "failure_type,trigger",
    [
        ("ACK_EVENT", "ack"),
        ("PWM_STAGE", "stage"),
        ("ABORT_EVENT", "abort_event"),
    ],
)
def test_control_record_append_failures_latch_write_disable_and_stop(
    tmp_path, monkeypatch, failure_type, trigger
):
    clock = FakeClock()
    stops = []
    acks = [(0, clock.utc_now())]
    ctl = SequenceController(
        RawLogV2Writer(tmp_path), manifest(tmp_path),
        lambda pwm: clock.utc_now(), lambda: stops.append("STOP"),
        lambda: acks.pop(0) if acks else None, clock,
    )
    ctl.startup_recover()
    ctl.start()
    calls = []
    original_append = ctl.session.append

    def fail_selected(record):
        calls.append(record["record_type"] + ":" + str(record.get("event", "")))
        selected = (
            (failure_type == "ACK_EVENT" and record["record_type"] == "SESSION_EVENT"
             and record.get("event") == "OTHER")
            or (failure_type == "PWM_STAGE" and record["record_type"] == "PWM_STAGE")
            or (failure_type == "ABORT_EVENT" and record["record_type"] == "SESSION_EVENT"
                and record.get("event") == "COMMUNICATION_LOST")
        )
        if selected:
            raise OSError("injected " + failure_type + " append failure")
        return original_append(record)

    monkeypatch.setattr(ctl.session, "append", fail_selected)
    if trigger == "ack":
        ctl.poll()
    elif trigger == "stage":
        ctl.poll()
        clock.advance_ms(10_000)
        ctl.poll()
    elif trigger == "abort_event":
        ctl.abort("communication_lost", fault="injected communication failure")
    assert ctl.state == SequenceState.FAULT
    assert ctl._log_write_failed
    assert stops == ["STOP"]
    failed_call_count = len(calls)
    with pytest.raises(SequenceError):
        ctl._append("SESSION_EVENT", event="MUST_NOT_BE_WRITTEN",
                    host_monotonic_ns=clock.monotonic_ns(), details={})
    assert len(calls) == failed_call_count
    assert not (tmp_path / "TEST-310").exists()
    assert (tmp_path / ".work" / "TEST-310" / "records.jsonl").is_file()


def test_session_started_append_failure_does_not_attempt_followup_append(tmp_path, monkeypatch):
    clock = FakeClock()
    stops = []
    writer = RawLogV2Writer(tmp_path)
    ctl = SequenceController(
        writer, manifest(tmp_path), lambda pwm: clock.utc_now(),
        lambda: stops.append("STOP"), lambda: None, clock,
    )
    ctl.startup_recover()
    original_begin = writer.begin
    calls = []

    def begin_with_injected_append_failure(fields):
        session = original_begin(fields)
        original_append = session.append

        def fail_started(record):
            calls.append(record["record_type"] + ":" + str(record.get("event", "")))
            if record["record_type"] == "SESSION_EVENT" and record.get("event") == "SESSION_STARTED":
                raise OSError("injected SESSION_STARTED append failure")
            return original_append(record)

        monkeypatch.setattr(session, "append", fail_started)
        return session

    monkeypatch.setattr(writer, "begin", begin_with_injected_append_failure)
    ctl.start()
    assert ctl.state == SequenceState.FAULT
    assert ctl._log_write_failed
    assert stops == ["STOP"]
    assert calls == ["SESSION_EVENT:SESSION_STARTED"]
    assert (tmp_path / ".work" / "TEST-310" / "records.jsonl").read_bytes() == b""


def test_ack_wait_preserves_non_ack_before_ack_and_exposes_it_separately():
    from measurement_310.transport import DecodedFrame, IncompleteMessage, ProtocolClient

    class StreamCodec:
        def encode_pwm(self, pwm): return bytes([pwm])
        def encode_stop(self): return b"!"
        def decode(self, payload):
            if len(payload) < 2:
                raise IncompleteMessage()
            tag, value = payload[0], payload[1]
            kind = "PWM_ACK" if tag == ord("A") else "TELEMETRY" if tag == ord("T") else "UNKNOWN"
            message = {"kind": kind, "value": value}
            if kind == "PWM_ACK":
                message["pwm"] = value
            return DecodedFrame(message, 2)

    mock = MockTransport()
    client = ProtocolClient(mock, StreamCodec())
    client.connect()
    mock.queue(b"T\\x03")
    mock.queue(b"A\\x07")
    assert client.poll_ack()[0] == 7
    assert client.poll_message() == {"kind": "TELEMETRY", "value": 3}
    assert client.poll_message() is None
    client.disconnect()


def test_ack_then_non_ack_coalesced_and_unknown_message_are_not_discarded():
    from measurement_310.transport import DecodedFrame, IncompleteMessage, ProtocolClient

    class StreamCodec:
        def encode_pwm(self, pwm): return bytes([pwm])
        def encode_stop(self): return b"!"
        def decode(self, payload):
            if len(payload) < 2:
                raise IncompleteMessage()
            tag, value = payload[0], payload[1]
            kind = {ord("A"): "PWM_ACK", ord("T"): "TELEMETRY"}.get(tag, "FUTURE_KIND")
            message = {"kind": kind, "value": value}
            if kind == "PWM_ACK":
                message["pwm"] = value
            return DecodedFrame(message, 2)

    mock = MockTransport()
    client = ProtocolClient(mock, StreamCodec())
    client.connect()
    mock.queue(b"A\\x08T\\x02X\\x09")
    assert client.poll_ack()[0] == 8
    assert client.poll_message() == {"kind": "TELEMETRY", "value": 2}
    assert client.poll_message() == {"kind": "FUTURE_KIND", "value": 9}
    client.disconnect()


@pytest.mark.parametrize(
    "failure_boundary,expected_status",
    [
        ("records_published", "incomplete"),
        ("manifest_published", "completed"),
        ("work_cleanup", "completed"),
    ],
)
def test_real_rawlog_finalize_publication_faults_preserve_consistent_recovery(
    tmp_path, monkeypatch, failure_boundary, expected_status
):
    import json
    import raw_log_v2.storage as storage

    clock = FakeClock()
    stops = []
    acks = []
    writer = RawLogV2Writer(tmp_path)
    ctl = SequenceController(
        writer, manifest(tmp_path), lambda pwm: clock.utc_now(),
        lambda: stops.append("STOP"),
        lambda: acks.pop(0) if acks else None, clock,
    )
    ctl.startup_recover()
    ctl.start()
    post_finalize_appends = []
    original_session_append = ctl.session.append

    def track_append(record):
        if ctl._finalization_started:
            post_finalize_appends.append(record)
        return original_session_append(record)

    monkeypatch.setattr(ctl.session, "append", track_append)
    work_dir = tmp_path / ".work" / "TEST-310"
    real_publish = storage._publish_new_file
    real_rmtree = storage.shutil.rmtree
    injected = {"done": False}

    if failure_boundary in {"records_published", "manifest_published"}:
        def fail_after_publication(path, payload, temp_path):
            result = real_publish(path, payload, temp_path)
            should_fail = (
                (failure_boundary == "records_published" and path.name == "records.jsonl")
                or (failure_boundary == "manifest_published" and path.name == "manifest.json")
            )
            if should_fail and not injected["done"]:
                injected["done"] = True
                raise OSError("injected after " + failure_boundary)
            return result
        monkeypatch.setattr(storage, "_publish_new_file", fail_after_publication)
    else:
        def fail_work_cleanup(path, *args, **kwargs):
            if Path(path) == work_dir and not injected["done"]:
                injected["done"] = True
                raise OSError("injected before work cleanup")
            return real_rmtree(path, *args, **kwargs)
        monkeypatch.setattr(storage.shutil, "rmtree", fail_work_cleanup)

    for pwm in range(31):
        acks.append((pwm, clock.utc_now()))
        ctl.poll()
        assert ctl.state == SequenceState.RUNNING
        clock.advance_ms(10_000)
        ctl.poll()
        if pwm < 30:
            assert ctl.state == SequenceState.WAITING_ACK
    assert injected["done"]
    assert ctl.state == SequenceState.FAULT
    assert ctl._finalization_started
    assert stops == ["STOP"]
    assert post_finalize_appends == []
    assert work_dir.is_dir()

    if failure_boundary in {"records_published", "manifest_published"}:
        monkeypatch.setattr(storage, "_publish_new_file", real_publish)
    else:
        monkeypatch.setattr(storage.shutil, "rmtree", real_rmtree)

    recovery = writer.recover_pending()
    assert len(recovery) == 1
    final_dir = tmp_path / "TEST-310"
    assert final_dir.is_dir()
    final_manifest = json.loads((final_dir / "manifest.json").read_text())
    final_records = [json.loads(line) for line in
                     (final_dir / "records.jsonl").read_text().splitlines()]
    assert final_manifest["status"] == expected_status
    assert final_records[-1]["record_type"] == "SESSION_EVENT"
    assert final_records[-1]["event"] == "SESSION_COMPLETED"
    assert not work_dir.exists()
    if expected_status == "incomplete":
        assert recovery[0]["recovery_status"] != "already_published"
        originals = list((tmp_path / ".recovery" / "TEST-310").glob("crash-*/original"))
        assert len(originals) == 1
        assert (originals[0] / "records.jsonl").is_file()
    else:
        assert recovery[0]["recovery_status"] == "already_published"
