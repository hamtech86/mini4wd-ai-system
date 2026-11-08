"""Host-side 310-4 v0.5 handshake, command correlation and durable wire evidence.

This adapter is hardware-neutral. It does not define magic/version values,
does not claim physical output state, and requires an independently supplied
emergency STOP callback at the SequenceController boundary.
"""
from __future__ import annotations

import base64
from dataclasses import asdict
import fcntl
import hashlib
import json
import os
from pathlib import Path
import secrets
import time
import uuid
from datetime import datetime, timezone
from typing import Callable, Optional

from .command_intent import AckCorrelator, AckIdentity, CommandIdentity, DurableIntentJournal
from .protocol_v1 import MessageType, ProtocolV1Codec, ProtocolV1Error, StopReason, epoch_tag_for_boot_id
from .transport import IncompleteMessage, SerialTransport


class ProtocolV1SessionError(RuntimeError):
    pass


class TransportEvidenceJournal:
    """Append-only hash-chained JSONL; every event is file-fsynced before return."""

    FORMAT = "transport-evidence-v1"

    def __init__(self, path: os.PathLike | str):
        self.path = Path(path)
        self._cached_signature = None
        self._cached_chain_head = None

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(str(path), flags)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    @classmethod
    def for_session(cls, rawlog_root: os.PathLike | str,
                    measurement_session_id: str) -> "TransportEvidenceJournal":
        """Create the deterministic external Evidence sidecar path durably."""
        try:
            parsed = uuid.UUID(measurement_session_id)
        except (ValueError, TypeError, AttributeError) as exc:
            raise ProtocolV1SessionError("measurement_session_id must be a canonical UUID") from exc
        if str(parsed) != measurement_session_id:
            raise ProtocolV1SessionError("measurement_session_id must be a canonical UUID")
        root = Path(rawlog_root)
        if root.is_symlink() or not root.is_dir():
            raise ProtocolV1SessionError("RawLog root must be an existing real directory")
        evidence_root = root / ".transport-evidence"
        session_root = evidence_root / measurement_session_id
        for parent, child in ((root, evidence_root), (evidence_root, session_root)):
            if child.is_symlink():
                raise ProtocolV1SessionError("transport Evidence directory must not be a symlink")
            if not child.exists():
                child.mkdir(mode=0o700)
                cls._fsync_directory(parent)
            if not child.is_dir():
                raise ProtocolV1SessionError("transport Evidence path component is not a directory")
            cls._fsync_directory(child)
        return cls(session_root / "transport-evidence-v1.jsonl")

    @staticmethod
    def _canonical(value: dict) -> bytes:
        return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def _read(self) -> tuple[list[dict], str]:
        if self.path.is_symlink():
            raise ProtocolV1SessionError("transport Evidence path must not be a symlink")
        if not self.path.exists():
            return [], "0" * 64
        raw = self.path.read_bytes()
        if raw and not raw.endswith(b"\n"):
            raise ProtocolV1SessionError("transport Evidence has a torn final line")
        events, previous = [], "0" * 64
        for number, line in enumerate(raw.splitlines(), 1):
            try:
                envelope = json.loads(line.decode("utf-8"))
                body = envelope["body"]
                digest = hashlib.sha256(self._canonical(body)).hexdigest()
                required = {
                    "format", "schema_version", "event_id", "event", "event_type",
                    "measurement_session_id", "device_epoch_id", "host_received_at_utc",
                    "host_received_monotonic_ns", "host_event_at_utc",
                    "host_event_monotonic_ns", "direction", "payload", "previous_hash",
                }
                uuid.UUID(body["event_id"])
                if (set(envelope) != {"body", "sha256"} or not required.issubset(body)
                        or envelope["sha256"] != digest or body["previous_hash"] != previous
                        or body["format"] != self.FORMAT or body["schema_version"] != self.FORMAT
                        or body["direction"] not in {"host_to_device", "device_to_host", "host_internal"}):
                    raise ValueError("hash chain/common schema mismatch")
                events.append(body)
                previous = digest
            except (ValueError, KeyError, TypeError, UnicodeError) as exc:
                raise ProtocolV1SessionError(f"transport Evidence record {number} is untrusted: {exc}") from exc
        return events, previous

    def append(self, event: str, payload: dict, *,
               measurement_session_id: Optional[str] = None,
               device_epoch_id: Optional[str] = None,
               direction: str = "host_internal",
               host_received_at_utc: Optional[str] = None,
               host_received_monotonic_ns: Optional[int] = None) -> str:
        if not isinstance(event, str) or not event or not isinstance(payload, dict):
            raise ValueError("event and payload are required")
        if direction not in {"host_to_device", "device_to_host", "host_internal"}:
            raise ValueError("invalid Evidence direction")
        if measurement_session_id is not None and not isinstance(measurement_session_id, str):
            raise TypeError("measurement_session_id must be a string or null")
        if device_epoch_id is not None and not isinstance(device_epoch_id, str):
            raise TypeError("device_epoch_id must be a full-identity string or null")
        if host_received_monotonic_ns is not None and (
            isinstance(host_received_monotonic_ns, bool) or not isinstance(host_received_monotonic_ns, int)
            or host_received_monotonic_ns < 0
        ):
            raise ValueError("host_received_monotonic_ns must be a nonnegative integer or null")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.path.with_name(self.path.name + ".lock")
        lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            if self.path.is_symlink():
                raise ProtocolV1SessionError("transport Evidence path must not be a symlink")
            try:
                current_stat = self.path.stat()
                signature = (
                    current_stat.st_dev, current_stat.st_ino,
                    current_stat.st_size, current_stat.st_mtime_ns,
                )
            except FileNotFoundError:
                signature = None
            if signature != self._cached_signature:
                _, previous = self._read()
                if self.path.exists():
                    current_stat = self.path.stat()
                    self._cached_signature = (
                        current_stat.st_dev, current_stat.st_ino,
                        current_stat.st_size, current_stat.st_mtime_ns,
                    )
                else:
                    self._cached_signature = None
                self._cached_chain_head = previous
            else:
                previous = self._cached_chain_head or ("0" * 64)
            event_id = str(uuid.uuid4())
            event_type = {
                "FRAME_TX_INTENT": "frame_tx_intent",
                "FRAME_TX_COMPLETE": "frame_tx_complete",
                "FRAME_TX_ERROR": "frame_tx_error",
                "RX_BYTES": "frame_rx_fragment",
                "FRAME_RX_DECODED": "frame_rx_received",
                "RX_DECODE_ERROR": "protocol_error",
                "HELLO_ACK_MATCHED": "hello_ack_match",
                "STAGE_CONTEXT_MAP": "sample_context_map",
                "ACK_MATCHED": "command_ack_match",
                "RX_UNEXPECTED_MESSAGE": "unsolicited_message",
                "ACK_IDENTITY_MISMATCH": "protocol_error",
                "STOP_TX_ATTEMPT": "stop_request_tx",
                "STOP_TX_ERROR": "stop_request_tx_error",
            }.get(event, event.lower())
            event_utc = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
            event_ns = time.monotonic_ns()
            body = {
                "format": self.FORMAT, "schema_version": self.FORMAT,
                "event_id": event_id, "event": event, "event_type": event_type,
                "measurement_session_id": measurement_session_id,
                "device_epoch_id": device_epoch_id,
                "host_received_at_utc": host_received_at_utc,
                "host_received_monotonic_ns": host_received_monotonic_ns,
                "host_event_at_utc": event_utc, "host_event_monotonic_ns": event_ns,
                "direction": direction, "payload": payload, "previous_hash": previous,
            }
            digest = hashlib.sha256(self._canonical(body)).hexdigest()
            line = self._canonical({"body": body, "sha256": digest}) + b"\n"
            existed = self.path.exists()
            fd = os.open(str(self.path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            try:
                if os.write(fd, line) != len(line):
                    raise ProtocolV1SessionError("short Evidence append; durability uncertain")
                os.fsync(fd)
                current_stat = os.fstat(fd)
                self._cached_signature = (
                    current_stat.st_dev, current_stat.st_ino,
                    current_stat.st_size, current_stat.st_mtime_ns,
                )
                self._cached_chain_head = digest
            except Exception:
                self._cached_signature = None
                self._cached_chain_head = None
                raise
            finally:
                os.close(fd)
            if not existed:
                dir_fd = os.open(str(self.path.parent), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            return event_id
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)


    def append_many(self, entries: list[dict]) -> list[str]:
        """Append an ordered Evidence transaction with one file fsync.

        Each entry has the same keyword fields as append(), plus an optional
        preallocated event_id and event-time pair. All JSON lines are hash
        chained in memory, written under one exclusive lock, and become
        durable together before this method returns.
        """
        if not isinstance(entries, list) or not entries:
            raise ValueError("entries must be a non-empty list")
        prepared = []
        for entry in entries:
            if not isinstance(entry, dict):
                raise TypeError("each Evidence entry must be a dict")
            event = entry.get("event")
            payload = entry.get("payload")
            direction = entry.get("direction", "host_internal")
            measurement_session_id = entry.get("measurement_session_id")
            device_epoch_id = entry.get("device_epoch_id")
            received_utc = entry.get("host_received_at_utc")
            received_ns = entry.get("host_received_monotonic_ns")
            event_id = entry.get("event_id") or str(uuid.uuid4())
            event_utc = entry.get("host_event_at_utc")
            event_ns = entry.get("host_event_monotonic_ns")
            if not isinstance(event, str) or not event or not isinstance(payload, dict):
                raise ValueError("each Evidence entry requires event and payload")
            if direction not in {"host_to_device", "device_to_host", "host_internal"}:
                raise ValueError("invalid Evidence direction")
            if measurement_session_id is not None and not isinstance(measurement_session_id, str):
                raise TypeError("measurement_session_id must be a string or null")
            if device_epoch_id is not None and not isinstance(device_epoch_id, str):
                raise TypeError("device_epoch_id must be a string or null")
            if received_utc is not None and not isinstance(received_utc, str):
                raise TypeError("host_received_at_utc must be a string or null")
            if received_ns is not None and (
                isinstance(received_ns, bool) or not isinstance(received_ns, int) or received_ns < 0
            ):
                raise ValueError("host_received_monotonic_ns must be a nonnegative integer or null")
            if str(uuid.UUID(event_id)) != event_id:
                raise ValueError("event_id must be a canonical UUID")
            if event_utc is not None and not isinstance(event_utc, str):
                raise TypeError("host_event_at_utc must be a string or null")
            if event_ns is not None and (
                isinstance(event_ns, bool) or not isinstance(event_ns, int) or event_ns < 0
            ):
                raise ValueError("host_event_monotonic_ns must be a nonnegative integer or null")
            prepared.append((event, payload, measurement_session_id, device_epoch_id,
                             direction, received_utc, received_ns, event_id, event_utc, event_ns))

        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.path.with_name(self.path.name + ".lock")
        lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            if self.path.is_symlink():
                raise ProtocolV1SessionError("transport Evidence path must not be a symlink")
            try:
                current_stat = self.path.stat()
                signature = (current_stat.st_dev, current_stat.st_ino,
                             current_stat.st_size, current_stat.st_mtime_ns)
            except FileNotFoundError:
                signature = None
            if signature != self._cached_signature:
                _, previous = self._read()
                if self.path.exists():
                    current_stat = self.path.stat()
                    self._cached_signature = (current_stat.st_dev, current_stat.st_ino,
                                              current_stat.st_size, current_stat.st_mtime_ns)
                else:
                    self._cached_signature = None
                self._cached_chain_head = previous
            else:
                previous = self._cached_chain_head or ("0" * 64)

            lines = []
            event_ids = []
            for (event, payload, measurement_session_id, device_epoch_id, direction,
                 received_utc, received_ns, event_id, event_utc, event_ns) in prepared:
                event_type = {
                    "FRAME_TX_INTENT": "frame_tx_intent",
                    "FRAME_TX_COMPLETE": "frame_tx_complete",
                    "FRAME_TX_ERROR": "frame_tx_error",
                    "RX_BYTES": "frame_rx_fragment",
                    "FRAME_RX_DECODED": "frame_rx_received",
                    "RX_DECODE_ERROR": "protocol_error",
                    "HELLO_ACK_MATCHED": "hello_ack_match",
                    "STAGE_CONTEXT_MAP": "sample_context_map",
                    "ACK_MATCHED": "command_ack_match",
                    "RX_UNEXPECTED_MESSAGE": "unsolicited_message",
                    "ACK_IDENTITY_MISMATCH": "protocol_error",
                    "STOP_TX_ATTEMPT": "stop_request_tx",
                    "STOP_TX_ERROR": "stop_request_tx_error",
                }.get(event, event.lower())
                body = {
                    "format": self.FORMAT, "schema_version": self.FORMAT,
                    "event_id": event_id, "event": event, "event_type": event_type,
                    "measurement_session_id": measurement_session_id,
                    "device_epoch_id": device_epoch_id,
                    "host_received_at_utc": received_utc,
                    "host_received_monotonic_ns": received_ns,
                    "host_event_at_utc": event_utc or datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
                    "host_event_monotonic_ns": event_ns if event_ns is not None else time.monotonic_ns(),
                    "direction": direction, "payload": payload, "previous_hash": previous,
                }
                digest = hashlib.sha256(self._canonical(body)).hexdigest()
                lines.append(self._canonical({"body": body, "sha256": digest}) + b"\\n")
                event_ids.append(event_id)
                previous = digest

            existed = self.path.exists()
            fd = os.open(str(self.path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            try:
                view = memoryview(b"".join(lines))
                while view:
                    count = os.write(fd, view)
                    if count <= 0:
                        raise ProtocolV1SessionError("short Evidence transaction append; durability uncertain")
                    view = view[count:]
                os.fsync(fd)
                current_stat = os.fstat(fd)
                self._cached_signature = (current_stat.st_dev, current_stat.st_ino,
                                          current_stat.st_size, current_stat.st_mtime_ns)
                self._cached_chain_head = previous
            except Exception:
                self._cached_signature = None
                self._cached_chain_head = None
                raise
            finally:
                os.close(fd)
            if not existed:
                try:
                    self._fsync_directory(self.path.parent)
                except Exception:
                    self._cached_signature = None
                    self._cached_chain_head = None
                    raise
            return event_ids
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)


class ProtocolV1HostSession:
    """Strict host session adapter used by SequenceController's additive v1 path."""

    def __init__(
        self,
        transport: SerialTransport,
        codec: ProtocolV1Codec,
        tag_allocator,
        intent_journal: DurableIntentJournal,
        evidence_journal: TransportEvidenceJournal,
        *,
        stop_writer: Optional[Callable[[bytes], None]] = None,
        ack_timeout_s: float = 2.0,
        monotonic: Callable[[], float] = time.monotonic,
        utc_now: Optional[Callable[[], str]] = None,
    ):
        if ack_timeout_s <= 0:
            raise ValueError("ack_timeout_s must be positive")
        self.transport = transport
        self.codec = codec
        self.tag_allocator = tag_allocator
        self.intent_journal = intent_journal
        self.evidence = evidence_journal
        self.stop_writer = stop_writer
        self.ack_timeout_s = ack_timeout_s
        self.monotonic = monotonic
        self.utc_now = utc_now or self._utc_now
        self.measurement_session_id: Optional[str] = None
        self.session_tag: Optional[int] = None
        self.boot_id64: Optional[int] = None
        self.epoch_tag: Optional[int] = None
        self._command_id = 0
        self._stop_request_id = 0
        self._last_stop_request_id: Optional[int] = None
        self._used_stop_request_ids: set[int] = set()
        self._stop_frames: dict[int, dict] = {}
        self._rx_buffer = bytearray()
        self._messages: list[dict] = []
        self._pending: Optional[dict] = None
        self._correlator = AckCorrelator()
        self._context_map: dict[int, str] = {}
        self._armed = False
        self._failed = False

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    def _append(self, event: str, *, direction: Optional[str] = None,
                host_received_at_utc: Optional[str] = None,
                host_received_monotonic_ns: Optional[int] = None, **payload) -> str:
        if direction is None:
            if event.startswith(("FRAME_TX", "STOP_TX")):
                direction = "host_to_device"
            elif event.startswith(("RX", "ACK_", "HELLO_ACK")):
                direction = "device_to_host"
            else:
                direction = "host_internal"
        message = payload.get("message")
        if isinstance(message, dict):
            host_received_at_utc = host_received_at_utc or message.get("_host_received_at_utc")
            if host_received_monotonic_ns is None:
                host_received_monotonic_ns = message.get("_host_received_monotonic_ns")
        return self.evidence.append(
            event, {"recorded_at_utc": self.utc_now(), **payload},
            measurement_session_id=self.measurement_session_id,
            device_epoch_id=str(self.boot_id64) if self.boot_id64 is not None else None,
            direction=direction, host_received_at_utc=host_received_at_utc,
            host_received_monotonic_ns=host_received_monotonic_ns,
        )

    def _next_command_id(self) -> int:
        if self._command_id >= 0xFFFFFFFF:
            raise ProtocolV1SessionError("command_id space exhausted; wrap forbidden")
        self._command_id += 1
        return self._command_id

    def _record_frame_intent(self, frame: bytes, *, kind: str, command_id: int,
                             session_tag: int, epoch_tag: int,
                             identity: Optional[CommandIdentity] = None,
                             intent_hash: Optional[str] = None) -> None:
        self._append("FRAME_TX_INTENT", kind=kind, frame_b64=base64.b64encode(frame).decode("ascii"),
                     byte_count=len(frame), command_id=command_id,
                     measurement_session_tag=session_tag, device_epoch_tag=epoch_tag,
                     identity=asdict(identity) if identity is not None else None,
                     intent_journal_sha256=intent_hash)

    def _send_frame(self, frame: bytes, *, kind: str, command_id: int,
                    session_tag: int, epoch_tag: int,
                    identity: Optional[CommandIdentity] = None,
                    intent_hash: Optional[str] = None) -> str:
        self._record_frame_intent(frame, kind=kind, command_id=command_id,
                                  session_tag=session_tag, epoch_tag=epoch_tag,
                                  identity=identity, intent_hash=intent_hash)
        try:
            self.transport.send(frame)
            self.last_write_completed_monotonic_ns = time.monotonic_ns()
        except Exception as exc:
            try:
                self._append("FRAME_TX_ERROR", kind=kind, command_id=command_id,
                             frame_b64=base64.b64encode(frame).decode("ascii"),
                             error=str(exc), outcome="UNKNOWN",
                             identity=asdict(identity) if identity is not None else None,
                             intent_journal_sha256=intent_hash)
            finally:
                raise ProtocolV1SessionError(f"{kind} write/flush outcome unknown: {exc}") from exc
        # Capture UTC immediately after the transport write/flush has completed.
        sent_utc = self.utc_now()
        # This fsync is required before the caller can treat host transmission as complete.
        self._append("FRAME_TX_COMPLETE", kind=kind, command_id=command_id,
                     frame_b64=base64.b64encode(frame).decode("ascii"),
                     byte_count=len(frame), host_write_completed_at_utc=self.utc_now(),
                     identity=asdict(identity) if identity is not None else None,
                     intent_journal_sha256=intent_hash)
        return sent_utc

    def _pump_rx(self, timeout_s: float) -> None:
        chunk = self.transport.receive(timeout_s)
        if chunk is None:
            return
        if not isinstance(chunk, (bytes, bytearray, memoryview)):
            raise ProtocolV1SessionError("transport returned non-byte RX data")
        raw = bytes(chunk)
        if not raw:
            return
        received_utc = self.utc_now()
        received_ns = time.monotonic_ns()
        rx_evidence_event_id = self._append(
            "RX_BYTES", raw_b64=base64.b64encode(raw).decode("ascii"),
            byte_count=len(raw), host_received_at_utc=received_utc,
            host_received_monotonic_ns=received_ns)
        self._rx_buffer.extend(raw)
        while b"\x00" in self._rx_buffer:
            try:
                decoded = self.codec.decode(bytes(self._rx_buffer))
            except IncompleteMessage:
                break
            except Exception as exc:
                self._append("RX_DECODE_ERROR", buffered_byte_count=len(self._rx_buffer), error=str(exc))
                raise ProtocolV1SessionError(f"RX frame rejected: {exc}") from exc
            raw_frame = bytes(self._rx_buffer[:decoded.consumed_bytes])
            del self._rx_buffer[:decoded.consumed_bytes]
            raw_frame_b64 = base64.b64encode(raw_frame).decode("ascii")
            decoded.message["_raw_frame_base64"] = raw_frame_b64
            decoded.message["_rx_chunk_event_id"] = rx_evidence_event_id
            decoded.message["_host_received_at_utc"] = received_utc
            decoded.message["_host_received_monotonic_ns"] = received_ns
            decoded.message["_rx_frame_evidence_event_id"] = self._append(
                "FRAME_RX_DECODED", direction="device_to_host",
                host_received_at_utc=received_utc,
                host_received_monotonic_ns=received_ns,
                raw_frame_base64=raw_frame_b64,
                rx_chunk_event_id=rx_evidence_event_id,
                message_type=decoded.message.get("message_type"),
                command_id=decoded.message.get("command_id"),
            )
            decoded.message["_rx_evidence_event_id"] = decoded.message["_rx_frame_evidence_event_id"]
            self._messages.append(decoded.message)

    def _next_message(self, timeout_s: float) -> Optional[dict]:
        if self._messages:
            return self._messages.pop(0)
        if timeout_s <= 0:
            self._pump_rx(0.0)
            return self._messages.pop(0) if self._messages else None
        deadline = self.monotonic() + timeout_s
        while self.monotonic() < deadline:
            remaining = max(0.0, deadline - self.monotonic())
            self._pump_rx(remaining)
            if self._messages:
                return self._messages.pop(0)
        return None

    def _wait_for(self, expected_kind: str, timeout_s: Optional[float] = None) -> dict:
        deadline = self.monotonic() + (self.ack_timeout_s if timeout_s is None else timeout_s)
        while self.monotonic() < deadline:
            message = self._next_message(max(0.0, deadline - self.monotonic()))
            if message is None:
                continue
            if message.get("kind") == expected_kind:
                return message
            self._append("RX_UNEXPECTED_MESSAGE", message=message, expected_kind=expected_kind)
        raise ProtocolV1SessionError(f"{expected_kind} timeout; command outcome remains unresolved")

    def start_session(self, measurement_session_id: str) -> int:
        if self._failed:
            raise ProtocolV1SessionError("host protocol session is fail-closed")
        if not isinstance(measurement_session_id, str) or not measurement_session_id:
            raise ValueError("measurement_session_id is required")
        if self.measurement_session_id is not None:
            if self.measurement_session_id != measurement_session_id:
                raise ProtocolV1SessionError("host adapter cannot switch measurement session in place")
            return int(self.session_tag)
        self.measurement_session_id = measurement_session_id
        allocation = self.tag_allocator.allocate()
        self.session_tag = allocation.tag
        nonce = secrets.randbits(64) or 1
        self.transport.connect()
        frame = self.codec.encode_hello(session_tag=self.session_tag, host_nonce64=nonce)
        self._send_frame(frame, kind="HELLO", command_id=0,
                         session_tag=self.session_tag, epoch_tag=0)
        ack = self._wait_for("HELLO_ACK")
        if (ack.get("result") != 0 or ack.get("host_nonce64", ack.get("echoed_host_nonce64")) != nonce
                or ack.get("measurement_session_tag") != self.session_tag):
            self._failed = True
            raise ProtocolV1SessionError("HELLO_ACK result/nonce/session mismatch")
        boot_id = ack.get("boot_id64")
        if isinstance(boot_id, bool) or not isinstance(boot_id, int) or boot_id == 0:
            self._failed = True
            raise ProtocolV1SessionError("HELLO_ACK did not establish a valid full boot_id64")
        self.boot_id64 = boot_id
        self.epoch_tag = epoch_tag_for_boot_id(boot_id)
        if ack.get("device_epoch_tag") != self.epoch_tag:
            self._failed = True
            raise ProtocolV1SessionError("HELLO_ACK epoch correlation mismatch")
        self._append("HELLO_ACK_MATCHED", measurement_session_id=measurement_session_id,
                     measurement_session_tag=self.session_tag, boot_id64=boot_id,
                     device_epoch_tag=self.epoch_tag, host_nonce64=nonce, ack=ack)
        return self.session_tag

    def _register_and_send(self, identity: CommandIdentity, frame: bytes, kind: str) -> str:
        intent_hash = self.intent_journal.append_intent(identity, self.utc_now())
        self._correlator.register(identity)
        return self._send_frame(frame, kind=kind, command_id=int(identity.command_id),
                                session_tag=int(self.session_tag), epoch_tag=int(self.epoch_tag),
                                identity=identity, intent_hash=intent_hash)

    def _accept_identity_ack(self, message: dict, identity: CommandIdentity,
                             expected_kind: str, expected_token: int,
                             expected_pwm: Optional[int] = None) -> bool:
        if (message.get("kind") != expected_kind
                or message.get("measurement_session_tag") != self.session_tag
                or message.get("device_epoch_tag") != self.epoch_tag
                or message.get("command_id") != int(identity.command_id)):
            return False
        if expected_kind == "ARM_ACK":
            if (message.get("result") != 0 or message.get("state") != "ARMED"
                    or message.get("active_context_token") != expected_token):
                raise ProtocolV1SessionError("ARM_ACK rejected or context echo mismatch")
        else:
            if (message.get("result") != 0 or message.get("applied_pwm") != expected_pwm
                    or message.get("stage_context_token") != expected_token):
                raise ProtocolV1SessionError("APPLY_ACK rejected or PWM/context echo mismatch")
        ack_identity = AckIdentity(
            command_id=identity.command_id, command_type=identity.command_type,
            session_id=identity.session_id, boot_id64=identity.boot_id64,
            stage_context_id=identity.stage_context_id,
        )
        if not self._correlator.correlate(ack_identity):
            raise ProtocolV1SessionError("ACK full identity correlation failed")
        self._append("ACK_MATCHED", expected_kind=expected_kind,
                     command_id=int(identity.command_id), identity=asdict(identity),
                     message=message)
        return True

    def send_stage_pwm(self, pwm: int, stage_context_id: str,
                       measurement_session_id: str, stage_index: Optional[int] = None) -> str:
        try:
            return self._send_stage_pwm(pwm, stage_context_id, measurement_session_id, stage_index)
        except Exception:
            self._failed = True
            raise

    def _send_stage_pwm(self, pwm: int, stage_context_id: str,
                        measurement_session_id: str, stage_index: Optional[int] = None) -> str:
        if self._failed:
            raise ProtocolV1SessionError("host protocol session is fail-closed")
        if self._pending is not None:
            raise ProtocolV1SessionError(
                "previous PWM command outcome is unresolved; a new stage cannot be sent"
            )
        if isinstance(pwm, bool) or not isinstance(pwm, int) or not 0 <= pwm <= 30:
            raise ValueError("PWM must be integer 0..30")
        if not isinstance(stage_context_id, str) or not stage_context_id:
            raise ValueError("stage_context_id is required")
        if stage_index is None:
            stage_index = pwm
        if isinstance(stage_index, bool) or not isinstance(stage_index, int) or not 0 <= stage_index <= 30:
            raise ValueError("stage_index must be integer 0..30")
        self.start_session(measurement_session_id)
        token = stage_index + 1
        if token in self._context_map:
            raise ProtocolV1SessionError("stage context token reuse prohibited")

        # Reserve command IDs before persisting the context map so the durable
        # mapping contains the exact PWM_SET command_id required by v0.5 §5.
        arm_id = None
        if not self._armed:
            arm_id = self._next_command_id()
        command_id = self._next_command_id()
        self._context_map[token] = stage_context_id
        self._append("STAGE_CONTEXT_MAP", measurement_session_id=measurement_session_id,
                     measurement_session_tag=self.session_tag, boot_id64=self.boot_id64,
                     stage_context_token=token, stage_context_id=stage_context_id,
                     stage_id=f"PWM-{stage_index:02d}", intended_pwm=pwm,
                     command_id=command_id)

        if arm_id is not None:
            arm_identity = CommandIdentity(
                command_id=str(arm_id), command_type="ARM",
                session_id=measurement_session_id, boot_id64=int(self.boot_id64),
                stage_context_id=stage_context_id,
            )
            arm_frame = self.codec.encode_arm(
                session_tag=int(self.session_tag), epoch_tag=int(self.epoch_tag),
                command_id=arm_id, stage_context_token=token,
            )
            self._register_and_send(arm_identity, arm_frame, "ARM")
            arm_ack = self._wait_for("ARM_ACK")
            if not self._accept_identity_ack(arm_ack, arm_identity, "ARM_ACK", token):
                raise ProtocolV1SessionError("ARM_ACK identity mismatch")
            self._armed = True

        identity = CommandIdentity(
            command_id=str(command_id), command_type="PWM_SET",
            session_id=measurement_session_id, boot_id64=int(self.boot_id64),
            stage_context_id=stage_context_id,
        )
        frame = self.codec.encode_pwm_set(
            session_tag=int(self.session_tag), epoch_tag=int(self.epoch_tag),
            command_id=command_id, pwm=pwm, stage_context_token=token,
        )
        sent_utc = self._register_and_send(identity, frame, "PWM_SET")
        self._pending = {"identity": identity, "token": token, "pwm": pwm,
                         "stage_context_id": stage_context_id, "command_id": command_id}
        return sent_utc

    def poll_apply_ack(self, timeout_s: float = 0.0):
        try:
            return self._poll_apply_ack(timeout_s)
        except Exception:
            self._failed = True
            raise

    def _poll_apply_ack(self, timeout_s: float = 0.0):
        if self._failed:
            raise ProtocolV1SessionError("host protocol session is fail-closed")
        if self._pending is None:
            return None
        message = self._next_message(timeout_s)
        if message is None:
            return None
        if message.get("kind") != "APPLY_ACK":
            self._append("RX_UNEXPECTED_MESSAGE", message=message, expected_kind="APPLY_ACK")
            return None
        pending = self._pending
        identity = pending["identity"]
        try:
            if not self._accept_identity_ack(message, identity, "APPLY_ACK",
                                             pending["token"], pending["pwm"]):
                self._append("ACK_IDENTITY_MISMATCH", expected=asdict(identity), message=message)
                return None
        except Exception:
            self._failed = True
            raise
        self._pending = None
        return pending["pwm"], self.utc_now()

    @property
    def last_stop_request_id(self) -> Optional[int]:
        """Most recent logical STOP identity, including an unknown write outcome."""
        return self._last_stop_request_id

    def send_stop_best_effort(self, *, stop_reason: int, stop_request_id: Optional[int] = None) -> int:
        """Send v0.5 STOP_REQ without waiting for Evidence fsync.

        This requires a separately supplied STOP writer. It is not proof that
        the writer is bounded or that the device physically stopped. The method
        returns the logical stop_request_id on success. If the write outcome is
        unknown, last_stop_request_id remains available; retry with that same
        ID and reason to resend the byte-identical retained frame.
        """
        if self.stop_writer is None:
            raise ProtocolV1SessionError("independent STOP writer is not configured")
        valid_stop_reasons = {int(reason) for reason in StopReason}
        if (isinstance(stop_reason, bool) or not isinstance(stop_reason, int)
                or stop_reason not in valid_stop_reasons):
            raise ValueError("stop_reason must use an assigned StopReason code")
        exhausted_id = False
        if stop_request_id is None:
            if self._stop_request_id < 0xFFFF:
                self._stop_request_id += 1
            else:
                exhausted_id = True
            stop_request_id = self._stop_request_id or 0xFFFF
        if isinstance(stop_request_id, bool) or not isinstance(stop_request_id, int) or not 1 <= stop_request_id <= 0xFFFF:
            raise ValueError("stop_request_id must be nonzero uint16")
        self._last_stop_request_id = stop_request_id

        cached = self._stop_frames.get(stop_request_id)
        if cached is not None:
            session_tag = cached["session_tag"]
            epoch_tag = cached["epoch_tag"]
            if cached["stop_reason"] != stop_reason:
                raise ProtocolV1SessionError(
                    "stop_request_id already identifies a different logical STOP; allocate a new ID"
                )
            # Retry the exact same logical STOP using the byte-identical frame.
            # This preserves both command_id and stop_request_id as required by v0.5.
            command_id = cached["command_id"]
            stale_command_id = cached["stale_command_id"]
            exhausted_id = cached["stop_request_id_exhausted"]
            frame = cached["frame"]
        else:
            if stop_request_id in self._used_stop_request_ids:
                raise ProtocolV1SessionError("stop_request_id reuse is not a retry of a retained frame")
            try:
                command_id = self._next_command_id()
                stale_command_id = False
            except ProtocolV1SessionError:
                # STOP is the protocol safety exception: retain a nonzero stale
                # command identity and let firmware act on the valid STOP_REQ.
                command_id = 0xFFFFFFFF
                stale_command_id = True
            session_tag = int(self.session_tag or 0)
            epoch_tag = int(self.epoch_tag or 0)
            frame = self.codec.encode_stop_request(
                session_tag=session_tag, epoch_tag=epoch_tag, command_id=command_id,
                stop_reason=stop_reason, stop_request_id=stop_request_id,
            )
            self._used_stop_request_ids.add(stop_request_id)
            self._stop_request_id = max(self._stop_request_id, stop_request_id)
            self._stop_frames[stop_request_id] = {
                "frame": frame,
                "command_id": command_id,
                "stop_reason": stop_reason,
                "session_tag": session_tag,
                "epoch_tag": epoch_tag,
                "stale_command_id": stale_command_id,
                "stop_request_id_exhausted": exhausted_id,
            }
        attempted_at = self.utc_now()
        try:
            # Safety STOP is deliberately sent on the separate injected path
            # before any journal fsync; it never shares the command transport.
            self.stop_writer(frame)
            outcome = "HOST_WRITE_COMPLETED"
            error = None
        except Exception as exc:
            outcome = "HOST_WRITE_FAILED_UNKNOWN"
            error = str(exc)
            try:
                self._append("STOP_TX_ERROR", frame_b64=base64.b64encode(frame).decode("ascii"),
                             command_id=command_id, stop_request_id=stop_request_id,
                             stop_reason=stop_reason, attempted_at_utc=attempted_at,
                             outcome=outcome, error=error,
                             stale_command_id=stale_command_id,
                             stop_request_id_exhausted=exhausted_id)
            except Exception:
                pass
            raise ProtocolV1SessionError(f"STOP_REQ write outcome unknown: {exc}") from exc
        try:
            self._append("STOP_TX_ATTEMPT", frame_b64=base64.b64encode(frame).decode("ascii"),
                         byte_count=len(frame), command_id=command_id,
                         stop_request_id=stop_request_id, stop_reason=stop_reason,
                         measurement_session_tag=session_tag, device_epoch_tag=epoch_tag,
                         attempted_at_utc=attempted_at, outcome=outcome,
                         stale_command_id=stale_command_id,
                         stop_request_id_exhausted=exhausted_id)
        except Exception:
            # The output-zero request has already been attempted; Evidence failure
            # must not retroactively block or repeat the safety transmission.
            pass
        return stop_request_id

    def latch_abort(self, reason: str) -> None:
        """In-memory fail-closed latch; deliberately performs no storage or I/O."""
        self._failed = True
        if self._pending is not None:
            identity = self._pending.get("identity")
            if identity is not None:
                self._correlator.expire(identity.command_id)
            self._pending = None

    def disconnect(self) -> None:
        self.transport.disconnect()
