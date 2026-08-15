"""Break-in Controller - MOTOR_BREAKIN_V3.

Recipe -> Phase Control -> Arduino -> Measurement -> Analysis.

Recipe stages may use ordinary PWM control, closed-loop motor-voltage
control, voltage ramps, or an adaptive brush-peak approach phase.
"""

import time

from .phase_manager import PhaseManager
from .recipe import BreakinPhase, BreakinRecipe


class BreakinController:
    VOLTAGE_KP = 20.0
    CONTROL_INTERVAL_SEC = 0.1
    DEFAULT_SAFETY = {
        "max_motor_temperature": 70.0,
        "max_current": 5.0,
        "max_pwm": 245,
    }

    def __init__(self, serial_controller, measurement_manager=None,
                 analysis_engine=None, database=None, session_manager=None,
                 safety_config=None):
        self.serial = serial_controller
        self.measurement_manager = measurement_manager
        self.analysis_engine = analysis_engine
        self.database = database
        self.session_manager = session_manager
        self.safety_config = dict(self.DEFAULT_SAFETY)
        if safety_config:
            self.safety_config.update(safety_config)
        self.running = False
        self.measurements = []
        self.session = None
        self.current_phase = None
        self.current_pwm = 0
        self.abort_reason = None
        self.phase_started_at = None
        self.current_phase_index = 0
        self.total_phases = 0
        self.last_brush_peak_current = 0.0
        self.brush_peak_target_current = 0.0
        self.brush_peak_reached = False

    def start(self, recipe, instance_id=None):
        self.phase_manager = PhaseManager(recipe)
        self.running = True
        self.measurements = []
        self.abort_reason = None
        self.current_phase = None
        self.current_phase_index = 0
        self.total_phases = len(recipe.phases)
        self.phase_started_at = None
        self.last_brush_peak_current = 0.0
        self.brush_peak_target_current = 0.0
        self.brush_peak_reached = False
        if self.session_manager:
            self.session = self.session_manager.start("BREAKIN", instance_id=instance_id)
        try:
            while self.running and self.phase_manager.has_next():
                self.execute_phase(self.phase_manager.current_phase())
                self.phase_manager.next_phase()
                self.current_phase_index = self.phase_manager.current_index()
            if self.abort_reason:
                raise RuntimeError(self.abort_reason)
            self.stop()
            result = self.analyze(self.measurements)
            if self.session_manager:
                self.session_manager.finish("COMPLETE")
            return result
        except Exception:
            if self.session_manager:
                self.session_manager.finish("ERROR")
            self.emergency_stop()
            raise
        finally:
            self.phase_started_at = None

    def benchmark_3v(self, duration_sec=30, instance_id=None):
        """Run the authoritative standalone 3 V benchmark."""
        phase = BreakinPhase(
            name="BENCHMARK_3V_TEST",
            duration_sec=float(duration_sec),
            pwm=80,
            direction="FWD",
            control="VOLTAGE",
            target_voltage=3.00,
            pwm_min=35,
            pwm_max=120,
        )
        recipe = BreakinRecipe(
            name="MOTOR_BENCHMARK_TEST",
            description="Standalone 3 V motor benchmark test",
            brush="UNKNOWN",
            family="BENCHMARK",
            objective="MEASUREMENT",
            phases=[phase],
            target_rpm=None,
            torque_priority=0.50,
            version="2.1",
        )
        return self.start(recipe, instance_id=instance_id)

    def execute_phase(self, phase):
        self.current_phase = phase
        self.current_phase_index = self.phase_manager.current_index()
        self.abort_reason = None
        self.phase_started_at = time.time()

        if phase.direction == "REV":
            self.serial.reverse()
        else:
            self.serial.forward()

        self.current_pwm = max(phase.pwm_min, min(phase.pwm_max, phase.pwm))
        if phase.control in ("VOLTAGE", "VOLTAGE_RAMP", "BRUSH_PEAK_APPROACH"):
            if phase.control == "VOLTAGE_RAMP":
                target = phase.start_voltage if phase.start_voltage is not None else 0.0
            else:
                target = phase.target_voltage if phase.target_voltage is not None else 0.0
            self.current_pwm = self._initial_pwm_for_voltage(target, phase)

        self.serial.set_pwm(self.current_pwm)

        measurement = self._collect_measurement(phase)
        safety = self._safety_violation(measurement)
        if safety:
            self.abort_reason = safety
            self.emergency_stop()
            return

        if phase.control == "BRUSH_PEAK_APPROACH":
            self._execute_brush_peak_approach(phase)
        else:
            self._execute_standard_phase(phase)

        self.serial.set_pwm(0)
        time.sleep(0.2)

    def _execute_standard_phase(self, phase):
        start = self.phase_started_at
        while self.running and time.time() - start < phase.duration_sec:
            measurement = self._collect_measurement(phase)
            if phase.control == "VOLTAGE" and phase.target_voltage is not None:
                self._voltage_control(phase, measurement)
            elif phase.control == "VOLTAGE_RAMP":
                self._voltage_ramp_control(phase)
            safety = self._safety_violation(measurement)
            if safety:
                self.abort_reason = safety
                self.emergency_stop()
                break
            time.sleep(self.CONTROL_INTERVAL_SEC)

    def _execute_brush_peak_approach(self, phase):
        """Hold 2 V until measured brush current approaches the last benchmark peak.

        The benchmark must precede this phase. The controller intentionally stops
        below the observed peak using peak_margin_ratio, rather than driving
        through the peak.
        """
        peak = self._estimate_brush_peak_current()
        if peak < phase.peak_min_current:
            self.abort_reason = (
                f"BRUSH PEAK APPROACH requires benchmark peak >= "
                f"{phase.peak_min_current:.3f} A; measured {peak:.3f} A"
            )
            self.emergency_stop()
            return

        target = peak * (1.0 - phase.peak_margin_ratio)
        self.brush_peak_target_current = target
        start = self.phase_started_at
        max_duration = phase.max_duration_sec or phase.duration_sec or 1800

        while self.running and time.time() - start < max_duration:
            measurement = self._collect_measurement(phase)
            current = self._current_from_measurement(measurement)
            if current > self.last_brush_peak_current:
                self.last_brush_peak_current = current
            if current >= target:
                self.brush_peak_reached = True
                self.serial.set_pwm(0)
                return
            self._voltage_control(phase, measurement)
            safety = self._safety_violation(measurement)
            if safety:
                self.abort_reason = safety
                self.emergency_stop()
                return
            time.sleep(self.CONTROL_INTERVAL_SEC)

        self.serial.set_pwm(0)

    def _estimate_brush_peak_current(self):
        values = []
        for measurement in self.measurements:
            value = self._measurement_value(measurement, "brush_peak_current", None)
            if value is not None:
                try:
                    values.append(float(value))
                except (TypeError, ValueError):
                    pass
        if values:
            return max(values)
        return max((self._current_from_measurement(m) for m in self.measurements), default=0.0)

    def _initial_pwm_for_voltage(self, target_voltage, phase):
        if target_voltage <= 0:
            return phase.pwm_min
        return max(
            phase.pwm_min,
            min(phase.pwm_max, int(round((target_voltage / 9.0) * 180.0))),
        )

    def _voltage_ramp_control(self, phase):
        elapsed = self.phase_elapsed_sec()
        duration = max(phase.duration_sec, 0.001)
        ratio = max(0.0, min(1.0, elapsed / duration))
        start = phase.start_voltage if phase.start_voltage is not None else 0.0
        end = phase.end_voltage if phase.end_voltage is not None else 0.0
        target = start + (end - start) * ratio
        error_target = BreakinPhase(
            name=phase.name,
            duration_sec=phase.duration_sec,
            pwm=self.current_pwm,
            direction=phase.direction,
            control="VOLTAGE",
            target_voltage=target,
            pwm_min=phase.pwm_min,
            pwm_max=phase.pwm_max,
        )
        measurement = self.measurements[-1] if self.measurements else None
        self._voltage_control(error_target, measurement)

    def phase_elapsed_sec(self):
        if self.phase_started_at is None:
            return 0.0
        return max(0.0, time.time() - self.phase_started_at)

    @staticmethod
    def _measurement_value(measurement, name, default=0.0):
        if measurement is None:
            return default
        if isinstance(measurement, dict):
            return measurement.get(name, default)
        return getattr(measurement, name, default)

    @classmethod
    def _current_from_measurement(cls, measurement):
        current = cls._measurement_value(measurement, "current_avg", None)
        if current is not None:
            try:
                return abs(float(current))
            except (TypeError, ValueError):
                pass
        return max(
            abs(float(cls._measurement_value(measurement, "current1", 0.0) or 0.0)),
            abs(float(cls._measurement_value(measurement, "current2", 0.0) or 0.0)),
        )

    @staticmethod
    def _value(measurement, name, default=0.0):
        return BreakinController._measurement_value(measurement, name, default)

    def _voltage_control(self, phase, measurement):
        voltage = float(self._value(measurement, "motor_voltage", 0.0) or 0.0)
        if voltage <= 0:
            return
        error = float(phase.target_voltage) - voltage
        if abs(error) <= 0.02:
            return
        new_pwm = self.current_pwm + int(round(self.VOLTAGE_KP * error))
        new_pwm = max(phase.pwm_min, min(phase.pwm_max, new_pwm))
        if new_pwm != self.current_pwm:
            self.current_pwm = new_pwm
            self.serial.set_pwm(new_pwm)

    def _safety_violation(self, measurement):
        max_temp = float(self.safety_config.get("max_motor_temperature", 0) or 0)
        max_current = float(self.safety_config.get("max_current", 0) or 0)
        max_pwm = int(self.safety_config.get("max_pwm", 255) or 255)
        temperature = float(self._value(measurement, "motor_temperature", 0.0) or 0.0)
        current = self._current_from_measurement(measurement)
        if max_temp > 0 and temperature >= max_temp:
            return f"SAFETY: motor temperature {temperature:.1f}C >= {max_temp:.1f}C"
        if max_current > 0 and current >= max_current:
            return f"SAFETY: current {current:.2f}A >= {max_current:.2f}A"
        if self.current_pwm > max_pwm:
            return f"SAFETY: PWM {self.current_pwm} > {max_pwm}"
        return None

    def _collect_measurement(self, phase):
        if not self.measurement_manager:
            return None
        measurement = self.measurement_manager.collect()
        if measurement is not None:
            if isinstance(measurement, dict):
                measurement["phase"] = phase
                measurement["phase_pwm"] = self.current_pwm
                measurement["phase_direction"] = phase.direction
            self.measurements.append(measurement)
        return measurement

    def analyze(self, measurements):
        if self.analysis_engine is None:
            return measurements
        return [self.analysis_engine.analyze(measurement) for measurement in measurements]

    def stop(self):
        self.running = False
        if hasattr(self.serial, "stop_breakin"):
            self.serial.stop_breakin()
        self.serial.set_pwm(0)

    def emergency_stop(self):
        self.running = False
        if hasattr(self.serial, "emergency_stop"):
            self.serial.emergency_stop()
        else:
            self.stop()
