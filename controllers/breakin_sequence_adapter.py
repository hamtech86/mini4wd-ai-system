"""Adapter between the generic SequenceExecutor and BreakinController.

This bridge intentionally reuses the controller's existing serial and
measurement primitives. It does not call BreakinController.start(), so the
legacy blocking phase loop is not nested inside the new executor.
"""

from .recipe import BreakinPhase


class BreakinSequenceAdapter:
    """Translate SequenceDefinition rows into safe motor-control operations."""

    def __init__(self, controller):
        self.controller = controller
        self._active = None
        self._last_measurement = None

    def start_sequence(self, sequence):
        # The generic sequence executor bypasses MainWindow's recipe callback.
        # Enforce the authorized firmware identity at this last software boundary
        # before ARM, direction, or PWM can be issued.
        serial_controller = self.controller.serial
        info = getattr(serial_controller, "device_info", None) or {}
        expected = {
            "TYPE": "MOTOR",
            "MODEL": "MOTOR_BREAKIN_V3",
            "FW": "3.03",
            "BUILD": "EXPLICIT-ARM-STOP-ACK-20261023-01",
        }
        if (
            getattr(serial_controller, "identity_verified", False) is not True
            or any(info.get(key) != value for key, value in expected.items())
        ):
            raise RuntimeError(
                "Sequence start rejected: exact authorized MOTOR_BREAKIN_V3 firmware "
                "identity is required; no ARM or drive command was issued."
            )
        arm_method = getattr(serial_controller, "arm", None)
        if not callable(arm_method) or arm_method() is False:
            raise RuntimeError("Sequence start rejected because explicit ARM was not accepted.")
        self._active = sequence
        if sequence.direction == "REV":
            self.controller.serial.reverse()
        else:
            self.controller.serial.forward()

        phase = self.to_phase(sequence)
        control = phase.control
        if control in ("VOLTAGE", "VOLTAGE_RAMP", "BRUSH_PEAK_APPROACH"):
            target = phase.start_voltage if control == "VOLTAGE_RAMP" else phase.target_voltage
            pwm = self.controller._initial_pwm_for_voltage(target or 0.0, phase)
        else:
            pwm = sequence.pwm if sequence.pwm is not None else 0
            pwm = max(phase.pwm_min, min(phase.pwm_max, int(pwm)))

        self.controller.current_pwm = pwm
        self.controller.serial.set_pwm(pwm)

    def tick(self, sequence):
        self._active = sequence
        phase = self.to_phase(sequence)
        measurement = self.controller._collect_measurement(phase)
        self._last_measurement = measurement
        if measurement is None:
            return

        control = phase.control
        if control == "VOLTAGE" and phase.target_voltage is not None:
            self.controller._voltage_control(phase, measurement)
        elif control == "VOLTAGE_RAMP":
            self.controller._voltage_ramp_control(phase)
        elif control == "BRUSH_PEAK_APPROACH":
            current = self.controller._current_from_measurement(measurement)
            peak = self.controller._estimate_brush_peak_current()
            if peak >= phase.peak_min_current and current >= peak * (1.0 - phase.peak_margin_ratio):
                self.controller.brush_peak_reached = True
                self.controller.serial.set_pwm(0)
            else:
                self.controller._voltage_control(phase, measurement)

    def stop_sequence(self, sequence):
        stop = getattr(self.controller.serial, "stop_breakin", None)
        if callable(stop):
            stop()
        else:
            self.controller.serial.set_pwm(0)
        self._active = None

    def read_metric(self, metric):
        value = self.controller._measurement_value(self._last_measurement, metric, None)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                return None
        return None

    @staticmethod
    def to_phase(sequence):
        params = sequence.parameters or {}
        control = str(params.get("control", "PWM")).upper()
        return BreakinPhase(
            name=sequence.sequence_id,
            duration_sec=float(sequence.duration_sec or 0.0),
            pwm=int(sequence.pwm or 0),
            direction=sequence.direction or "FWD",
            control=control,
            target_voltage=params.get("target_voltage"),
            start_voltage=params.get("start_voltage"),
            end_voltage=params.get("end_voltage"),
            pwm_min=int(params.get("pwm_min", 0) or 0),
            pwm_max=int(params.get("pwm_max", 255) or 255),
            max_duration_sec=params.get("max_duration_sec"),
            peak_margin_ratio=float(params.get("peak_margin_ratio", 0.10) or 0.10),
            peak_min_current=float(params.get("peak_min_current", 0.0) or 0.0),
            metadata={
                **dict(sequence.metadata or {}),
                "voltage_control_mode": str(
                    (sequence.metadata or {}).get(
                        "voltage_control_mode", params.get("voltage_control_mode", "TERMINAL")
                    )
                ).upper(),
            },
        )
