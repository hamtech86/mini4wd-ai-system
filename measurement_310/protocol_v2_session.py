"""Host-side protocol v2 session: UUID identity, device-owned sequence and durable ACK gate."""
from __future__ import annotations

import base64
from dataclasses import asdict
import os
import stat
import secrets
import time
import threading
import uuid
from typing import Callable, Optional

from .command_intent import AckCorrelator, AckIdentity, CommandIdentity, DurableIntentJournal
from .epoch_checkpoint import CheckpointStatus
from .device_loss_accounting import DeviceLossAccountingError, DeviceLossWindowAccumulator
from .protocol_v1_session import TransportEvidenceJournal
from .protocol_v2 import (
    DriveDirection, MessageType, ProtocolV2Codec, ProtocolV2Error, StopReason, epoch_tag_for_boot_id,
)
from .sequence_reconciliation import (
    SequenceReconciliationStatus, reconcile_device_sequence,
)
from .transport import IncompleteMessage, SerialTransport


class ProtocolV2SessionError(RuntimeError):
    pass


class ProtocolV2HostSession:
    """Strict v2 host adapter. No persistent session-tag allocator is used."""

    supports_stage_direction = True

    @staticmethod
    def _validate_stop_writer_binding(transport, stop_writer, stop_timeout_s: float) -> None:
        command_port = getattr(transport, "port", None)
        if command_port is None:
            return
        stop_port = getattr(stop_writer, "port", None)
        worst_case = getattr(stop_writer, "worst_case_s", None)
        if stop_writer is None or not callable(stop_writer) or not stop_port:
            raise ValueError("real serial transport requires a dedicated independent STOP endpoint")
        command_real = os.path.realpath(str(command_port))
        stop_real = os.path.realpath(str(stop_port))
        if command_real == stop_real:
            raise ValueError("STOP endpoint must be physically distinct from command serial port")
        try:
            command_stat = os.stat(command_real)
            stop_stat = os.stat(stop_real)
        except FileNotFoundError:
            command_stat = stop_stat = None
        if (command_stat is not None and stop_stat is not None
                and stat.S_ISCHR(command_stat.st_mode) and stat.S_ISCHR(stop_stat.st_mode)
                and command_stat.st_rdev == stop_stat.st_rdev):
            raise ValueError("STOP endpoint resolves to the same character device as command serial")
        if (isinstance(worst_case, bool) or not isinstance(worst_case, (int, float))
                or worst_case <= 0 or worst_case >= stop_timeout_s):
            raise ValueError("independent STOP writer worst-case bound must be below STOP caller deadline")

    def __init__(
        self,
        transport: SerialTransport,
        codec: ProtocolV2Codec,
        intent_journal: DurableIntentJournal,
        evidence_journal: TransportEvidenceJournal,
        *,
        stop_writer: Optional[Callable[[bytes], None]] = None,
        ack_timeout_s: float = 2.0,
        stop_timeout_s: float = 0.25,
        monotonic: Callable[[], float] = time.monotonic,
        utc_now: Optional[Callable[[], str]] = None,
    ):
        if ack_timeout_s <= 0 or stop_timeout_s <= 0:
            raise ValueError("ACK and STOP timeouts must be positive")
        self._validate_stop_writer_binding(transport, stop_writer, stop_timeout_s)
        self.transport = transport
        self.codec = codec
        self.intent_journal = intent_journal
        self.evidence = evidence_journal
        self.stop_writer = stop_writer
        self.ack_timeout_s = ack_timeout_s
        self.stop_timeout_s = stop_timeout_s
        self.monotonic = monotonic
        self.utc_now = utc_now or self._utc_now
        self.measurement_session_id: Optional[str] = None
        self._storage_session_id: Optional[str] = None
        self.boot_id64: Optional[int] = None
        self.epoch_tag: Optional[int] = None
        self.next_sample_sequence64: Optional[int] = None
        self.sequence_reconciliation = None
        self._command_id = 0
        self._stop_request_id = 0
        self._last_stop_request_id: Optional[int] = None
        self._used_stop_request_ids: set[int] = set()
        self._stop_frames: dict[int, dict] = {}
        self._rx_buffer = bytearray()
        self._messages: list[dict] = []
        self._telemetry_queue: list[dict] = []
        self._pending: Optional[dict] = None
        self._correlator = AckCorrelator()
        self._context_map: dict[int, str] = {}
        self._armed = False
        self._active_stage: Optional[dict] = None
        self._loss_accumulator: Optional[DeviceLossWindowAccumulator] = None
        self._failed = False

    @classmethod
    def for_rawlog_session(
        cls, transport: SerialTransport, codec: ProtocolV2Codec,
        rawlog_root, measurement_session_id: str, *,
        stop_writer: Optional[Callable[[bytes], None]] = None,
        ack_timeout_s: float = 2.0, stop_timeout_s: float = 0.25,
        monotonic: Callable[[], float] = time.monotonic,
        utc_now: Optional[Callable[[], str]] = None,
    ) -> "ProtocolV2HostSession":
        """Bind sidecars and require a distinct STOP endpoint for real serial transports."""
        cls._validate_stop_writer_binding(transport, stop_writer, stop_timeout_s)
        intent = DurableIntentJournal.for_session(rawlog_root, measurement_session_id)
        evidence = TransportEvidenceJournal.for_session(rawlog_root, measurement_session_id)
        session = cls(
            transport, codec, intent, evidence, stop_writer=stop_writer,
            ack_timeout_s=ack_timeout_s, stop_timeout_s=stop_timeout_s,
            monotonic=monotonic, utc_now=utc_now,
        )
        session._storage_session_id = measurement_session_id
        return session

    @staticmethod
    def _utc_now() -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    def _append(self, event: str, *, direction: Optional[str] = None,
                host_received_at_utc: Optional[str] = None,
                host_received_monotonic_ns: Optional[int] = None, **payload) -> str:
        if direction is None:
            if event.startswith(("FRAME_TX", "STOP_TX")):
                direction = "host_to_device"
            elif event.startswith(("RX", "ACK_", "HELLO_ACK", "ADC_")):
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
            raise ProtocolV2SessionError("command_id space exhausted; wrap forbidden")
        self._command_id += 1
        return self._command_id

    def _send_frame(self, frame: bytes, *, kind: str, command_id: int,
                    identity: Optional[CommandIdentity] = None,
                    intent_hash: Optional[str] = None) -> str:
        self._append("FRAME_TX_INTENT", kind=kind, frame_b64=base64.b64encode(frame).decode("ascii"),
                     byte_count=len(frame), command_id=command_id,
                     measurement_session_id=self.measurement_session_id,
                     device_epoch_tag=self.epoch_tag,
                     identity=asdict(identity) if identity is not None else None,
                     intent_journal_sha256=intent_hash)
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
                raise ProtocolV2SessionError(f"{kind} write/flush outcome unknown: {exc}") from exc
        sent_utc = self.utc_now()
        self._append("FRAME_TX_COMPLETE", kind=kind, command_id=command_id,
                     frame_b64=base64.b64encode(frame).decode("ascii"),
                     byte_count=len(frame), host_write_completed_at_utc=sent_utc,
                     identity=asdict(identity) if identity is not None else None,
                     intent_journal_sha256=intent_hash)
        return sent_utc

    def _pump_rx(self, timeout_s: float) -> None:
        chunk = self.transport.receive(timeout_s)
        if chunk is None:
            return
        if not isinstance(chunk, (bytes, bytearray, memoryview)):
            raise ProtocolV2SessionError("transport returned non-byte RX data")
        raw = bytes(chunk)
        if not raw:
            return
        received_utc = self.utc_now()
        received_ns = time.monotonic_ns()
        rx_id = self._append("RX_BYTES", raw_b64=base64.b64encode(raw).decode("ascii"),
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
                raise ProtocolV2SessionError(f"RX frame rejected: {exc}") from exc
            raw_frame = bytes(self._rx_buffer[:decoded.consumed_bytes])
            del self._rx_buffer[:decoded.consumed_bytes]
            decoded.message["_raw_frame_base64"] = base64.b64encode(raw_frame).decode("ascii")
            decoded.message["_rx_chunk_event_id"] = rx_id
            decoded.message["_host_received_at_utc"] = received_utc
            decoded.message["_host_received_monotonic_ns"] = received_ns
            decoded.message["_rx_frame_evidence_event_id"] = self._append(
                "FRAME_RX_DECODED", direction="device_to_host",
                host_received_at_utc=received_utc,
                host_received_monotonic_ns=received_ns,
                raw_frame_base64=decoded.message["_raw_frame_base64"],
                rx_chunk_event_id=rx_id, message_type=decoded.message.get("message_type"),
                command_id=decoded.message.get("command_id"),
                measurement_session_id=decoded.message.get("measurement_session_id"),
            )
            self._messages.append(decoded.message)

    def _next_message(self, timeout_s: float) -> Optional[dict]:
        if self._messages:
            return self._messages.pop(0)
        if timeout_s <= 0:
            self._pump_rx(0.0)
            return self._messages.pop(0) if self._messages else None
        deadline = self.monotonic() + timeout_s
        while self.monotonic() < deadline:
            self._pump_rx(max(0.0, deadline - self.monotonic()))
            if self._messages:
                return self._messages.pop(0)
        return None

    def _wait_for(self, expected_kind: str) -> dict:
        deadline = self.monotonic() + self.ack_timeout_s
        while self.monotonic() < deadline:
            message = self._next_message(max(0.0, deadline - self.monotonic()))
            if message is None:
                continue
            if message.get("kind") == expected_kind:
                return message
            if message.get("kind") in {"ADC_BATCH", "STATUS"}:
                self._telemetry_queue.append(message)
                continue
            self._append("RX_UNEXPECTED_MESSAGE", message=message, expected_kind=expected_kind)
        raise ProtocolV2SessionError(f"{expected_kind} timeout; outcome unresolved")

    def start_session(self, measurement_session_id: str, *,
                      host_boot_id64: Optional[int] = None,
                      host_next_sequence64: Optional[int] = None) -> str:
        if self._failed:
            raise ProtocolV2SessionError("host protocol session is fail-closed")
        try:
            parsed = uuid.UUID(str(measurement_session_id))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError("measurement_session_id must be a UUID") from exc
        if parsed.int == 0 or parsed.version != 4 or parsed.variant != uuid.RFC_4122:
            raise ValueError("measurement_session_id must be a nonzero RFC4122 UUIDv4")
        canonical_id = str(parsed)
        if self._storage_session_id is not None and canonical_id != self._storage_session_id:
            raise ProtocolV2SessionError("measurement session UUID does not match its durable sidecar paths")
        if self.measurement_session_id is not None:
            if self.measurement_session_id != canonical_id:
                raise ProtocolV2SessionError("adapter cannot switch measurement session in place")
            return canonical_id
        self.measurement_session_id = canonical_id
        nonce = secrets.randbits(64) or 1
        stop_connect = getattr(self.stop_writer, "connect", None)
        try:
            if callable(stop_connect):
                stop_connect()
            self.transport.connect()
        except Exception as exc:
            self._failed = True
            stop_disconnect = getattr(self.stop_writer, "disconnect", None)
            if callable(stop_disconnect):
                try:
                    stop_disconnect()
                except Exception:
                    pass
            raise ProtocolV2SessionError(f"serial session startup failed closed: {exc}") from exc
        frame = self.codec.encode_hello(session_id=canonical_id, host_nonce64=nonce)
        self._send_frame(frame, kind="HELLO", command_id=0)
        ack = self._wait_for("HELLO_ACK")
        if (ack.get("result") != 0
                or ack.get("echoed_host_nonce64") != nonce
                or ack.get("measurement_session_id") != canonical_id):
            self._failed = True
            raise ProtocolV2SessionError("HELLO_ACK result/nonce/full UUID mismatch")
        boot_id = ack.get("boot_id64")
        next_sequence = ack.get("next_sample_sequence64")
        if (isinstance(boot_id, bool) or not isinstance(boot_id, int) or boot_id == 0
                or isinstance(next_sequence, bool) or not isinstance(next_sequence, int)
                or not 0 <= next_sequence <= 0xFFFFFFFFFFFFFFFF):
            self._failed = True
            raise ProtocolV2SessionError("HELLO_ACK has invalid boot identity or next sequence")
        self.boot_id64 = boot_id
        self.epoch_tag = epoch_tag_for_boot_id(boot_id)
        if ack.get("device_epoch_tag") != self.epoch_tag:
            self._failed = True
            raise ProtocolV2SessionError("HELLO_ACK epoch correlation mismatch")
        resolution = reconcile_device_sequence(
            device_boot_id64=boot_id,
            device_next_sequence64=next_sequence,
            host_boot_id64=host_boot_id64,
            host_next_sequence64=host_next_sequence64,
            device_identity_verified=True,
        )
        if resolution.status in {
            SequenceReconciliationStatus.UNRESOLVED_DEVICE_ROLLBACK,
            SequenceReconciliationStatus.UNRESOLVED_IDENTITY,
            SequenceReconciliationStatus.UNRESOLVED_INVALID,
        }:
            self._failed = True
            raise ProtocolV2SessionError(f"device sequence reconciliation failed: {resolution.detail}")
        self.sequence_reconciliation = resolution
        self.next_sample_sequence64 = next_sequence
        self._append("HELLO_ACK_MATCHED", boot_id64=boot_id, device_epoch_tag=self.epoch_tag,
                     host_nonce64=nonce, next_sample_sequence64=next_sequence,
                     sequence_reconciliation=asdict(resolution), ack=ack)
        if resolution.status is SequenceReconciliationStatus.GAP_UNATTRIBUTABLE:
            self._append("DEVICE_SEQUENCE_GAP_UNATTRIBUTABLE",
                         boot_id64=boot_id, start_sequence64=resolution.gap_start_sequence64,
                         end_sequence64_exclusive=resolution.gap_end_sequence64_exclusive,
                         resume_from_sequence64=next_sequence, reason=resolution.detail)
        elif resolution.status is SequenceReconciliationStatus.NEW_DEVICE_EPOCH:
            self._append("DEVICE_EPOCH_CHANGED", boot_id64=boot_id,
                         next_sample_sequence64=next_sequence,
                         prior_epoch_gap_start=resolution.gap_start_sequence64,
                         prior_epoch_gap_end_exclusive=resolution.gap_end_sequence64_exclusive)
        return canonical_id

    def _register_and_send(self, identity: CommandIdentity, frame: bytes, kind: str) -> str:
        digest = self.intent_journal.append_intent(identity, self.utc_now())
        self._correlator.register(identity)
        return self._send_frame(frame, kind=kind, command_id=int(identity.command_id),
                                identity=identity, intent_hash=digest)

    def _accept_ack(self, message: dict, identity: CommandIdentity,
                    expected_kind: str, token: int, pwm: Optional[int] = None,
                    direction: Optional[int] = None) -> bool:
        if (message.get("kind") != expected_kind
                or message.get("measurement_session_id") != self.measurement_session_id
                or message.get("device_epoch_tag") != self.epoch_tag
                or message.get("command_id") != int(identity.command_id)):
            return False
        if expected_kind == "ARM_ACK":
            if (message.get("result") != 0 or message.get("state") != "ARMED"
                    or message.get("active_context_token") != token
                    or (direction is not None and message.get("direction_code") != int(direction))):
                raise ProtocolV2SessionError("ARM_ACK rejected or context/direction mismatch")
        elif expected_kind == "DISARM_ACK":
            if (message.get("result") != 0 or message.get("state") != "IDLE"
                    or message.get("stage_context_token") != token):
                raise ProtocolV2SessionError("DISARM_ACK rejected or context mismatch")
        elif (message.get("result") != 0 or message.get("applied_pwm") != pwm
              or message.get("stage_context_token") != token):
            raise ProtocolV2SessionError("APPLY_ACK rejected or PWM/context mismatch")
        ack_identity = AckIdentity(
            command_id=identity.command_id, command_type=identity.command_type,
            session_id=identity.session_id, boot_id64=identity.boot_id64,
            stage_context_id=identity.stage_context_id,
        )
        if not self._correlator.correlate(ack_identity):
            raise ProtocolV2SessionError("ACK full identity correlation failed")
        self._append("ACK_MATCHED", expected_kind=expected_kind,
                     command_id=int(identity.command_id), identity=asdict(identity), message=message)
        return True

    def send_stage_pwm(self, pwm: int, stage_context_id: str, measurement_session_id: str,
                       stage_index: Optional[int] = None, *,
                       host_boot_id64: Optional[int] = None,
                       host_next_sequence64: Optional[int] = None,
                       direction: int = DriveDirection.FWD) -> str:
        try:
            if self._failed:
                raise ProtocolV2SessionError("host protocol session is fail-closed")
            if self._pending is not None:
                raise ProtocolV2SessionError("previous PWM outcome unresolved")
            if self._armed:
                raise ProtocolV2SessionError("previous stage must complete DISARM before the next ARM")
            if isinstance(direction, bool) or not isinstance(direction, int) or direction not in {0, 1}:
                raise ValueError("direction must be DriveDirection.FWD(0) or REV(1)")
            if isinstance(pwm, bool) or not isinstance(pwm, int) or not 0 <= pwm <= 30:
                raise ValueError("PWM must be integer 0..30")
            if not isinstance(stage_context_id, str) or not stage_context_id:
                raise ValueError("stage_context_id is required")
            if stage_index is None:
                stage_index = pwm
            if isinstance(stage_index, bool) or not isinstance(stage_index, int) or not 0 <= stage_index <= 30:
                raise ValueError("stage_index must be integer 0..30")
            self.start_session(measurement_session_id, host_boot_id64=host_boot_id64,
                               host_next_sequence64=host_next_sequence64)
            token = stage_index + 1
            if token in self._context_map:
                raise ProtocolV2SessionError("stage context token reuse prohibited")
            arm_id = None if self._armed else self._next_command_id()
            command_id = self._next_command_id()
            self._context_map[token] = stage_context_id
            self._append("STAGE_CONTEXT_MAP", stage_context_token=token,
                         stage_context_id=stage_context_id, stage_id=f"PWM-{stage_index:02d}",
                         intended_pwm=pwm, command_id=command_id)
            if arm_id is not None:
                arm_identity = CommandIdentity(str(arm_id), "ARM", self.measurement_session_id,
                                               int(self.boot_id64), stage_context_id)
                arm_frame = self.codec.encode_arm(session_id=self.measurement_session_id,
                                                  epoch_tag=int(self.epoch_tag), command_id=arm_id,
                                                  stage_context_token=token, direction=direction)
                self._register_and_send(arm_identity, arm_frame, "ARM")
                arm_ack = self._wait_for("ARM_ACK")
                if not self._accept_ack(arm_ack, arm_identity, "ARM_ACK", token, direction=direction):
                    raise ProtocolV2SessionError("ARM_ACK identity mismatch")
                self._armed = True
                self._loss_accumulator = DeviceLossWindowAccumulator(
                    int(self.boot_id64), token
                )
            identity = CommandIdentity(str(command_id), "PWM_SET", self.measurement_session_id,
                                       int(self.boot_id64), stage_context_id)
            frame = self.codec.encode_pwm_set(session_id=self.measurement_session_id,
                                              epoch_tag=int(self.epoch_tag), command_id=command_id,
                                              pwm=pwm, stage_context_token=token)
            sent = self._register_and_send(identity, frame, "PWM_SET")
            self._pending = {"identity": identity, "token": token, "pwm": pwm}
            self._active_stage = {"token": token, "stage_context_id": stage_context_id,
                                  "direction": direction, "stage_index": stage_index}
            return sent
        except Exception:
            self._failed = True
            raise

    def poll_apply_ack(self, timeout_s: float = 0.0):
        if self._failed:
            raise ProtocolV2SessionError("host protocol session is fail-closed")
        if self._pending is None:
            return None
        message = self._next_message(timeout_s)
        if message is None:
            return None
        if message.get("kind") in {"ADC_BATCH", "STATUS"}:
            self._telemetry_queue.append(message)
            return None
        if message.get("kind") != "APPLY_ACK":
            self._append("RX_UNEXPECTED_MESSAGE", message=message, expected_kind="APPLY_ACK")
            return None
        pending = self._pending
        if not self._accept_ack(message, pending["identity"], "APPLY_ACK",
                                pending["token"], pending["pwm"]):
            self._append("ACK_IDENTITY_MISMATCH", expected=asdict(pending["identity"]), message=message)
            return None
        self._pending = None
        return pending["pwm"], self.utc_now()


    def disarm_stage(self) -> str:
        """End the active stage safely while retaining the HELLO session."""
        try:
            if self._failed:
                raise ProtocolV2SessionError("host protocol session is fail-closed")
            if self._pending is not None:
                raise ProtocolV2SessionError("cannot DISARM while PWM outcome is unresolved")
            if not self._armed or self._active_stage is None:
                raise ProtocolV2SessionError("no armed stage is available to DISARM")
            token = int(self._active_stage["token"])
            stage_context_id = str(self._active_stage["stage_context_id"])
            command_id = self._next_command_id()
            identity = CommandIdentity(str(command_id), "DISARM", self.measurement_session_id,
                                       int(self.boot_id64), stage_context_id)
            frame = self.codec.encode_disarm(
                session_id=self.measurement_session_id, epoch_tag=int(self.epoch_tag),
                command_id=command_id, stage_context_token=token)
            sent = self._register_and_send(identity, frame, "DISARM")
            ack = self._wait_for("DISARM_ACK")
            if not self._accept_ack(ack, identity, "DISARM_ACK", token):
                raise ProtocolV2SessionError("DISARM_ACK identity mismatch")
            self._drain_telemetry_queue()
            self._armed = False
            self._active_stage = None
            self._append("STAGE_DISARMED", direction="host_internal",
                         stage_context_token=token, stage_context_id=stage_context_id,
                         command_id=command_id)
            self._finalize_adc_loss_window()
            return sent
        except Exception:
            self._failed = True
            raise

    def poll_adc_batch(self, timeout_s: float = 0.0) -> Optional[list[dict]]:
        """Drain one queued or newly received telemetry message without blocking."""
        if self._failed:
            raise ProtocolV2SessionError("host protocol session is fail-closed")
        message = self._telemetry_queue.pop(0) if self._telemetry_queue else self._next_message(timeout_s)
        if message is None:
            return None
        kind = message.get("kind")
        if kind == "ADC_BATCH":
            return self.accept_adc_batch(message)
        if kind == "STATUS":
            self._append("DEVICE_STATUS_RECEIVED", message=message)
            return None
        if kind == "ERROR":
            self._failed = True
            self._append("DEVICE_ERROR_RECEIVED", message=message)
            raise ProtocolV2SessionError("device reported protocol-v2 ERROR")
        self._append("RX_UNEXPECTED_MESSAGE", message=message, expected_kind="ADC_BATCH or STATUS")
        return None

    def _drain_telemetry_queue(self) -> None:
        while self._telemetry_queue:
            message = self._telemetry_queue.pop(0)
            if message.get("kind") == "ADC_BATCH":
                self.accept_adc_batch(message)
            elif message.get("kind") == "STATUS":
                self._append("DEVICE_STATUS_RECEIVED", message=message)

    def accept_adc_batch(self, message: dict) -> list[dict]:
        if self._failed or self.boot_id64 is None or self.next_sample_sequence64 is None:
            raise ProtocolV2SessionError("session identity/sequence is not established")
        if (message.get("kind") != "ADC_BATCH"
                or message.get("measurement_session_id") != self.measurement_session_id
                or message.get("device_epoch_tag") != self.epoch_tag):
            raise ProtocolV2SessionError("ADC_BATCH session/epoch mismatch")
        samples = message.get("samples")
        if not isinstance(samples, list) or len(samples) != 12:
            raise ProtocolV2SessionError("ADC_BATCH must contain exactly 12 sample slots")
        first = samples[0].get("sample_sequence64")
        if (isinstance(first, bool) or not isinstance(first, int)
                or not 0 <= first <= 0xFFFFFFFFFFFFFFFF - len(samples)):
            self._failed = True
            raise ProtocolV2SessionError("ADC_BATCH first sequence is invalid or would exhaust uint64")
        if first < self.next_sample_sequence64:
            self._failed = True
            raise ProtocolV2SessionError("stale or duplicate ADC_BATCH sequence")
        if first > self.next_sample_sequence64:
            self._append("DEVICE_SEQUENCE_GAP_UNATTRIBUTABLE", boot_id64=self.boot_id64,
                         start_sequence64=self.next_sample_sequence64,
                         end_sequence64_exclusive=first,
                         reason="ADC_BATCH starts after the next expected device sequence")
        for i, sample in enumerate(samples):
            if sample.get("sample_sequence64") != first + i:
                self._failed = True
                raise ProtocolV2SessionError("ADC_BATCH sample sequence is not contiguous")
        if self._active_stage is None or self._loss_accumulator is None:
            self._failed = True
            raise ProtocolV2SessionError("ADC_BATCH received outside an active ARM epoch")
        active_token = int(self._active_stage["token"])
        for sample in samples:
            status = sample.get("acquisition_status")
            token = sample.get("stage_context_token")
            if status == 3:
                if token != 0:
                    self._failed = True
                    raise ProtocolV2SessionError("NOT_ACQUIRED slot must have unresolved context token zero")
            elif token != active_token:
                self._failed = True
                raise ProtocolV2SessionError("ADC sample stage context does not match active ARM epoch")
        gap_slots = first - self.next_sample_sequence64
        try:
            completed_windows = self._loss_accumulator.add_batch(samples, gap_slots=gap_slots)
        except DeviceLossAccountingError as exc:
            self._failed = True
            raise ProtocolV2SessionError(f"ADC loss accounting rejected batch: {exc}") from exc
        self._append("ADC_BATCH_ACCEPTED", first_sample_sequence64=first,
                     next_sample_sequence64=first + len(samples),
                     sample_count=len(samples),
                     device_elapsed_us=samples[-1].get("device_elapsed_us"),
                     raw_frame_base64=message.get("_raw_frame_base64"))
        for window in completed_windows:
            self._append("ADC_LOSS_WINDOW_SUMMARY", summary=asdict(window), terminal=False)
        self.next_sample_sequence64 = first + len(samples)
        return samples

    def finalize_evidence_bundle(self, rawlog_package_dir):
        if not self.measurement_session_id:
            raise ProtocolV2SessionError("cannot bind Evidence bundle before HELLO session identity")
        from .evidence_bundle import write_evidence_bundle_manifest
        return write_evidence_bundle_manifest(
            rawlog_package_dir, self.evidence, self.measurement_session_id
        )

    def _finalize_adc_loss_window(self) -> None:
        accumulator = self._loss_accumulator
        self._loss_accumulator = None
        if accumulator is None:
            return
        summary = accumulator.finalize()
        if summary is not None:
            self._append("ADC_LOSS_WINDOW_SUMMARY", summary=asdict(summary), terminal=True)

    @property
    def last_stop_request_id(self) -> Optional[int]:
        return self._last_stop_request_id

    def send_stop_best_effort(self, *, stop_reason: int, stop_request_id: Optional[int] = None) -> int:
        if self.stop_writer is None:
            raise ProtocolV2SessionError("independent STOP writer is not configured")
        valid = {int(reason) for reason in StopReason}
        if isinstance(stop_reason, bool) or not isinstance(stop_reason, int) or stop_reason not in valid:
            raise ValueError("stop_reason must use an assigned StopReason code")
        if stop_request_id is None:
            self._stop_request_id = min(0xFFFF, self._stop_request_id + 1)
            stop_request_id = self._stop_request_id or 0xFFFF
        if isinstance(stop_request_id, bool) or not isinstance(stop_request_id, int) or not 1 <= stop_request_id <= 0xFFFF:
            raise ValueError("stop_request_id must be nonzero uint16")
        self._last_stop_request_id = stop_request_id
        cached = self._stop_frames.get(stop_request_id)
        if cached:
            if cached["stop_reason"] != stop_reason:
                raise ProtocolV2SessionError("STOP ID reused with a different reason")
            frame, command_id = cached["frame"], cached["command_id"]
        else:
            if stop_request_id in self._used_stop_request_ids:
                raise ProtocolV2SessionError("STOP ID reuse is not an exact retry")
            try:
                command_id = self._next_command_id()
            except ProtocolV2SessionError:
                command_id = 0xFFFFFFFF
            session = self.measurement_session_id or str(uuid.UUID(int=0))
            epoch = int(self.epoch_tag or 0)
            frame = self.codec.encode_stop_request(
                session_id=session, epoch_tag=epoch, command_id=command_id,
                stop_reason=stop_reason, stop_request_id=stop_request_id)
            self._used_stop_request_ids.add(stop_request_id)
            self._stop_frames[stop_request_id] = {
                "frame": frame, "command_id": command_id, "stop_reason": stop_reason,
            }
        try:
            finished = threading.Event()
            writer_errors = []
            def writer_worker():
                try:
                    self.stop_writer(frame)
                except Exception as exc:
                    writer_errors.append(exc)
                finally:
                    finished.set()
            worker = threading.Thread(target=writer_worker, name="310-stop-writer", daemon=True)
            worker.start()
            if not finished.wait(self.stop_timeout_s):
                raise TimeoutError(f"STOP writer deadline expired after {self.stop_timeout_s:.3f}s")
            if writer_errors:
                raise writer_errors[0]
        except Exception as exc:
            try:
                self._append("STOP_TX_ERROR", frame_b64=base64.b64encode(frame).decode("ascii"),
                             command_id=command_id, stop_request_id=stop_request_id,
                             stop_reason=stop_reason, outcome="HOST_WRITE_FAILED_UNKNOWN", error=str(exc))
            except Exception:
                pass
            try:
                self._finalize_adc_loss_window()
            except Exception:
                self._failed = True
            raise ProtocolV2SessionError(f"STOP_REQ write outcome unknown: {exc}") from exc
        try:
            self._append("STOP_TX_ATTEMPT", frame_b64=base64.b64encode(frame).decode("ascii"),
                         byte_count=len(frame), command_id=command_id,
                         stop_request_id=stop_request_id, stop_reason=stop_reason,
                         outcome="HOST_WRITE_COMPLETED")
        except Exception:
            pass
        self._finalize_adc_loss_window()
        return stop_request_id

    def latch_abort(self, reason: str) -> None:
        self._failed = True
        if self._pending is not None:
            identity = self._pending.get("identity")
            if identity is not None:
                self._correlator.expire(identity.command_id)
            self._pending = None

    def disconnect(self) -> None:
        try:
            self.transport.disconnect()
        finally:
            stop_disconnect = getattr(self.stop_writer, "disconnect", None)
            if callable(stop_disconnect):
                stop_disconnect()
