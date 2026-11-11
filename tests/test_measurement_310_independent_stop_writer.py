import threading
import uuid
from types import SimpleNamespace

import pytest

from measurement_310.protocol_v2 import (
    ProtocolV2Codec, PROTOCOL_V2_MAGIC, PROTOCOL_V2_VERSION, StopReason,
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
    def __init__(self, *args, flush_release=None, flush_started=None, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.flush_release = flush_release
        self.flush_started = flush_started
        self.writes = []
        self.flush_count = 0
        self.closed = False

    def write(self, payload):
        self.writes.append(bytes(payload))
        return len(payload)

    def flush(self):
        self.flush_count += 1
        if self.flush_started is not None:
            self.flush_started.set()
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


def test_real_serial_factory_accepts_same_uart_priority_stop_without_independent_endpoint(tmp_path):
    session_id = str(uuid.uuid4())
    command = PySerialTransport("/dev/ttyACM0", 57600)
    codec = ProtocolV2Codec(PROTOCOL_V2_MAGIC, PROTOCOL_V2_VERSION)
    session = ProtocolV2HostSession.for_rawlog_session(
        command, codec, tmp_path, session_id,
    )
    assert session.stop_writer is None
    assert callable(command.send_stop_priority)


def test_real_serial_factory_still_rejects_transport_without_any_priority_stop(tmp_path):
    class SerialTransportWithoutPriority:
        port = "/dev/ttyACM0"

        def connect(self):
            pass

        def disconnect(self):
            pass

        def send(self, payload):
            pass

        def receive(self, timeout_s):
            return None

    session_id = str(uuid.uuid4())
    codec = ProtocolV2Codec(PROTOCOL_V2_MAGIC, PROTOCOL_V2_VERSION)
    with pytest.raises(ValueError, match="same-UART priority STOP support"):
        ProtocolV2HostSession.for_rawlog_session(
            SerialTransportWithoutPriority(), codec, tmp_path, session_id,
        )


def test_concurrent_stop_write_is_rejected_without_frame_interleaving(monkeypatch):
    release = threading.Event()
    started = threading.Event()
    fake = FakeSerialPort(flush_release=release, flush_started=started)
    monkeypatch.setitem(__import__("sys").modules, "serial",
                        SimpleNamespace(Serial=lambda *a, **k: fake))
    writer = IndependentPySerialStopWriter(
        "/dev/ttyUSB-stop", write_timeout_s=0.1, flush_timeout_s=0.5
    )
    writer.connect()
    errors = []
    worker = threading.Thread(target=lambda: writer(b"FIRST-STOP"))
    worker.start()
    assert started.wait(0.2)
    with pytest.raises(TransportError, match="already in progress"):
        writer(b"SECOND-STOP")
    assert fake.writes == [b"FIRST-STOP"]
    release.set()
    worker.join(0.5)
    assert not worker.is_alive()
    assert fake.writes == [b"FIRST-STOP"]


def test_independent_stop_tty_survives_command_tty_tx_timeout(tmp_path):
    import os
    import pty
    import select

    pytest.importorskip("serial")
    command_master, command_slave = pty.openpty()
    stop_master, stop_slave = pty.openpty()
    command_path = os.ttyname(command_slave)
    stop_path = os.ttyname(stop_slave)
    os.close(command_slave)
    os.close(stop_slave)
    command = PySerialTransport(
        command_path, 57600, timeout_s=0, write_timeout_s=0.02
    )
    stop = IndependentPySerialStopWriter(
        stop_path, 57600, write_timeout_s=0.05, flush_timeout_s=0.05
    )
    try:
        command.connect()
        stop.connect()
        with pytest.raises(TransportError):
            command.send(b"C" * 1_000_000)
        # The command tty write has timed out. The protocol session must still
        # send a framed STOP_REQ on the separate tty.
        session_id = str(uuid.uuid4())
        codec = ProtocolV2Codec(PROTOCOL_V2_MAGIC, PROTOCOL_V2_VERSION)
        session = ProtocolV2HostSession.for_rawlog_session(
            command, codec, tmp_path, session_id, stop_writer=stop,
            stop_timeout_s=0.25,
        )
        session.send_stop_best_effort(stop_reason=int(StopReason.OPERATOR_REQUEST))
        ready, _, _ = select.select([stop_master], [], [], 0.5)
        assert ready
        frame = os.read(stop_master, 256)
        decoded = codec.decode(frame).message
        assert decoded["kind"] == "STOP_REQ"
        assert decoded["stop_reason"] == int(StopReason.OPERATOR_REQUEST)
    finally:
        command.disconnect()
        stop.disconnect()
        os.close(command_master)
        os.close(stop_master)


def test_direct_protocol_session_constructor_cannot_bypass_stop_endpoint_guard(tmp_path):
    command = PySerialTransport("/dev/ttyACM0", 57600)
    stop = IndependentPySerialStopWriter("/dev/ttyACM0")
    codec = ProtocolV2Codec(PROTOCOL_V2_MAGIC, PROTOCOL_V2_VERSION)
    with pytest.raises(ValueError, match="physically distinct"):
        ProtocolV2HostSession(
            command, codec,
            DurableIntentJournal(tmp_path / "intent.jsonl"),
            TransportEvidenceJournal(tmp_path / "transport-evidence.jsonl"),
            stop_writer=stop,
        )
