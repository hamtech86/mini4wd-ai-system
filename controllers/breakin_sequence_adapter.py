"""Adapter between the generic SequenceExecutor and BreakinController.

This bridge intentionally reuses the controller's existing serial and
measurement primitives.  It does not call BreakinController.start(), so the
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
        self._active = sequence
        if sequence.direction == "REV":
            self.controller.serial.reverse()
        else:
            self.controller.serial.forward()
        pwm = sequence.pwm if sequence.pwm is not None else 0
        self.controller.current_pwm = pwm
        self.controller.serial.set_pwm(pwm)

    def tick(self, sequence):
        self._active = sequence
        phase = self.to_phase(sequence)
        measurement = self.controller._collect_measurement(phase)
        self._last_measurement = measurement
        if measurement is None:
            return
        control = str(sequence.parameters.get("control", "PWM")).upper()
        if control == "VOLTAGE" and phase.target_voltage is not None:
            self.controller._voltage_control(phase, measurement)
        elif control == "VOLTAGE_RAMP":
            self.controller._voltage_ramp_control(phase)

    def stop_sequence(self, sequence):
        self.controller.serial.set_pwm(0)
        self._active = None

    def read_metric(self, metric):
        value = self.controller._measurement_value(self._last_measurement, metric, None)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                return None
        # Analysis-derived values can be supplied by the controller/engine in
        # the future without changing the generic SequenceExecutor contract.
        return None

    @staticmethod
    def to_phase(sequence):
        params = sequence.parameters or {}
        return BreakinPhase(
            name=sequence.sequence_id,
            duration_sec=float(sequence.duration_sec or 0.0),
            pwm=int(sequence.pwm or 0),
            direction=sequence.direction or "FWD",
            control=str(params.get("control", "PWM")),
            target_voltage=params.get("target_voltage"),
            start_voltage=params.get("start_voltage"),
            end_voltage=params.get("end_voltage"),
            pwm_min=int(params.get("pwm_min", 0) or 0),
            pwm_max=int(params.get("pwm_max", 255) or 255),
            max_duration_sec=params.get("max_duration_sec"),
            peak_margin_ratio=float(params.get("peak_margin_ratio", 0.10) or 0.10),
            peak_min_current=float(params.get("peak_min_current", 0.0) or 0.0),
            metadata=dict(sequence.metadata or {}),
        )
