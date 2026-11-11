"""Transport abstraction. Wire format is deliberately injected, not specified here."""
from __future__ import annotations
from dataclasses import dataclass
import os
import threading
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
                 write_timeout_s: float = 0.10):
        if (not port or baudrate <= 0 or timeout_s < 0
                or write_timeout_s <= 0):
            raise ValueError("invalid serial configuration")
        self.port, self.baudrate, self.timeout_s = port, baudrate, timeout_s
        self.write_timeout_s = write_timeout_s
        self._serial = None
        self._flush_failed = False
        # Only the short serial.write() call is protected by this lock.
        # flush() is deliberately outside it so priority STOP can be written
        # while a normal sender is waiting for the UART TX queue to drain.
        self._write_lock = threading.Lock()
        self._state_lock = threading.Lock()
        self._stop_requested = False

    def connect(self) -> None:
        if self._serial is not None:
            return
        try:
            import serial
            self._serial = serial.Serial(self.port, self.baudrate, timeout=self.timeout_s,
                                         write_timeout=self.write_timeout_s)
            self._flush_failed = False
        except Exception as exc:
            raise TransportError(f"serial connect failed: {exc}") from exc

    def disconnect(self) -> None:
        if self._serial is not None:
            try:
                self._serial.close()
            finally:
                self._serial = None

    def _flush_with_deadline(self, timeout_s: float, *, label: str) -> None:
        # pySerial.flush() has no timeout parameter. Keep it off the write lock:
        # an urgent STOP may append its complete frame while this waiter drains.
        finished = threading.Event()
        flush_errors = []
        def flush_worker():
            try:
                self._serial.flush()
            except Exception as exc:
                flush_errors.append(exc)
            finally:
                finished.set()
        worker = threading.Thread(target=flush_worker, name=f"310-{label}-flush", daemon=True)
        worker.start()
        if not finished.wait(max(0.0, timeout_s)):
            self._flush_failed = True
            raise TransportError(f"{label} flush deadline expired; delivery outcome unknown")
        if flush_errors:
            self._flush_failed = True
            raise TransportError(f"{label} flush failed; delivery outcome unknown: {flush_errors[0]}")

    def send(self, payload: bytes) -> None:
        if self._serial is None:
            raise TransportError("serial port is not connected")
        with self._state_lock:
            if self._stop_requested:
                raise TransportError("STOP has priority; normal TX is permanently inhibited")
        if self._flush_failed:
            raise TransportError("serial TX flush previously timed out; delivery outcome unknown")
        acquired = self._write_lock.acquire(timeout=self.write_timeout_s)
        if not acquired:
            raise TransportError("serial TX writer deadline expired; delivery outcome unknown")
        try:
            with self._state_lock:
                if self._stop_requested:
                    raise TransportError("STOP has priority; normal TX is permanently inhibited")
            written = self._serial.write(payload)
            if written != len(payload):
                self._flush_failed = True
                raise TransportError("short serial write; delivery outcome unknown")
        except Exception as exc:
            self._flush_failed = True
            raise TransportError(f"serial send failed: {exc}") from exc
        finally:
            self._write_lock.release()
        try:
            self._flush_with_deadline(self.write_timeout_s, label="serial")
        except Exception as exc:
            raise TransportError(f"serial send failed: {exc}") from exc

    def send_stop_priority(self, payload: bytes, *, timeout_s: float = 0.25) -> None:
        """Send STOP ahead of queued normal frames on this one UART.

        The write lock covers only an in-flight serial.write(), never flush(),
        RawLog work, or a normal command queue. A leading COBS delimiter safely
        terminates any partial frame before STOP. Once requested, all later
        normal writes are rejected. Caller wait is bounded; a timeout is UNKNOWN.
        This is transport priority, not an independent electrical stop.
        """
        if self._serial is None:
            raise TransportError("serial port is not connected; STOP outcome unknown")
        if (not isinstance(payload, (bytes, bytearray, memoryview)) or not payload
                or timeout_s <= 0):
            raise ValueError("STOP payload and positive timeout are required")
        with self._state_lock:
            self._stop_requested = True

        finished = threading.Event()
        errors = []

        def stop_worker():
            acquired = self._write_lock.acquire(
                timeout=max(0.0, min(timeout_s, self.write_timeout_s))
            )
            if not acquired:
                errors.append(TransportError(
                    "STOP could not acquire the bounded in-flight serial writer"
                ))
                finished.set()
                return
            try:
                # An empty COBS delimiter is ignored after a complete frame and
                # discards an incomplete one. STOP is never spliced mid-frame.
                stop_wire = b"\x00" + bytes(payload)
                written = self._serial.write(stop_wire)
                if written != len(stop_wire):
                    raise TransportError("short priority STOP write; delivery outcome unknown")
            except Exception as exc:
                errors.append(exc)
                finished.set()
                self._write_lock.release()
                return
            self._write_lock.release()
            try:
                # This flush may overlap a normal sender's flush waiter. The
                # single write lock still guarantees serialized frame bytes.
                self._serial.flush()
            except Exception as exc:
                errors.append(exc)
            finally:
                finished.set()

        worker = threading.Thread(target=stop_worker, name="310-priority-stop", daemon=True)
        worker.start()
        if not finished.wait(timeout_s):
            self._flush_failed = True
            raise TransportError("priority STOP deadline expired; delivery outcome unknown")
        if errors:
            self._flush_failed = True
            raise TransportError(f"priority STOP outcome unknown: {errors[0]}") from errors[0]

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

class IndependentPySerialStopWriter:
    """Dedicated pySerial endpoint for STOP; never shares the command transport.

    This class is intentionally separate from PySerialTransport. Configure it
    only for a dedicated external safety-controller endpoint that can assert the
    hardware inhibit independently of the motor command UART. A different path
    does not by itself prove electrical independence or driver cutoff; those
    require a reviewed wiring design and physical qualification. A pathname
    resolving to the same tty is rejected by for_rawlog_session.
    """
    def __init__(self, port: str, baudrate: int = 57600,
                 write_timeout_s: float = 0.10, flush_timeout_s: float = 0.10):
        if not port or baudrate <= 0 or write_timeout_s <= 0 or flush_timeout_s <= 0:
            raise ValueError("invalid independent STOP serial configuration")
        self.port = os.path.realpath(port)
        self.baudrate = baudrate
        self.write_timeout_s = write_timeout_s
        self.flush_timeout_s = flush_timeout_s
        self.worst_case_s = write_timeout_s + flush_timeout_s
        self._serial = None
        self._failed = False
        self._write_lock = threading.Lock()

    def connect(self) -> None:
        if self._serial is not None:
            return
        if self._failed:
            raise TransportError("independent STOP writer is fail-closed")
        try:
            import serial
            self._serial = serial.Serial(
                self.port, self.baudrate, timeout=0,
                write_timeout=self.write_timeout_s,
            )
        except Exception as exc:
            self._failed = True
            raise TransportError(f"independent STOP serial connect failed: {exc}") from exc

    def __call__(self, payload: bytes) -> None:
        if not self._write_lock.acquire(blocking=False):
            raise TransportError("independent STOP write already in progress; outcome unresolved")
        try:
            if self._serial is None:
                raise TransportError("independent STOP serial endpoint is not connected")
            if self._failed:
                raise TransportError("independent STOP writer is fail-closed")
            try:
                written = self._serial.write(payload)
                if written != len(payload):
                    raise TransportError("short independent STOP write; outcome unknown")
                finished = threading.Event()
                errors = []
                def flush_worker():
                    try:
                        self._serial.flush()
                    except Exception as exc:
                        errors.append(exc)
                    finally:
                        finished.set()
                worker = threading.Thread(
                    target=flush_worker, name="310-independent-stop-flush", daemon=True
                )
                worker.start()
                if not finished.wait(self.flush_timeout_s):
                    raise TimeoutError("independent STOP flush deadline expired; outcome unknown")
                if errors:
                    raise TransportError(f"independent STOP flush failed: {errors[0]}")
            except Exception as exc:
                self._failed = True
                raise TransportError(f"independent STOP write outcome unknown: {exc}") from exc
        finally:
            self._write_lock.release()

    def disconnect(self) -> None:
        if self._serial is not None:
            try:
                self._serial.close()
            finally:
                self._serial = None


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
