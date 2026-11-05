"""Transport abstraction. Wire format is deliberately injected, not specified here."""
from __future__ import annotations
from dataclasses import dataclass
import time
from typing import Optional, Protocol

class TransportError(RuntimeError):
    pass

class IncompleteMessage(Exception):
    """Codec signal that buffered bytes do not yet contain a complete frame."""

@dataclass(frozen=True)
class DecodedFrame:
    """One decoded message and the exact number of input bytes it consumed."""
    message: object
    consumed_bytes: int

class MessageCodec(Protocol):
    """310-4 supplies the concrete wire protocol implementation."""
    def encode_pwm(self, pwm: int) -> bytes: ...
    def encode_stop(self) -> bytes: ...
    def decode(self, payload: bytes) -> object:
        """Return DecodedFrame for streams; raise IncompleteMessage if partial.

        Legacy single-frame codecs may return a mapping and consume the full buffer.
        """
        ...

class SerialTransport(Protocol):
    def connect(self) -> None: ...
    def disconnect(self) -> None: ...
    def send(self, payload: bytes) -> None: ...
    def receive(self, timeout_s: float) -> Optional[bytes]: ...

class PySerialTransport:
    """Lazy pySerial adapter; construction never opens a port."""
    def __init__(self, port: str, baudrate: int, timeout_s: float = 0.1,
                 write_timeout_s: float = 0.25):
        if (not port or baudrate <= 0 or timeout_s < 0
                or write_timeout_s <= 0):
            raise ValueError("invalid serial configuration")
        self.port, self.baudrate, self.timeout_s = port, baudrate, timeout_s
        self.write_timeout_s = write_timeout_s
        self._serial = None

    def connect(self) -> None:
        if self._serial is not None:
            return
        try:
            import serial
            self._serial = serial.Serial(self.port, self.baudrate, timeout=self.timeout_s,
                                         write_timeout=self.write_timeout_s)
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
            if written != len(payload):
                raise TransportError("short serial write; delivery outcome unknown")
            # pySerial.flush() has no caller-supplied deadline. Poll the driver
            # queue instead so a blocked TX drain cannot hold the controller
            # forever. A timeout remains an UNKNOWN delivery outcome.
            deadline = time.monotonic() + self.write_timeout_s
            while self._serial.out_waiting:
                if time.monotonic() >= deadline:
                    raise TransportError("serial TX drain deadline expired; delivery outcome unknown")
                time.sleep(0.001)
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
    """Protocol-neutral client with separate ACK and unsolicited-message paths.

    The injected codec owns framing and firmware grammar. Non-ACK messages are
    retained in arrival order and can be consumed with poll_message(); they are
    never mistaken for ACKs or silently discarded.
    """
    def __init__(self, transport: SerialTransport, codec: MessageCodec):
        self.transport, self.codec = transport, codec
        self.connected = False
        self._receive_buffer = bytearray()
        self._pending_messages: list[object] = []
        self._pending_acks: list[tuple[int, str]] = []

    def connect(self):
        self.transport.connect()
        self.connected = True

    def disconnect(self):
        try:
            self.transport.disconnect()
        finally:
            self.connected = False
            self._receive_buffer.clear()
            self._pending_messages.clear()
            self._pending_acks.clear()

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

    def _decode_buffered_message(self) -> tuple[bool, object]:
        if not self._receive_buffer:
            return False, None
        try:
            decoded = self.codec.decode(bytes(self._receive_buffer))
        except IncompleteMessage:
            return False, None
        if isinstance(decoded, DecodedFrame):
            consumed = decoded.consumed_bytes
            if (not isinstance(consumed, int) or isinstance(consumed, bool)
                    or consumed <= 0 or consumed > len(self._receive_buffer)):
                raise TransportError("codec returned invalid consumed byte count")
            del self._receive_buffer[:consumed]
            return True, decoded.message
        # Compatibility for legacy codecs: one mapping consumes the whole buffer.
        self._receive_buffer.clear()
        return True, decoded

    def _receive_one(self, timeout_s: float) -> tuple[bool, object]:
        """Return one decoded message, first draining already-buffered frames."""
        if not self.connected:
            raise TransportError("device connection is unavailable")
        try:
            available, message = self._decode_buffered_message()
            if available:
                return True, message
            payload = self.transport.receive(timeout_s)
            if payload is not None:
                if not isinstance(payload, (bytes, bytearray, memoryview)):
                    raise TransportError("transport returned non-byte payload")
                self._receive_buffer.extend(payload)
            return self._decode_buffered_message()
        except TransportError:
            raise
        except Exception as exc:
            raise TransportError(f"response receive/decode failed: {exc}") from exc

    @staticmethod
    def _ack_value(message: object) -> Optional[int]:
        if not isinstance(message, dict) or message.get("kind") != "PWM_ACK":
            return None
        pwm = message.get("pwm")
        if not isinstance(pwm, int) or isinstance(pwm, bool) or not 0 <= pwm <= 30:
            raise TransportError("invalid ACK PWM")
        return pwm

    @staticmethod
    def _host_received_utc() -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    def poll_message(self, timeout_s: float = 0.0):
        """Return the next non-ACK message; ACKs remain available to poll_ack()."""
        if not self.connected:
            raise TransportError("device connection is unavailable")
        if self._pending_messages:
            return self._pending_messages.pop(0)
        first_read = True
        while True:
            available, message = self._receive_one(timeout_s if first_read else 0.0)
            first_read = False
            if not available:
                return None
            pwm = self._ack_value(message)
            if pwm is not None:
                self._pending_acks.append((pwm, self._host_received_utc()))
                continue
            return message

    def poll_ack(self, timeout_s: float = 0.0):
        """Find the next PWM_ACK while preserving every other decoded message."""
        if not self.connected:
            raise TransportError("device connection is unavailable")
        if self._pending_acks:
            return self._pending_acks.pop(0)
        first_read = True
        while True:
            available, message = self._receive_one(timeout_s if first_read else 0.0)
            first_read = False
            if not available:
                return None
            pwm = self._ack_value(message)
            if pwm is not None:
                return pwm, self._host_received_utc()
            # Telemetry and unknown message kinds are preserved for the caller.
            self._pending_messages.append(message)
