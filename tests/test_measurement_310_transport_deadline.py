import sys
import types

import pytest

from measurement_310.transport import PySerialTransport, TransportError


class FakeSerial:
    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs
        self.out_waiting = 0
        self.closed = False
        self.written = []
    def write(self, payload):
        self.written.append(bytes(payload))
        return len(payload)
    def close(self):
        self.closed = True


def test_connect_passes_explicit_write_timeout(monkeypatch):
    instances = []
    def factory(*args, **kwargs):
        item = FakeSerial(*args, **kwargs)
        instances.append(item)
        return item
    monkeypatch.setitem(sys.modules, "serial", types.SimpleNamespace(Serial=factory))
    transport = PySerialTransport("mock", 57600, write_timeout_s=0.125)
    transport.connect()
    assert instances[0].kwargs["write_timeout"] == 0.125


def test_send_returns_after_driver_queue_drains(monkeypatch):
    instance = FakeSerial()
    monkeypatch.setitem(sys.modules, "serial", types.SimpleNamespace(
        Serial=lambda *args, **kwargs: instance
    ))
    transport = PySerialTransport("mock", 57600)
    transport.connect()
    transport.send(b"STOP")
    assert instance.written == [b"STOP"]


def test_send_fails_closed_when_driver_queue_does_not_drain(monkeypatch):
    instance = FakeSerial()
    instance.out_waiting = 1
    monkeypatch.setitem(sys.modules, "serial", types.SimpleNamespace(
        Serial=lambda *args, **kwargs: instance
    ))
    transport = PySerialTransport("mock", 57600, write_timeout_s=0.002)
    transport.connect()
    with pytest.raises(TransportError, match="UNKNOWN"):
        transport.send(b"STOP")


def test_short_write_is_unknown(monkeypatch):
    instance = FakeSerial()
    instance.write = lambda payload: len(payload) - 1
    monkeypatch.setitem(sys.modules, "serial", types.SimpleNamespace(
        Serial=lambda *args, **kwargs: instance
    ))
    transport = PySerialTransport("mock", 57600)
    transport.connect()
    with pytest.raises(TransportError, match="unknown"):
        transport.send(b"PWM")
