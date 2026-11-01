"""Transport abstraction. Wire format is deliberately injected, not specified here."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Protocol

class TransportError(RuntimeError):
    pass

class IncompleteMessage(Exception):
    """Codec signal that buffered bytes do not yet contain a complete frame."""

class MessageCodec(Protocol):
    """310-4 supplies the concrete wire protocol implementation."""
    def encode_pwm(self, pwm: int) -> bytes: ...
    def encode_stop(self) -> bytes: ...
    def decode(self, payload: bytes) -> object:
        """Decode one complete frame; raise IncompleteMessage for partial data."""
        ...

class SerialTransport(Protocol):
    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def send(self, payload: bytes) -> None: ...
    def receive(self, timeout_s: float) -> Optional[bytes]: ...

class PySerialTransport:
    """Lazy pySerial adapter; construction never opens a port."""
    def __init__(self, port: str, baudrate: int, timeout_s: float = 0.1):
        if not port or baudrate <= 0 or timeout_s < 0:
            raise ValueError("invalid serial configuration")
        self.port, self.baudrate, self.timeout_s = port, baudrate, timeout_s
        self._serial = None

    def connect(self) -> None:
        if self._serial is not None:
            return
        try:
            import serial
            self._serial = serial.Serial(self.port, self.baudrate, timeout=self.timeout_s)
        except Exception as exc:
            raise TransportError(f"serial connect failed: {exc}") from exc

    def disconnect(self) -> None:
        if self._serial is not None:
            try:
                self._serial.close()
            finally:
                self._serial = None

    def send(self, payload: bytes) -> None:
        if self._serial is None:
            raise TransportError("serial port is not connected")
        try:
            written = self._serial.write(payload)
            self._serial.flush()
            if written != len(payload):
                raise TransportError("short serial write")
        except Exception as exc:
            raise TransportError(f"serial send failed: {exc}") from exc

    def receive(self, timeout_s: float) -> Optional[bytes]:
        if self._serial is None:
            raise TransportError("serial port is not connected")
        try:
            self._serial.timeout = timeout_s
            available = self._serial.in_waiting
            data = self._serial.read(available if available > 0 else 1)
            return data or None
        except Exception as exc:
            raise TransportError(f"serial receive failed: {exc}") from exc

@dataclass
class MockTransport:
    """Deterministic in-memory transport for tests; never opens a device."""
    connected: bool = False
    fail_connect: bool = False
    fail_send: bool = False
    fail_receive: bool = False
    incoming: list[bytes] | None = None
    sent: list[bytes] | None = None

    def __post_init__(self):
        self.incoming = [] if self.incoming is None else self.incoming
        self.sent = [] if self.sent is None else self.sent

    def connect(self):
        if self.fail_connect:
            raise TransportError("mock connect failure")
        self.connected = True

    def disconnect(self):
        self.connected = False

    def send(self, payload: bytes):
        if not self.connected or self.fail_send:
            raise TransportError("mock send failure or disconnected")
        self.sent.append(bytes(payload))

    def receive(self, timeout_s: float):
        if not self.connected or self.fail_receive:
            raise TransportError("mock receive failure or disconnected")
        return self.incoming.pop(0) if self.incoming else None

    def queue(self, payload: bytes):
        self.incoming.append(bytes(payload))

class ProtocolClient:
    """Protocol-neutral client. Codec owns framing and firmware grammar.

    Codec output is normalized to a mapping such as
    {"kind": "PWM_ACK", "pwm": 12}. Host receipt time is captured here.
    This is an internal adapter contract, not a wire-format decision.
    """
    def __init__(self, transport: SerialTransport, codec: MessageCodec):
        self.transport, self.codec = transport, codec
        self.connected = False
        self._receive_buffer = bytearray()

    def connect(self):
        self.transport.connect()
        self.connected = True

    def disconnect(self):
        try:
            self.transport.disconnect()
        finally:
            self.connected = False
            self._receive_buffer.clear()

    def send_pwm(self, pwm: int) -> str:
        if not self.connected:
            raise TransportError("device connection is unavailable")
        if not isinstance(pwm, int) or isinstance(pwm, bool) or not 0 <= pwm <= 30:
            raise ValueError("PWM must be integer 0..30")
        try:
            self.transport.send(self.codec.encode_pwm(pwm))
        except Exception as exc:
            raise TransportError(f"PWM command send failed: {exc}") from exc
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    def send_stop(self):
        if not self.connected:
            raise TransportError("device connection is unavailable")
        try:
            self.transport.send(self.codec.encode_stop())
        except Exception as exc:
            raise TransportError(f"STOP command send failed: {exc}") from exc

    def poll_ack(self, timeout_s: float = 0.0):
        if not self.connected:
            raise TransportError("device connection is unavailable")
        try:
            payload = self.transport.receive(timeout_s)
            if payload is not None:
                if not isinstance(payload, (bytes, bytearray, memoryview)):
                    raise TransportError("transport returned non-byte payload")
                self._receive_buffer.extend(payload)
            if not self._receive_buffer:
                return None
            try:
                message = self.codec.decode(bytes(self._receive_buffer))
            except IncompleteMessage:
                return None
            # The codec owns frame boundaries. Do not guess delimiters here.
            self._receive_buffer.clear()
            if not isinstance(message, dict) or message.get("kind") != "PWM_ACK":
                raise TransportError("response type/format mismatch")
            pwm = message.get("pwm")
            if not isinstance(pwm, int) or isinstance(pwm, bool) or not 0 <= pwm <= 30:
                raise TransportError("invalid ACK PWM")
            from datetime import datetime, timezone
            received_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
            return pwm, received_at
        except TransportError:
            raise
        except Exception as exc:
            raise TransportError(f"response receive/decode failed: {exc}") from exc
