import threading
import uuid
from types import SimpleNamespace

import pytest

from measurement_310.protocol_v2 import (
    ProtocolV2Codec, PROTOCOL_V2_MAGIC, PROTOCOL_V2_VERSION,
)
from measurement_310.protocol_v2_session import ProtocolV2HostSession
from measurement_310.command_intent import DurableIntentJournal
from measurement_310.protocol_v1_session import TransportEvidenceJournal
from measurement_310.transport import (
    IndependentPySerialStopWriter,
    PySerialTransport,
    TransportError,
)


class FakeSerialPort:
    def __init__(self, *args, flush_release=None, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.flush_release = flush_release
        self.writes = []
        self.flush_count = 0
        self.closed = False

    def write(self, payload):
        self.writes.append(bytes(payload))
        return len(payload)

    def flush(self):
        self.flush_count += 1
        if self.flush_release is not None:
            self.flush_release.wait()

    def close(self):
        self.closed = True


def test_independent_stop_writer_uses_own_serial_object_and_flushes(monkeypatch):
    fake = FakeSerialPort()
    monkeypatch.setitem(__import__("sys").modules, "serial",
                        SimpleNamespace(Serial=lambda *a, **k: fake))
    writer = IndependentPySerialStopWriter(
        "/dev/ttyUSB-stop", write_timeout_s=0.05, flush_timeout_s=0.05
    )
    writer.connect()
    writer(b"STOP-FRAME")
    assert fake.writes == [b"STOP-FRAME"]
    assert fake.flush_count == 1
    writer.disconnect()
    assert fake.closed


def test_independent_stop_writer_timeout_latches_fail_closed(monkeypatch):
    release = threading.Event()
    fake = FakeSerialPort(flush_release=release)
    monkeypatch.setitem(__import__("sys").modules, "serial",
                        SimpleNamespace(Serial=lambda *a, **k: fake))
    writer = IndependentPySerialStopWriter(
        "/dev/ttyUSB-stop", write_timeout_s=0.05, flush_timeout_s=0.001
    )
    writer.connect()
    with pytest.raises(TransportError, match="outcome unknown"):
        writer(b"STOP-FRAME")
    release.set()  # Let the timed-out daemon flush worker terminate.
    with pytest.raises(TransportError, match="fail-closed"):
        writer(b"STOP-FRAME-RETRY")
    assert fake.writes == [b"STOP-FRAME"]


def test_production_session_factory_rejects_same_stop_and_command_tty(tmp_path):
    session_id = str(uuid.uuid4())
    command = PySerialTransport("/dev/ttyACM0", 57600)
    stop = IndependentPySerialStopWriter("/dev/ttyACM0")
    codec = ProtocolV2Codec(PROTOCOL_V2_MAGIC, PROTOCOL_V2_VERSION)
    with pytest.raises(ValueError, match="physically distinct"):
        ProtocolV2HostSession.for_rawlog_session(
            command, codec, tmp_path, session_id, stop_writer=stop,
        )
    assert not (tmp_path / ".command-intents").exists()


def test_production_session_factory_requires_stop_deadline_inside_caller_budget(tmp_path):
    session_id = str(uuid.uuid4())
    command = PySerialTransport("/dev/ttyACM0", 57600)
    stop = IndependentPySerialStopWriter(
        "/dev/ttyUSB9", write_timeout_s=0.15, flush_timeout_s=0.15
    )
    codec = ProtocolV2Codec(PROTOCOL_V2_MAGIC, PROTOCOL_V2_VERSION)
    with pytest.raises(ValueError, match="below STOP caller deadline"):
        ProtocolV2HostSession.for_rawlog_session(
            command, codec, tmp_path, session_id, stop_writer=stop,
            stop_timeout_s=0.25,
        )
    assert not (tmp_path / ".command-intents").exists()


def test_production_session_factory_accepts_distinct_bounded_stop_endpoint(tmp_path):
    session_id = str(uuid.uuid4())
    command = PySerialTransport("/dev/ttyACM0", 57600)
    stop = IndependentPySerialStopWriter(
        "/dev/ttyUSB9", write_timeout_s=0.10, flush_timeout_s=0.10
    )
    codec = ProtocolV2Codec(PROTOCOL_V2_MAGIC, PROTOCOL_V2_VERSION)
    session = ProtocolV2HostSession.for_rawlog_session(
        command, codec, tmp_path, session_id, stop_writer=stop,
        stop_timeout_s=0.25,
    )
    assert session.stop_writer is stop
    assert stop.worst_case_s < session.stop_timeout_s
    assert session.intent_journal.path.parent.is_dir()
    assert session.evidence.path.parent.is_dir()


class FakeIndependentWriter:
    port = "/dev/ttyUSB9"
    worst_case_s = 0.20

    def __init__(self, events):
        self.events = events

    def connect(self):
        self.events.append("stop-connect")

    def __call__(self, payload):
        self.events.append("stop-write")

    def disconnect(self):
        self.events.append("stop-disconnect")


class FakeCommandTransport:
    port = "/dev/ttyACM0"

    def __init__(self, events):
        self.events = events
        self.sent = []

    def connect(self):
        self.events.append("command-connect")

    def send(self, payload):
        self.sent.append(bytes(payload))

    def receive(self, timeout_s):
        return None

    def disconnect(self):
        self.events.append("command-disconnect")


def test_session_opens_stop_endpoint_before_command_and_closes_both(tmp_path):
    session_id = str(uuid.uuid4())
    events = []
    transport = FakeCommandTransport(events)
    stop_writer = FakeIndependentWriter(events)
    codec = ProtocolV2Codec(PROTOCOL_V2_MAGIC, PROTOCOL_V2_VERSION)
    session = ProtocolV2HostSession.for_rawlog_session(
        transport, codec, tmp_path, session_id, stop_writer=stop_writer,
        stop_timeout_s=0.25,
    )

    def hello_ack(kind):
        hello = codec.decode(transport.sent[0]).message
        from measurement_310.protocol_v2 import epoch_tag_for_boot_id
        return {
            "kind": "HELLO_ACK",
            "result": 0,
            "echoed_host_nonce64": hello["host_nonce64"],
            "measurement_session_id": session_id,
            "boot_id64": 123,
            "device_epoch_tag": epoch_tag_for_boot_id(123),
            "next_sample_sequence64": 0,
        }

    session._wait_for = hello_ack
    session.start_session(session_id)
    assert events[:2] == ["stop-connect", "command-connect"]
    session.disconnect()
    assert events[-2:] == ["command-disconnect", "stop-disconnect"]


def test_real_serial_factory_rejects_missing_independent_stop_writer(tmp_path):
    session_id = str(uuid.uuid4())
    command = PySerialTransport("/dev/ttyACM0", 57600)
    codec = ProtocolV2Codec(PROTOCOL_V2_MAGIC, PROTOCOL_V2_VERSION)
    with pytest.raises(ValueError, match="dedicated independent STOP endpoint"):
        ProtocolV2HostSession.for_rawlog_session(
            command, codec, tmp_path, session_id,
        )
