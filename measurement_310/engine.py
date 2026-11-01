"""310-stage sequence orchestration and RawLog v2 adapter."""
from __future__ import annotations

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
        send_pwm: Callable[[int], str],
        send_stop: Callable[[], None],
        poll_ack: Callable[[], Optional[tuple[int, str]]],
        clock: Optional[Clock] = None,
        ack_timeout_ms: int = 2_000,
    ) -> None:
        self.writer = writer
        self.manifest_fields = dict(manifest_fields)
        self.send_pwm = send_pwm
        self.send_stop = send_stop
        self.poll_ack = poll_ack
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
        self._finalization_started = False
        # Once any append fails, this session is write-disabled. STOP is still attempted.
        self._log_write_failed = False

    def startup_recover(self) -> list[dict[str, Any]]:
        if self.state != SequenceState.READY:
            raise SequenceError("startup recovery must precede session start")
        # Explicitly discover, then recover. No measurement is permitted on failure.
        pending_before = self.writer.list_incomplete_work()
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
        self._recovery_complete = True
        return result

    def start(self) -> None:
        if not self._recovery_complete:
            raise SequenceError("startup recovery has not completed")
        if self.state != SequenceState.READY:
            raise SequenceError("controller is not ready")
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

    def _begin_stage(self, index: int) -> None:
        if self.state in {SequenceState.FAULT, SequenceState.ABORTED, SequenceState.STOPPING}:
            return
        self.stage_index = index
        self.stage_context_id = str(uuid.uuid4())
        self._stage_recorded = False
        self.command_sent_utc = None
        self.command_sent_ns = self.clock.monotonic_ns()
        self.ack_utc = None
        self.stage_start_ns = None
        self.stage_start_utc = None
        self.next_deadline_ns = None
        try:
            self.command_sent_utc = self.send_pwm(index)
        except Exception as exc:
            self.abort("communication_lost", fault=f"PWM send failed: {exc}")
            return
        self.state = SequenceState.WAITING_ACK

    def poll(self) -> SequenceState:
        """Advance using injected clock; caller controls polling cadence."""
        if self.state == SequenceState.WAITING_ACK:
            try:
                ack = self.poll_ack()
            except Exception as exc:
                self.abort("communication_lost", fault=str(exc))
                return self.state
            if ack is not None:
                if not isinstance(ack, tuple) or len(ack) != 2:
                    self.abort("communication_lost", fault="malformed ACK object")
                    return self.state
                pwm, ack_utc = ack
                if not isinstance(pwm, int) or isinstance(pwm, bool) or not isinstance(ack_utc, str):
                    self.abort("communication_lost", fault="malformed ACK fields")
                    return self.state
                if pwm != self.stage_index:
                    self.abort("communication_lost", fault="ACK PWM mismatch")
                    return self.state
                self.ack_utc = ack_utc
                self.stage_start_utc = ack_utc
                self.stage_start_ns = self.clock.monotonic_ns()
                self.next_deadline_ns = self.stage_start_ns + self.STAGE_DURATION_MS * 1_000_000
                self.state = SequenceState.RUNNING
                try:
                    self._append("SESSION_EVENT", event="OTHER",
                                 host_monotonic_ns=self.stage_start_ns,
                                 details={"kind": "PWM_ACK_RECEIVED",
                                          "stage_index": self.stage_index,
                                          "command_sent_host_monotonic_ns": self.command_sent_ns,
                                          "ack_received_host_monotonic_ns": self.stage_start_ns,
                                          "command_to_ack_delay_ms":
                                              (self.stage_start_ns - int(self.command_sent_ns)) / 1_000_000})
                except Exception as exc:
                    self.abort("storage_failure", fault=f"RawLog ACK record failed: {exc}")
            elif self.clock.monotonic_ns() - int(self.command_sent_ns) >= self.ack_timeout_ns:
                self.abort("communication_lost", fault="PWM ACK timeout")
        elif self.state == SequenceState.RUNNING:
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

    def record_adc_sample(
        self, channel: str, adc_raw: Optional[int], adc_resolution_bits: int,
        device_timestamp_us_u32: Optional[int], device_timestamp_point: str,
        device_epoch_id: str, device_elapsed_us: Optional[int] = None,
        device_sample_sequence: Optional[int] = None, validity: str = "valid",
        invalid_reason: Optional[str] = None,
    ) -> None:
        """Persist one channel observation without merging or re-timing ADC samples."""
        from raw_log_v2.validator import CHANNELS
        if channel not in CHANNELS:
            raise ValueError("unknown ADC channel")
        if not isinstance(adc_resolution_bits, int) or isinstance(adc_resolution_bits, bool) or not 1 <= adc_resolution_bits <= 32:
            raise ValueError("adc_resolution_bits must be 1..32")
        sensor, role = CHANNELS[channel]
        now_ns = self.clock.monotonic_ns()
        confirmed = self.state == SequenceState.RUNNING and self.stage_context_id is not None
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
                stage_context_id=self.stage_context_id if confirmed else None,
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
        self._append("SESSION_EVENT", event="SESSION_COMPLETED",
                     host_monotonic_ns=self.clock.monotonic_ns(), details={"stages_completed": 31})
        self.state = SequenceState.FINALIZING
        self._finalization_started = True
        self.session.finalize({"record_counts": {}}, "completed", self.clock.utc_now())
        self.state = SequenceState.COMPLETED

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
        if self.state in {SequenceState.ABORTED, SequenceState.COMPLETED}:
            return
        previous = self.state
        self.state = SequenceState.STOPPING
        self._last_fault = fault
        if not self._finalization_started and not self._log_write_failed:
            try:
                self._record_aborted_stage(reason)
            except Exception as exc:
                self._last_fault = f"{self._last_fault or reason}; stage log failed: {exc}"
        try:
            self.send_stop()
        except Exception as exc:
            self._last_fault = f"{self._last_fault or reason}; STOP send failed: {exc}"
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
