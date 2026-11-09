"""310-stage sequence orchestration and RawLog v2 adapter."""
from __future__ import annotations

import os
import threading
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional, Protocol

from raw_log_v2 import RawLogV2Writer


class Clock(Protocol):
    def monotonic_ns(self) -> int: ...
    def utc_now(self) -> str: ...


class SystemClock:
    def monotonic_ns(self) -> int:
        import time
        return time.monotonic_ns()

    def utc_now(self) -> str:
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class SequenceState(str, Enum):
    READY = "ready"
    WAITING_ACK = "waiting_ack"
    RUNNING = "running"
    STOPPING = "stopping"
    FINALIZING = "finalizing"
    ABORTED = "aborted"
    COMPLETED = "completed"
    FAULT = "fault"


class SequenceError(RuntimeError):
    pass


class SequenceController:
    """Clock-injected, fail-closed coordinator.

    send_pwm(pwm) must send a protocol command and return its host UTC send time.
    poll_ack() returns (acknowledged_pwm, host_utc) or None. ACK is only a
    protocol acknowledgement, never proof of physical motor state.
    """

    STAGE_COUNT = 31
    STAGE_DURATION_MS = 10_000

    def __init__(
        self,
        writer: RawLogV2Writer,
        manifest_fields: dict[str, Any],
        send_pwm: Optional[Callable[[int], str]],
        send_stop: Callable[[], None],
        poll_ack: Optional[Callable[[], Optional[tuple[int, str]]]],
        clock: Optional[Clock] = None,
        ack_timeout_ms: int = 2_000,
        protocol_session: Optional[object] = None,
        send_normal_stop: Optional[Callable[[], None]] = None,
        stage_direction: Optional[Callable[[int], int]] = None,
    ) -> None:
        if protocol_session is None and (not callable(send_pwm) or not callable(poll_ack)):
            raise ValueError("legacy send_pwm and poll_ack callbacks are required without protocol_session")
        if protocol_session is not None and (
            not callable(getattr(protocol_session, "send_stage_pwm", None))
            or not callable(getattr(protocol_session, "poll_apply_ack", None))
        ):
            raise ValueError("protocol_session must implement send_stage_pwm and poll_apply_ack")
        self.writer = writer
        self.manifest_fields = dict(manifest_fields)
        self.send_pwm = send_pwm
        self.send_stop = send_stop
        self.send_normal_stop = send_normal_stop or send_stop
        self.poll_ack = poll_ack
        self.protocol_session = protocol_session
        self.stage_direction = stage_direction or (lambda _index: 0)
        self.current_stage_direction = 0
        self.clock = clock or SystemClock()
        self.ack_timeout_ns = ack_timeout_ms * 1_000_000
        self.state = SequenceState.READY
        self.session = None
        self.stage_index = -1
        self.stage_context_id: Optional[str] = None
        self._stage_recorded = False
        self.command_sent_utc: Optional[str] = None
        self.command_sent_ns: Optional[int] = None
        self.ack_utc: Optional[str] = None
        self.stage_start_ns: Optional[int] = None
        self.stage_start_utc: Optional[str] = None
        self.next_deadline_ns: Optional[int] = None
        self._last_fault: Optional[str] = None
        self._recovery_complete = False
        # Recovering a prior incomplete session repairs storage only; it does not
        # establish whether a nonzero command reached the device or was stopped.
        self._recovery_requires_review = False
        self._finalization_started = False
        self._stop_attempted = False
        # Once any append fails, this session is write-disabled. STOP is still attempted.
        self._log_write_failed = False
        # Non-blocking lock makes abort entry atomic and safe for callback re-entry.
        self._abort_lock = threading.Lock()

    @classmethod
    def with_protocol_session(
        cls,
        writer: RawLogV2Writer,
        manifest_fields: dict[str, Any],
        protocol_session: object,
        send_stop: Callable[[], None],
        clock: Optional[Clock] = None,
        ack_timeout_ms: int = 2_000,
        send_normal_stop: Optional[Callable[[], None]] = None,
        stage_direction: Optional[Callable[[int], int]] = None,
    ) -> "SequenceController":
        """Construct the v0.5 path without dummy legacy PWM/ACK callbacks."""
        return cls(
            writer, manifest_fields, None, send_stop, None, clock,
            ack_timeout_ms=ack_timeout_ms, protocol_session=protocol_session,
            send_normal_stop=send_normal_stop, stage_direction=stage_direction,
        )

    def startup_recover(self) -> list[dict[str, Any]]:
        if self.state != SequenceState.READY:
            raise SequenceError("startup recovery must precede session start")
        # Explicitly discover, then recover. No measurement is permitted on failure.
        pending_before = self.writer.list_incomplete_work()
        # Persist the re-arm inhibition BEFORE recovery removes the .work area.
        # Otherwise a second process could see no pending work and silently
        # re-arm after the first process recovered it.
        inhibit_path = self.writer.root / ".310-rearm-inhibited"
        if inhibit_path.is_symlink():
            raise SequenceError("re-arm inhibition marker must not be a symlink")
        if pending_before and not inhibit_path.exists():
            self.writer.root.mkdir(parents=True, exist_ok=True)
            try:
                fd = os.open(str(inhibit_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except FileExistsError:
                fd = None
            if fd is not None:
                try:
                    payload = (
                        "Recovered incomplete 310 work requires explicit command-outcome "
                        "reconciliation before re-arm. This marker is intentionally "
                        "persistent and is not cleared automatically.\n"
                    ).encode("utf-8")
                    written = os.write(fd, payload)
                    if written != len(payload):
                        raise OSError("short re-arm inhibition marker write")
                    os.fsync(fd)
                finally:
                    os.close(fd)
                dir_fd = os.open(str(self.writer.root), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
        if inhibit_path.exists():
            if inhibit_path.is_symlink() or not inhibit_path.is_file():
                raise SequenceError("re-arm inhibition marker is not a regular file")
            self._recovery_requires_review = True
        evidence_marker = self.writer.root / ".310-evidence-reconciliation-required"
        if evidence_marker.is_symlink():
            raise SequenceError("Evidence reconciliation marker must not be a symlink")
        if evidence_marker.exists():
            if not evidence_marker.is_file():
                raise SequenceError("Evidence reconciliation marker is not a regular file")
            self._recovery_requires_review = True
        result = self.writer.recover_pending()
        pending_after = self.writer.list_incomplete_work()
        if pending_after:
            raise SequenceError(f"startup recovery left pending work: {pending_after}")
        recovered_ids = {
            item.get("log_id") for item in result
            if isinstance(item, dict) and isinstance(item.get("log_id"), str)
        }
        if recovered_ids != set(pending_before):
            raise SequenceError("startup recovery result does not match discovered pending work")
        self._recovery_requires_review = self._recovery_requires_review or bool(recovered_ids)
        self._recovery_complete = True
        return result

    def start(self) -> None:
        if not self._recovery_complete:
            raise SequenceError("startup recovery has not completed")
        if self.state != SequenceState.READY:
            raise SequenceError("controller is not ready")
        if self._recovery_requires_review:
            raise SequenceError(
                "recovered incomplete work requires command-outcome reconciliation; "
                "automatic re-arm is prohibited"
            )
        fields = dict(self.manifest_fields)
        now = self.clock.utc_now()
        fields.setdefault("schema_name", "mini4wd.rawlog")
        fields.setdefault("schema_version", "2.0.0")
        fields.setdefault("measurement_type", "PWM_START_SWEEP_310S")
        fields.setdefault("created_at_utc", now)
        fields.setdefault("started_at_utc", now)
        fields.setdefault("ended_at_utc", None)
        fields.setdefault("status", "incomplete")
        fields.setdefault("planned_stage_count", 31)
        fields.setdefault("planned_stage_duration_ms", 10000)
        fields.setdefault("planned_total_duration_ms", 310000)
        fields.setdefault("motor_instance_id", None)
        fields.setdefault("device", {"type": None, "model": None, "firmware_version": None,
                                     "firmware_build": None, "firmware_id": None,
                                     "adc_resolution_bits": None})
        fields.setdefault("measurement_conditions", {
            "direction": "UNKNOWN", "voltage_control_mode": "UNKNOWN",
            "sweep_pwm_min": 0, "sweep_pwm_max": 30,
            "stage_duration_ms": 10000, "schedule_owner": "PYTHON"})
        fields.setdefault("record_counts", {})
        self.session = self.writer.begin(fields)
        try:
            self._append("SESSION_EVENT", event="SESSION_STARTED",
                         host_monotonic_ns=self.clock.monotonic_ns(), details={"stage_count": 31})
            self._begin_stage(0)
        except Exception as exc:
            self.abort("storage_or_command_failure", fault=str(exc))
            raise SequenceError("sequence startup failed closed") from exc

    def _append(self, record_type: str, **payload: Any) -> None:
        if self._log_write_failed:
            raise SequenceError("RawLog writes are disabled after an append failure")
        if self.session is None:
            raise SequenceError("RawLog session is not open")
        record = {
            "schema_version": "2.0.0", "record_type": record_type,
            "record_id": str(uuid.uuid4()), "record_seq": int(self.session.state["last_record_seq"]) + 1,
            "log_id": self.session.state["log_id"],
            "measurement_session_id": self.session.state["measurement_session_id"],
            "recorded_at_utc": self.clock.utc_now(),
            **payload,
        }
        try:
            self.session.append(record)
        except Exception:
            # Do not write a FAULT marker into a work area whose append path failed.
            # Preserve the original .work bytes for RawLog v2 startup recovery.
            self._log_write_failed = True
            raise

    def _assert_rearm_not_inhibited(self) -> None:
        """Apply the persistent recovery gate before every sequence PWM entry path."""
        root = self.writer.root
        if root.is_symlink() or not root.is_dir():
            raise SequenceError("RawLog root is missing, symlinked, or not a directory")
        for name in (".310-rearm-inhibited", ".310-evidence-reconciliation-required"):
            marker = root / name
            if marker.is_symlink():
                raise SequenceError(f"{name} must not be a symlink")
            if marker.exists():
                if not marker.is_file():
                    raise SequenceError(f"{name} is not a regular file")
                raise SequenceError(
                    f"automatic re-arm is inhibited by {name}; explicit command-outcome "
                    "reconciliation and independent safe-state confirmation are required"
                )

    def _begin_stage(self, index: int) -> None:
        if self.state in {SequenceState.FAULT, SequenceState.ABORTED, SequenceState.STOPPING}:
            return
        self.stage_index = index
        self.stage_context_id = str(uuid.uuid4())
        self._stage_recorded = False
        self.command_sent_utc = None
        self.command_sent_ns = None
        self.ack_utc = None
        self.stage_start_ns = None
        self.stage_start_utc = None
        self.next_deadline_ns = None
        try:
            self._assert_rearm_not_inhibited()
            # send_pwm returns UTC after transport write/flush completes.
            # Capture monotonic time immediately afterwards so ACK timeout and
            # send-to-ACK delay exclude time spent inside the blocking send.
            if self.protocol_session is None:
                self.command_sent_utc = self.send_pwm(index)
            else:
                direction = self.stage_direction(index)
                if isinstance(direction, bool) or not isinstance(direction, int) or direction not in {0, 1}:
                    raise SequenceError("stage_direction must return FWD(0) or REV(1)")
                self.current_stage_direction = direction
                send_stage = self.protocol_session.send_stage_pwm
                if getattr(self.protocol_session, "supports_stage_direction", False):
                    self.command_sent_utc = send_stage(
                        index, self.stage_context_id,
                        self.session.state["measurement_session_id"], stage_index=index,
                        direction=direction,
                    )
                else:
                    if direction != 0:
                        raise SequenceError("protocol session does not support per-stage REV direction")
                    self.command_sent_utc = send_stage(
                        index, self.stage_context_id,
                        self.session.state["measurement_session_id"], stage_index=index,
                    )
            transport_sent_ns = (
                getattr(self.protocol_session, "last_write_completed_monotonic_ns", None)
                if self.protocol_session is not None else None
            )
            self.command_sent_ns = (
                transport_sent_ns if isinstance(transport_sent_ns, int)
                and not isinstance(transport_sent_ns, bool)
                else self.clock.monotonic_ns()
            )
        except Exception as exc:
            self.abort("communication_lost", fault=f"PWM send failed: {exc}")
            return
        self.state = SequenceState.WAITING_ACK

    def poll(self) -> SequenceState:
        """Advance using injected clock; caller controls polling cadence."""
        if self.state == SequenceState.WAITING_ACK:
            try:
                ack = (self.poll_ack() if self.protocol_session is None
                       else self.protocol_session.poll_apply_ack(timeout_s=0.0))
            except Exception as exc:
                self.abort("communication_lost", fault=str(exc))
                return self.state
            if ack is not None:
                if not isinstance(ack, tuple) or len(ack) not in {2, 3}:
                    self.abort("communication_lost", fault="malformed ACK object")
                    return self.state
                pwm, ack_utc = ack[:2]
                ack_received_ns = ack[2] if len(ack) == 3 else self.clock.monotonic_ns()
                if (not isinstance(pwm, int) or isinstance(pwm, bool) or not isinstance(ack_utc, str)
                        or isinstance(ack_received_ns, bool) or not isinstance(ack_received_ns, int)
                        or ack_received_ns < 0):
                    self.abort("communication_lost", fault="malformed ACK fields")
                    return self.state
                if self.command_sent_ns is not None and ack_received_ns < self.command_sent_ns:
                    self.abort("communication_lost", fault="ACK receive timestamp precedes command write completion")
                    return self.state
                if pwm != self.stage_index:
                    self.abort("communication_lost", fault="ACK PWM mismatch")
                    return self.state
                self.ack_utc = ack_utc
                self.stage_start_utc = ack_utc
                self.stage_start_ns = ack_received_ns
                self.next_deadline_ns = self.stage_start_ns + self.STAGE_DURATION_MS * 1_000_000
                self.state = SequenceState.RUNNING
                try:
                    self._append("SESSION_EVENT", event="OTHER",
                                 host_monotonic_ns=self.stage_start_ns,
                                 details={"kind": "PWM_ACK_RECEIVED",
                                          "stage_index": self.stage_index,
                                          "stage_id": f"PWM-{self.stage_index:02d}",
                                          "stage_context_id": self.stage_context_id,
                                          "command_sent_at_utc": self.command_sent_utc,
                                          "ack_received_at_utc": ack_utc,
                                          "command_sent_host_monotonic_ns": self.command_sent_ns,
                                          "ack_received_host_monotonic_ns": self.stage_start_ns,
                                          "command_to_ack_delay_ms":
                                              (self.stage_start_ns - int(self.command_sent_ns)) / 1_000_000})
                    if self.clock.monotonic_ns() >= self.next_deadline_ns:
                        self.abort("storage_failure",
                                   fault="durable ACK evidence/RawLog commit exceeded stage deadline")
                except Exception as exc:
                    self.abort("storage_failure", fault=f"RawLog ACK record failed: {exc}")
            elif self.clock.monotonic_ns() - int(self.command_sent_ns) >= self.ack_timeout_ns:
                self.abort("communication_lost", fault="PWM ACK timeout")
        elif self.state == SequenceState.RUNNING:
            if self.protocol_session is not None:
                poll_telemetry = getattr(self.protocol_session, "poll_adc_batch", None)
                if callable(poll_telemetry):
                    try:
                        samples = poll_telemetry(timeout_s=0.0)
                        if samples:
                            channel_names = {
                                0: "A0", 1: "A1", 2: "A2", 3: "A3", 4: "A4", 5: "A5"
                            }
                            boot_id = int(self.protocol_session.boot_id64)
                            batch_records = []
                            for sample in samples:
                                status = int(sample["acquisition_status"])
                                channel = channel_names[int(sample["channel_code"])]
                                valid = status == 0
                                reason = {
                                    1: "PRECONDITION_INVALID",
                                    2: "CONVERSION_TIMEOUT",
                                    3: "NOT_ACQUIRED",
                                }.get(status)
                                batch_records.append({
                                    "channel": channel,
                                    "adc_raw": int(sample["adc_raw"]) if valid else None,
                                    "adc_resolution_bits": 10,
                                    "device_timestamp_us_u32": int(sample["timestamp_us_u32"]),
                                    "device_timestamp_point": (
                                        "scheduled_slot_start" if status == 3
                                        else "conversion_midpoint" if valid
                                        else "attempt_timestamp"
                                    ),
                                    "device_epoch_id": f"{boot_id:016X}",
                                    "device_elapsed_us": int(sample["device_elapsed_us"]),
                                    "device_sample_sequence": int(sample["sample_sequence64"]),
                                    "validity": "valid" if valid else "invalid",
                                    "invalid_reason": reason,
                                    "stage_assignment_override": (
                                        "unresolved" if status == 3 else "confirmed"
                                    ),
                                    "stage_context_id_override": (
                                        None if status == 3 else self.stage_context_id
                                    ),
                                })
                            self.record_adc_samples(batch_records)
                    except Exception as exc:
                        self.abort("communication_lost", fault=f"ADC telemetry processing failed: {exc}")
                        return self.state
            if self.clock.monotonic_ns() >= int(self.next_deadline_ns):
                try:
                    self._finish_stage()
                    if self.stage_index == self.STAGE_COUNT - 1:
                        self._complete()
                    else:
                        self._begin_stage(self.stage_index + 1)
                except Exception as exc:
                    self.abort("storage_failure", fault=f"RawLog append/finalize failed: {exc}")
        return self.state

    def _finish_stage(self) -> None:
        end_ns = self.clock.monotonic_ns()
        end_utc = self.clock.utc_now()
        disarm = getattr(self.protocol_session, "disarm_stage", None)
        if callable(disarm):
            # Normal stage boundary: wait for DISARM_ACK before any next-stage ARM.
            disarm()
            self._append(
                "SESSION_EVENT", event="OTHER", host_monotonic_ns=end_ns,
                details={"kind": "STAGE_DISARM_ACKNOWLEDGED",
                         "stage_index": self.stage_index,
                         "stage_id": f"PWM-{self.stage_index:02d}",
                         "stage_context_id": self.stage_context_id,
                         "stage_ended_at_utc": end_utc,
                         "stage_end_host_monotonic_ns": end_ns,
                         "direction": self.current_stage_direction},
            )
        self._append("PWM_STAGE", stage_id=f"PWM-{self.stage_index:02d}",
                     stage_index=self.stage_index, pwm_command=self.stage_index,
                     planned_duration_ms=self.STAGE_DURATION_MS, stage_status="completed",
                     started_at_utc=self.stage_start_utc, ended_at_utc=end_utc,
                     start_host_monotonic_ns=self.stage_start_ns, end_host_monotonic_ns=end_ns,
                     actual_duration_ms=(end_ns - int(self.stage_start_ns)) / 1_000_000,
                     pwm_command_sent_at_utc=self.command_sent_utc,
                     pwm_applied_ack_received_at_utc=self.ack_utc,
                     output_state="unknown", stage_context_id=self.stage_context_id,
                     termination_reason="duration_elapsed")
        self._stage_recorded = True

    def record_adc_samples(self, samples: list[dict]) -> None:
        """Persist one validated protocol ADC_BATCH as one RawLog durability unit."""
        from raw_log_v2.validator import CHANNELS
        if not isinstance(samples, list) or len(samples) != 12:
            raise ValueError("protocol ADC sample batch must contain exactly 12 samples")
        if self.session is None:
            raise SequenceError("RawLog session is not open")
        records = []
        base_seq = int(self.session.state["last_record_seq"]) + 1
        for offset, sample in enumerate(samples):
            channel = sample["channel"]
            if channel not in CHANNELS:
                raise ValueError("unknown ADC channel")
            bits = sample["adc_resolution_bits"]
            if isinstance(bits, bool) or not isinstance(bits, int) or not 1 <= bits <= 32:
                raise ValueError("adc_resolution_bits must be 1..32")
            sensor, role = CHANNELS[channel]
            now_ns = self.clock.monotonic_ns()
            override = sample.get("stage_assignment_override")
            if override is None:
                confirmed = self.state == SequenceState.RUNNING and self.stage_context_id is not None
                context_id = self.stage_context_id if confirmed else None
            else:
                if override not in {"confirmed", "unresolved"}:
                    raise ValueError("stage_assignment_override must be confirmed or unresolved")
                confirmed = override == "confirmed"
                context_id = sample.get("stage_context_id_override") if confirmed else None
                if confirmed and not context_id:
                    raise ValueError("confirmed sample requires stage_context_id_override")
            records.append({
                "schema_version": "2.0.0", "record_type": "ADC_SAMPLE",
                "record_id": str(uuid.uuid4()), "record_seq": base_seq + offset,
                "log_id": self.session.state["log_id"],
                "measurement_session_id": self.session.state["measurement_session_id"],
                "recorded_at_utc": self.clock.utc_now(),
                "sample_id": str(uuid.uuid4()), "channel": channel, "sensor": sensor,
                "signal_role": role, "adc_raw": sample["adc_raw"],
                "adc_resolution_bits": bits, "raw_unit": "count",
                "device_timestamp_us_u32": sample["device_timestamp_us_u32"],
                "device_timestamp_point": sample["device_timestamp_point"],
                "device_epoch_id": sample["device_epoch_id"],
                "device_elapsed_us": sample["device_elapsed_us"],
                "device_sample_sequence": sample["device_sample_sequence"],
                "host_received_at_utc": self.clock.utc_now(),
                "host_received_monotonic_ns": now_ns,
                "stage_context_id": context_id,
                "stage_id": f"PWM-{self.stage_index:02d}" if confirmed else None,
                "stage_assignment": "confirmed" if confirmed else "unresolved",
                "calibration_id": None, "validity": sample["validity"],
                "invalid_reason": sample["invalid_reason"],
            })
        try:
            if self.session is None:
                raise SequenceError("RawLog session is not open")
            self.session.append_many(records)
        except Exception as exc:
            # append_many may have written a partial/torn tail or durable records
            # without a durable work-state update. Never append another record
            # to this work area; startup recovery must reconcile the bytes.
            self._log_write_failed = True
            self.abort("storage_failure", fault=f"RawLog ADC_SAMPLE batch append failed: {exc}")
            raise SequenceError("ADC sample batch storage failed; sequence stopped") from exc

    def record_adc_sample(
        self, channel: str, adc_raw: Optional[int], adc_resolution_bits: int,
        device_timestamp_us_u32: Optional[int], device_timestamp_point: str,
        device_epoch_id: str, device_elapsed_us: Optional[int] = None,
        device_sample_sequence: Optional[int] = None, validity: str = "valid",
        invalid_reason: Optional[str] = None,
        stage_assignment_override: Optional[str] = None,
        stage_context_id_override: Optional[str] = None,
    ) -> None:
        """Persist one channel observation without merging or re-timing ADC samples."""
        from raw_log_v2.validator import CHANNELS
        if channel not in CHANNELS:
            raise ValueError("unknown ADC channel")
        if not isinstance(adc_resolution_bits, int) or isinstance(adc_resolution_bits, bool) or not 1 <= adc_resolution_bits <= 32:
            raise ValueError("adc_resolution_bits must be 1..32")
        sensor, role = CHANNELS[channel]
        now_ns = self.clock.monotonic_ns()
        if stage_assignment_override is None:
            confirmed = self.state == SequenceState.RUNNING and self.stage_context_id is not None
            assigned_context_id = self.stage_context_id if confirmed else None
        else:
            if stage_assignment_override not in {"confirmed", "unresolved"}:
                raise ValueError("stage_assignment_override must be confirmed or unresolved")
            confirmed = stage_assignment_override == "confirmed"
            assigned_context_id = stage_context_id_override if confirmed else None
            if confirmed and not assigned_context_id:
                raise ValueError("confirmed sample requires stage_context_id_override")
        try:
            self._append(
                "ADC_SAMPLE", sample_id=str(uuid.uuid4()), channel=channel,
                sensor=sensor, signal_role=role, adc_raw=adc_raw,
                adc_resolution_bits=adc_resolution_bits, raw_unit="count",
                device_timestamp_us_u32=device_timestamp_us_u32,
                device_timestamp_point=device_timestamp_point,
                device_epoch_id=device_epoch_id, device_elapsed_us=device_elapsed_us,
                device_sample_sequence=device_sample_sequence,
                host_received_at_utc=self.clock.utc_now(),
                host_received_monotonic_ns=now_ns,
                stage_context_id=assigned_context_id,
                stage_id=f"PWM-{self.stage_index:02d}" if confirmed else None,
                stage_assignment="confirmed" if confirmed else "unresolved",
                calibration_id=None, validity=validity, invalid_reason=invalid_reason,
            )
        except Exception as exc:
            self.abort("storage_failure", fault=f"RawLog ADC_SAMPLE append failed: {exc}")
            raise SequenceError("ADC sample storage failed; sequence stopped") from exc

    def record_visual_event(self, event: str, actor: str, observed_at_utc: str) -> None:
        """Record a human observation; never infer rotation from sensor values."""
        if event not in {"ROTATION_START_CONFIRMED", "ROTATION_NOT_OBSERVED_AT_STAGE"}:
            raise ValueError("unsupported visual event")
        if not actor or not observed_at_utc:
            raise ValueError("actor and observed_at_utc are required")
        confirmed = self.state == SequenceState.RUNNING
        try:
            self._append(
                "EVENT", event=event, observation_method="human_visual", actor=actor,
                observed_at_utc=observed_at_utc, reported_at_utc=self.clock.utc_now(),
                host_monotonic_ns=self.clock.monotonic_ns(),
                stage_id=f"PWM-{self.stage_index:02d}" if confirmed else None,
                stage_index=self.stage_index if confirmed else None,
                pwm_value=self.stage_index if confirmed else None,
            )
        except Exception as exc:
            self.abort("storage_failure", fault=f"RawLog EVENT append failed: {exc}")
            raise SequenceError("visual event storage failed; sequence stopped") from exc

    def _complete(self) -> None:
        # The final PWM_SET has no device-side duration field. Therefore normal
        # completion must request STOP before recording/finalizing completion.
        self.state = SequenceState.FINALIZING
        self._stop_attempted = True
        try:
            self.send_normal_stop()
        except Exception as exc:
            self._last_fault = f"normal completion STOP failed: {exc}"
            self.state = SequenceState.FAULT
            raise SequenceError(
                "normal completion STOP failed; RawLog remains incomplete"
            ) from exc
        self._append(
            "SESSION_EVENT", event="SESSION_COMPLETED",
            host_monotonic_ns=self.clock.monotonic_ns(),
            details={
                "stages_completed": 31,
                "stop_transmission_attempted": True,
                "device_state": "unknown",
            },
        )
        self._finalization_started = True
        final_dir = self.session.finalize({"record_counts": {}}, "completed", self.clock.utc_now())
        if self.protocol_session is not None:
            finalize_bundle = getattr(self.protocol_session, "finalize_evidence_bundle", None)
            if callable(finalize_bundle):
                try:
                    finalize_bundle(final_dir)
                except Exception as exc:
                    self._last_fault = f"Evidence companion-manifest finalization failed: {exc}"
                    self._recovery_requires_review = True
                    try:
                        self._mark_evidence_reconciliation_required(str(exc))
                    except Exception as marker_exc:
                        self._last_fault += f"; re-arm marker write failed: {marker_exc}"
                    self.state = SequenceState.FAULT
                    raise SequenceError(
                        "RawLog package finalized but Evidence bundle is untrusted; re-arm is inhibited"
                    ) from exc
        self.state = SequenceState.COMPLETED

    def _mark_evidence_reconciliation_required(self, reason: str) -> None:
        marker = self.writer.root / ".310-evidence-reconciliation-required"
        if marker.is_symlink():
            raise SequenceError("Evidence reconciliation marker must not be a symlink")
        if not marker.exists():
            payload = (
                "Protocol Evidence companion finalization failed; verify the RawLog package "
                "and external Evidence sidecar before any re-arm. Reason: " + str(reason) + "\n"
            ).encode("utf-8")
            fd = os.open(str(marker), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                written = os.write(fd, payload)
                if written != len(payload):
                    raise OSError("short Evidence reconciliation marker write")
                os.fsync(fd)
            finally:
                os.close(fd)
            dir_fd = os.open(str(self.writer.root), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)

    def _record_aborted_stage(self, reason: str) -> None:
        if self.session is None or self.stage_index < 0 or self.stage_context_id is None or self._stage_recorded:
            return
        if self.command_sent_utc is None:
            # The transport raised before confirming a completed host write.
            # Do not invent a command-send timestamp or imply it was sent.
            return
        end_ns = self.clock.monotonic_ns()
        end_utc = self.clock.utc_now()
        reason_map = {
            "user_stop": "user_stop", "safety_stop": "safety_stop",
            "communication_lost": "communication_lost",
            "process_interrupted": "process_interrupted",
        }
        termination = reason_map.get(reason, "other")
        acknowledged = self.ack_utc is not None and self.stage_start_ns is not None
        self._append(
            "PWM_STAGE", stage_id=f"PWM-{self.stage_index:02d}",
            stage_index=self.stage_index, pwm_command=self.stage_index,
            planned_duration_ms=self.STAGE_DURATION_MS, stage_status="aborted",
            started_at_utc=self.stage_start_utc if acknowledged else None,
            ended_at_utc=end_utc,
            start_host_monotonic_ns=self.stage_start_ns if acknowledged else None,
            end_host_monotonic_ns=end_ns,
            actual_duration_ms=((end_ns - self.stage_start_ns) / 1_000_000) if acknowledged else None,
            pwm_command_sent_at_utc=self.command_sent_utc,
            pwm_applied_ack_received_at_utc=self.ack_utc if acknowledged else None,
            output_state="unknown", stage_context_id=self.stage_context_id,
            termination_reason=termination,
        )

    def abort(self, reason: str, fault: Optional[str] = None) -> None:
        # A non-blocking acquisition avoids deadlock on same-thread callback
        # re-entry and makes the state check/latch atomic across caller threads.
        if not self._abort_lock.acquire(blocking=False):
            return
        try:
            if self.state in {SequenceState.STOPPING, SequenceState.ABORTED,
                             SequenceState.FAULT, SequenceState.COMPLETED}:
                return
            previous = self.state
            self.state = SequenceState.STOPPING
        finally:
            self._abort_lock.release()
        self._last_fault = fault
        # Inhibit any later v1 command in memory only; never let journal I/O delay STOP.
        if self.protocol_session is not None:
            try:
                latch = getattr(self.protocol_session, "latch_abort", None)
                if callable(latch):
                    latch(reason)
            except Exception as exc:
                self._last_fault = f"{self._last_fault or reason}; protocol latch failed: {exc}"
        # STOP transmission must be attempted before any RawLog append/fsync.
        # Logging is secondary evidence and must never delay the emergency command.
        if not self._stop_attempted:
            self._stop_attempted = True
            try:
                self.send_stop()
            except Exception as exc:
                self._last_fault = f"{self._last_fault or reason}; STOP send failed: {exc}"
        if not self._finalization_started and not self._log_write_failed:
            try:
                self._record_aborted_stage(reason)
            except Exception as exc:
                self._last_fault = f"{self._last_fault or reason}; stage log failed: {exc}"
        self.state = SequenceState.FAULT if self._last_fault else SequenceState.ABORTED
        # Keep work area incomplete for crash-safe recovery; do not falsely finalize
        # a partially completed sequence or claim physical stop.
        if (self.session is not None and not self._finalization_started
                and not self._log_write_failed):
            try:
                self._append("SESSION_EVENT", event="COMMUNICATION_LOST" if fault else "SESSION_ABORTED",
                             host_monotonic_ns=self.clock.monotonic_ns(),
                             details={"reason": reason, "previous_state": previous.value,
                                      "stop_transmission_attempted": True,
                                      "device_state": "unknown", "fault": self._last_fault})
            except Exception:
                # Preserve the private work area for next-startup recovery.
                self.state = SequenceState.FAULT
