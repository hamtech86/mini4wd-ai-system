"""PC-side 310-second PWM sweep coordinator for winding micro-current tests.

This controller schedules PWM 0..30 in Python. The Arduino only executes each
explicit command and emits telemetry. No hardware is touched by importing this
module; start() requires an already identified, connected SerialController.
"""
from __future__ import annotations

from datetime import datetime, timezone
import time
from typing import Callable

from communication.protocol import CSV_FIELDS
from raw_log_library.v2_store import RawLogV2Store


class WindingSweepError(RuntimeError):
    """Raised for an invalid sweep lifecycle or failed command path."""


class WindingPwmSweepController:
    STAGES = tuple(range(31))
    STAGE_HOLD_SECONDS = 10.0

    def __init__(
        self,
        serial_controller,
        rawlog_store: RawLogV2Store,
        *,
        monotonic: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.device = serial_controller
        self.store = rawlog_store
        self.monotonic = monotonic
        self.wall_clock = wall_clock
        self.active = False
        self.stage_index = -1
        self.stage_pwm = 0
        self._started_monotonic = None
        self._stage_started_monotonic = None
        self._measurement_session_id = None
        self._record_sequence = 0
        self._raw_offset = 0
        self._line_buffer = ""

    @property
    def status(self) -> str:
        if self.active:
            return "RUNNING"
        return "IDLE"

    @property
    def elapsed_seconds(self) -> float:
        if self._started_monotonic is None:
            return 0.0
        return max(0.0, self.monotonic() - self._started_monotonic)

    def start(
        self,
        *,
        log_id: str,
        measurement_session_id: str,
        measurement_plan_id: str = "WINDING_PWM_SWEEP_0_30",
    ) -> bool:
        """Create a v2 package, ARM the identified device, and begin PWM 0."""
        if self.active:
            raise WindingSweepError("sweep is already active")
        if not getattr(self.device, "connected", False):
            raise WindingSweepError("serial device is not connected")
        if not getattr(self.device, "identity_verified", False):
            raise WindingSweepError("verified firmware identity is required")
        info = getattr(self.device, "device_info", None)
        if not isinstance(info, dict):
            raise WindingSweepError("verified device_info is unavailable")
        required_info = ("TYPE", "MODEL", "FW", "BUILD", "ID")
        if any(not isinstance(info.get(key), str) or not info[key].strip() for key in required_info):
            raise WindingSweepError("device_info is incomplete")

        started_at = self._now_iso()
        device_info = {
            "type": info["TYPE"],
            "model": info["MODEL"],
            "device_id": info["ID"],
        }
        firmware_info = {"version": info["FW"], "build": info["BUILD"]}
        plan = {
            "id": measurement_plan_id,
            "pwm_stages": list(self.STAGES),
            "stage_hold_seconds": self.STAGE_HOLD_SECONDS,
            "priority_pwm_candidates": list(range(1, 10)),
            "orchestrator": "PYTHON",
        }
        self.store.create({
            "schema": "mini4wd.rawlog.v2",
            "log_id": log_id,
            "measurement_session_id": measurement_session_id,
            "status": "STARTED",
            "started_at": started_at,
            "device": device_info,
            "firmware": firmware_info,
            "measurement_plan": plan,
        })

        self.active = True
        self._measurement_session_id = measurement_session_id
        self._started_monotonic = self.monotonic()
        self._stage_started_monotonic = self._started_monotonic
        self._record_sequence = 0
        self.stage_index = 0
        self.stage_pwm = 0
        self._raw_offset = 0
        self._line_buffer = ""

        self._append_record({
            "record_type": "SESSION",
            "session_status": "STARTED",
            "device": device_info,
            "firmware": firmware_info,
            "measurement_plan": plan,
        })
        if self.device.arm() is False:
            self._fault("ARM_FAILED")
            return False
        # arm() resets the firmware raw capture after its token-matched ACK.
        if self.device.forward() is False:
            self._fault("DIRECTION_COMMAND_FAILED")
            return False
        if self.device.set_pwm(0) is False:
            self._fault("PWM_ZERO_COMMAND_FAILED")
            return False
        # The 10-second baseline dwell begins only after the PWM=0 command
        # succeeds, not while ARM is still waiting for its acknowledgement.
        self._stage_started_monotonic = self.monotonic()

        self._append_event("SWEEP_STARTED", {
            "stage_count": len(self.STAGES),
            "stage_hold_seconds": self.STAGE_HOLD_SECONDS,
            "orchestrator": "PYTHON",
        })
        self._append_stage_started()
        return True

    def tick(self) -> dict:
        """Poll telemetry and advance at most one PWM stage without blocking."""
        if not self.active:
            return {"status": self.status, "stage_index": self.stage_index, "pwm": self.stage_pwm}
        try:
            if not getattr(self.device, "connected", False):
                self._fault("SERIAL_CONNECTION_LOST")
                return self._snapshot()
            self.device.read_measurement()
            if getattr(self.device, "device_reboot_detected", False):
                self._fault("FIRMWARE_REBOOT_DETECTED")
                return self._snapshot()
            if not getattr(self.device, "identity_verified", False):
                self._fault("FIRMWARE_IDENTITY_LOST")
                return self._snapshot()
            self._consume_new_lines()
            if not self.active:
                return self._snapshot()

            now = self.monotonic()
            if now - self._stage_started_monotonic < self.STAGE_HOLD_SECONDS:
                return self._snapshot()

            if self.stage_index < len(self.STAGES) - 1:
                next_index = self.stage_index + 1
                next_pwm = self.STAGES[next_index]
                if self.device.set_pwm(next_pwm) is False:
                    self._fault("PWM_STAGE_COMMAND_FAILED")
                    return self._snapshot()
                self.stage_index = next_index
                self.stage_pwm = next_pwm
                self._stage_started_monotonic = now
                self._append_stage_started()
                return self._snapshot()

            self._complete()
            return self._snapshot()
        except Exception as exc:
            self._fault("SWEEP_EXCEPTION", detail=f"{type(exc).__name__}: {exc}")
            return self._snapshot()

    def record_rotation_observation(self, label: str, note: str = "") -> None:
        """Attach the user's visual rotation label to the currently active stage."""
        labels = {"NO_ROTATION", "ROTATION", "UNKNOWN"}
        if label not in labels:
            raise ValueError("label must be NO_ROTATION, ROTATION, or UNKNOWN")
        if not self.active:
            raise WindingSweepError("no active sweep")
        self._append_event("ROTATION_OBSERVATION", {
            "label": label,
            "stage_index": self.stage_index,
            "pwm": self.stage_pwm,
            "note": str(note),
            "source": "USER_VISUAL",
        })

    def stop(self, reason: str = "USER_STOP") -> bool:
        """Stop normally and retain all collected data as an incomplete sweep."""
        if not self.active:
            return False
        try:
            if getattr(self.device, "connected", False):
                self.device.read_measurement()
                self._consume_new_lines()
                result = self.device.stop_breakin()
                if result is False:
                    self._fault("STOP_COMMAND_FAILED", detail=reason)
                    return False
            else:
                self._fault("SERIAL_CONNECTION_LOST", detail=reason)
                return False
            self._append_event("SWEEP_STOPPED", {
                "reason": reason,
                "completed_stage_index": self.stage_index,
                "completed_pwm": self.stage_pwm,
            })
            self._finish("STOPPED", reason)
            return True
        except Exception as exc:
            self._fault("STOP_EXCEPTION", detail=f"{type(exc).__name__}: {exc}")
            return False

    def _complete(self) -> None:
        self.device.read_measurement()
        self._consume_new_lines()
        if not self.active:
            return
        result = self.device.stop_breakin()
        if result is False:
            self._fault("FINAL_STOP_COMMAND_FAILED")
            return
        self._append_event("SWEEP_COMPLETED", {
            "stage_count": len(self.STAGES),
            "nominal_duration_seconds": len(self.STAGES) * self.STAGE_HOLD_SECONDS,
        })
        self._finish("COMPLETE", None)

    def _fault(self, code: str, detail: str | None = None) -> None:
        if not self.active:
            return
        try:
            emergency_stop = getattr(self.device, "emergency_stop", None)
            if callable(emergency_stop):
                emergency_stop()
        except Exception:
            pass
        try:
            self._consume_new_lines(flush_partial=True)
            details = {"code": code, "stage_index": self.stage_index, "pwm": self.stage_pwm}
            if detail:
                details["detail"] = detail
            self._append_event("SWEEP_FAULT", details)
            self._finish("FAULTED", code)
        except Exception:
            # Preserve the original failure; the package may remain STARTED and
            # therefore visibly incomplete rather than falsely marked complete.
            self.active = False

    def _finish(self, status: str, reason: str | None) -> None:
        self._consume_new_lines(flush_partial=True)
        self.store.finalize(status, self._now_iso(), reason)
        self.active = False

    def _append_stage_started(self) -> None:
        self._append_event("PWM_STAGE_STARTED", {
            "stage_index": self.stage_index,
            "pwm": self.stage_pwm,
            "hold_seconds": self.STAGE_HOLD_SECONDS,
        })

    def _append_event(self, event_type: str, details: dict) -> None:
        self._append_record({
            "record_type": "EVENT",
            "event_type": event_type,
            "details": details,
        })

    def _append_record(self, payload: dict) -> None:
        now = self.monotonic()
        elapsed_ms = max(0, int((now - self._started_monotonic) * 1000))
        sequence = self._record_sequence
        self._record_sequence += 1
        record = {
            "schema": "mini4wd.rawlog.v2",
            "log_id": self.store.log_id,
            "measurement_session_id": self._measurement_session_id,
            "record_id": f"{self._measurement_session_id}-{sequence:08d}",
            "sequence": sequence,
            "elapsed_time_ms": elapsed_ms,
            "recorded_at": self._now_iso(),
        }
        record.update(payload)
        self.store.append(record)

    def _consume_new_lines(self, flush_partial: bool = False) -> None:
        raw_text = getattr(self.device, "raw_log", "")
        if not isinstance(raw_text, str):
            return
        if len(raw_text) < self._raw_offset:
            self._raw_offset = 0
            self._line_buffer = ""
        pending = raw_text[self._raw_offset:]
        self._raw_offset = len(raw_text)
        combined = self._line_buffer + pending
        lines = combined.splitlines(keepends=True)
        self._line_buffer = ""
        for index, line in enumerate(lines):
            if line.endswith("\n") or line.endswith("\r"):
                self._handle_wire_line(line.rstrip("\r\n"))
            elif index == len(lines) - 1 and not flush_partial:
                self._line_buffer = line
            elif line:
                self._handle_wire_line(line)
        if flush_partial and self._line_buffer:
            self._handle_wire_line(self._line_buffer)
            self._line_buffer = ""

    def _handle_wire_line(self, line: str) -> None:
        if not line:
            return
        if line == "INFO" or line.startswith("INFO,"):
            return
        if line.startswith("DATA,"):
            self._append_measurement(line)
            return
        if line.startswith("AUX,"):
            self._append_adc_sample(line)
            return
        if line.startswith("ERROR,"):
            self._append_event("DEVICE_ERROR", {"raw_line": line})
            raise WindingSweepError("firmware reported " + line)
        self._append_event("TRANSPORT_LINE", {"raw_line": line})

    def _append_measurement(self, raw_line: str) -> None:
        values = raw_line.split(",")
        if len(values) != len(CSV_FIELDS) or values[0] != "DATA":
            self._append_event("INVALID_MEASUREMENT_LINE", {
                "raw_line": raw_line,
                "reason": "unexpected DATA field count or record type",
            })
            return
        parsed = {}
        for key, value in zip(CSV_FIELDS, values):
            value = value.strip()
            if key in {"device_model", "instance_id", "direction", "state", "record_type"}:
                parsed[key] = value
            elif value == "":
                parsed[key] = None
            else:
                try:
                    parsed[key] = float(value) if "." in value else int(value)
                except ValueError:
                    parsed[key] = value

        mapping = {
            "device_model": parsed.get("device_model"),
            "instance_id": parsed.get("instance_id"),
            "raw_acs1": parsed.get("raw_acs1"),
            "raw_acs2": parsed.get("raw_acs2"),
            "current1_a": parsed.get("current1"),
            "current2_a": parsed.get("current2"),
            "voltage1_v": parsed.get("voltage1"),
            "voltage2_v": parsed.get("voltage2"),
            "motor_voltage_v": parsed.get("motor_voltage"),
            "pwm": parsed.get("pwm"),
            "direction": parsed.get("direction"),
            "state": parsed.get("state"),
            "current_avg_a": parsed.get("current_avg"),
            "power_w": parsed.get("power"),
            "current_ripple_a": parsed.get("current_ripple"),
            "voltage_ripple_v": parsed.get("voltage_ripple"),
            "peak_power_w": parsed.get("peak_power"),
            "peak_current_a": parsed.get("peak_current"),
            "peak_voltage_v": parsed.get("peak_voltage"),
            "peak_pwm": parsed.get("peak_pwm"),
            "brush_peak_current_a": parsed.get("brush_peak_current"),
            "raw_magnetic": parsed.get("raw_magnetic"),
            "magnetic_level": parsed.get("magnetic_level"),
            "motor_temperature_c": parsed.get("motor_temperature"),
        }
        unavailable = [
            {"field": key, "reason": "not_provided_in_DATA_record"}
            for key, value in mapping.items()
            if value is None and key not in {"device_model", "instance_id", "state", "direction"}
        ]
        payload = {
            "record_type": "MEASUREMENT",
            **mapping,
            "unavailable_fields": unavailable,
            "firmware_elapsed_time_ms": parsed.get("elapsed_time"),
            "raw_wire_line": raw_line,
        }
        try:
            self._append_record(payload)
        except Exception as exc:
            self._append_event("INVALID_MEASUREMENT_LINE", {
                "raw_line": raw_line,
                "reason": f"{type(exc).__name__}: {exc}",
            })

    def _append_adc_sample(self, raw_line: str) -> None:
        fields = raw_line.split(",")
        if len(fields) != 11 or fields[0] != "AUX" or fields[1] != "2":
            self._append_event("INVALID_ADC_SAMPLE_LINE", {
                "raw_line": raw_line,
                "reason": "AUX v2 requires exactly 11 fields",
            })
            return
        try:
            _, _, firmware_session, sample_sequence, phase, direction, pwm, run_state, channel, adc_raw, timestamp_us = fields
            payload = {
                "record_type": "ADC_SAMPLE",
                "channel": channel,
                "adc_raw": int(adc_raw),
                "timestamp_us": int(timestamp_us),
                "acquisition_sequence": int(sample_sequence),
                "phase": phase,
                "direction": direction,
                "pwm": int(pwm),
                "run_state": run_state,
                "firmware_session_id": firmware_session,
                "raw_wire_line": raw_line,
            }
            self._append_record(payload)
        except Exception as exc:
            self._append_event("INVALID_ADC_SAMPLE_LINE", {
                "raw_line": raw_line,
                "reason": f"{type(exc).__name__}: {exc}",
            })

    def _now_iso(self) -> str:
        value = self.wall_clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise WindingSweepError("wall_clock must return a timezone-aware datetime")
        return value.isoformat(timespec="milliseconds")

    def _snapshot(self) -> dict:
        return {
            "status": self.status,
            "stage_index": self.stage_index,
            "pwm": self.stage_pwm,
            "elapsed_seconds": self.elapsed_seconds,
        }
