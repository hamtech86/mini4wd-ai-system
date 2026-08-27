"""Break-in Controller - MOTOR_BREAKIN_V3.

Recipe -> Phase Control -> Arduino -> Measurement -> Analysis.

The break-in phases are execution-only. After the recipe completes, a
separate 3 V / 30 s benchmark is run and only benchmark measurements are fed
to the performance/weight analysis. A settling period is excluded so
startup/hand-spin latency and transient break-in values cannot contaminate
the estimate.
"""

import time

from .phase_manager import PhaseManager
from .recipe import BreakinPhase, BreakinRecipe


class BreakinController:
    VOLTAGE_KP = 20.0
    CONTROL_INTERVAL_SEC = 0.1
    BENCHMARK_DURATION_SEC = 30.0
    BENCHMARK_SETTLE_SEC = 1.0
    BENCHMARK_TARGET_VOLTAGE = 3.00
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
        self.benchmark_measurements = []
        self.session = None
        self.current_phase = None
        self.current_pwm = 0
        self.abort_reason = None

    def start(self, recipe):
        """Execute break-in, then 30 s benchmark, then perform final analysis."""
        self.phase_manager = PhaseManager(recipe)
        self.running = True
        self.measurements = []
        self.benchmark_measurements = []
        self.abort_reason = None
        if self.session_manager:
            self.session = self.session_manager.start("BREAKIN")
        try:
            while self.running and self.phase_manager.has_next():
                self.execute_phase(self.phase_manager.current_phase())
                self.phase_manager.next_phase()
            if self.abort_reason:
                raise RuntimeError(self.abort_reason)

            self.stop()
            self.running = True
            self._run_benchmark(self.BENCHMARK_DURATION_SEC)
            if self.abort_reason:
                raise RuntimeError(self.abort_reason)

            self.measurements = list(self.benchmark_measurements)
            result = self.analyze(self.measurements)
            if self.session_manager:
                self.session_manager.finish("COMPLETE")
            return result
        except Exception:
            if self.session_manager:
                self.session_manager.finish("ERROR")
            self.emergency_stop()
            raise

    def benchmark_3v(self, duration_sec=30.0):
        """Run only the 3 V / 30 s benchmark used for estimation."""
        self.running = True
        self.measurements = []
        self.benchmark_measurements = []
        self.abort_reason = None
        try:
            self._run_benchmark(float(duration_sec))
            if self.abort_reason:
                raise RuntimeError(self.abort_reason)
            self.measurements = list(self.benchmark_measurements)
            return self.analyze(self.measurements)
        except Exception:
            self.emergency_stop()
            raise

    def _run_benchmark(self, duration_sec):
        """Run a settled 3 V benchmark and retain benchmark samples only."""
        phase = BreakinPhase(
            name="BENCHMARK_3V_30S",
            duration_sec=float(duration_sec),
            pwm=80,
            direction="FWD",
            control="VOLTAGE",
            target_voltage=self.BENCHMARK_TARGET_VOLTAGE,
            pwm_min=35,
            pwm_max=120,
        )
        self.current_phase = phase
        self.abort_reason = None
        self.benchmark_measurements = []

        self.serial.forward()
        self.current_pwm = phase.pwm
        self.serial.set_pwm(self.current_pwm)

        # Allow a manually-started/stationary motor to begin rotating. These
        # samples are intentionally stored outside both analysis and the
        # operator-facing benchmark measurement list.
        settling_measurements = []
        settle_end = time.time() + self.BENCHMARK_SETTLE_SEC
        while self.running and time.time() < settle_end:
            measurement = self._collect_measurement(
                phase, target=settling_measurements
            )
            if phase.control == "VOLTAGE" and phase.target_voltage is not None:
                self._voltage_control(phase, measurement)
            safety = self._safety_violation(measurement)
            if safety:
                self.abort_reason = safety
                self.emergency_stop()
                return
            time.sleep(self.CONTROL_INTERVAL_SEC)

        # The actual estimation window begins only after settling. Samples
        # collected during break-in and the hand-spin/startup period are never
        # sent to analysis.
        self.benchmark_measurements.clear()
        start = time.time()
        while self.running and time.time() - start < duration_sec:
            measurement = self._collect_measurement(
                phase, target=self.benchmark_measurements
            )
            if phase.control == "VOLTAGE" and phase.target_voltage is not None:
                self._voltage_control(phase, measurement)
            safety = self._safety_violation(measurement)
            if safety:
                self.abort_reason = safety
                self.emergency_stop()
                return
            time.sleep(self.CONTROL_INTERVAL_SEC)

        self.serial.set_pwm(0)
        time.sleep(0.2)
        self.running = False

    def execute_phase(self, phase):
        self.current_phase = phase
        self.abort_reason = None
        if phase.direction == "REV":
            self.serial.reverse()
        else:
            self.serial.forward()
        if phase.control == "VOLTAGE" and phase.target_voltage is not None:
            initial = phase.pwm or int((phase.pwm_min + phase.pwm_max) / 2)
            self.current_pwm = max(phase.pwm_min, min(phase.pwm_max, initial))
        else:
            self.current_pwm = phase.pwm
        self.serial.set_pwm(self.current_pwm)

        measurement = self._collect_measurement(phase)
        safety = self._safety_violation(measurement)
        if safety:
            self.abort_reason = safety
            self.emergency_stop()
            return

        start = time.time()
        while self.running and time.time() - start < phase.duration_sec:
            measurement = self._collect_measurement(phase)
            if phase.control == "VOLTAGE" and phase.target_voltage is not None:
                self._voltage_control(phase, measurement)
            safety = self._safety_violation(measurement)
            if safety:
                self.abort_reason = safety
                self.emergency_stop()
                break
            time.sleep(self.CONTROL_INTERVAL_SEC)
        self.serial.set_pwm(0)
        time.sleep(0.2)

    @staticmethod
    def _value(measurement, name, default=0.0):
        if measurement is None:
            return default
        if isinstance(measurement, dict):
            return measurement.get(name, default)
        return getattr(measurement, name, default)

    def _voltage_control(self, phase, measurement):
        voltage = float(self._value(measurement, "motor_voltage", 0.0))
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
        temperature = float(self._value(measurement, "motor_temperature", 0.0))
        current = max(float(self._value(measurement, "current1", 0.0)),
                      float(self._value(measurement, "current2", 0.0)))
        if max_temp > 0 and temperature >= max_temp:
            return f"SAFETY: motor temperature {temperature:.1f}C >= {max_temp:.1f}C"
        if max_current > 0 and current >= max_current:
            return f"SAFETY: current {current:.2f}A >= {max_current:.2f}A"
        if self.current_pwm > max_pwm:
            return f"SAFETY: PWM {self.current_pwm} > {max_pwm}"
        return None

    def _collect_measurement(self, phase, target=None):
        if not self.measurement_manager:
            return None
        measurement = self.measurement_manager.collect()
        if isinstance(measurement, dict):
            measurement["phase"] = phase
            measurement["phase_pwm"] = self.current_pwm
            measurement["phase_direction"] = phase.direction
        destination = self.measurements if target is None else target
        destination.append(measurement)
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
