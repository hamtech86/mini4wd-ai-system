"""Transport abstraction. Wire format is deliberately injected, not specified here."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Protocol


class TransportError(RuntimeError):
    pass


class MessageCodec(Protocol):
    """310-4 supplies the concrete wire protocol implementation."""
    def encode_pwm(self, pwm: int) -> bytes: ...
    def encode_stop(self) -> bytes: ...
    def decode(self, payload: bytes) -> object: ...


class SerialTransport(Protocol):
    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def send(self, payload: bytes) -> None: ...
    def receive(self, timeout_s: float) -> Optional[bytes]: ...


@dataclass
class MockTransport:
    """Deterministic in-memory transport for tests; never opens a device."""
    connected: bool = False
    fail_connect: bool = False
    fail_send: bool = False
    fail_receive: bool = False
    incoming: list[bytes] | None = None
    sent: list[bytes] | None = None

    def __post_init__(self) -> None:
        self.incoming = [] if self.incoming is None else self.incoming
        self.sent = [] if self.sent is None else self.sent

    def connect(self) -> None:
        if self.fail_connect:
            raise TransportError("mock connect failure")
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False

    def send(self, payload: bytes) -> None:
        if not self.connected or self.fail_send:
            raise TransportError("mock send failure or disconnected")
        self.sent.append(bytes(payload))

    def receive(self, timeout_s: float) -> Optional[bytes]:
        if not self.connected or self.fail_receive:
            raise TransportError("mock receive failure or disconnected")
        return self.incoming.pop(0) if self.incoming else None

    def queue(self, payload: bytes) -> None:
        self.incoming.append(bytes(payload))
