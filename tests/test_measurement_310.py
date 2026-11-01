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
