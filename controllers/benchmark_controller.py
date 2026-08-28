"""Benchmark-aware Break-in Controller.

The common motor benchmark does not start its official measurement window at
button press time. It first waits for a measurable, stable operating point.
Stabilization samples are deliberately discarded from the official benchmark
sample set and therefore cannot contaminate AI-analysis RAW LOG.
"""

import time

from .breakin_controller import BreakinController


class BenchmarkBreakinController(BreakinController):
    """BreakinController with condition-based benchmark start detection."""

    BENCHMARK_TARGET_VOLTAGE = 3.00
    BENCHMARK_START_VOLTAGE = 1.50
    BENCHMARK_MIN_CURRENT = 0.05
    BENCHMARK_STABLE_WINDOW_SEC = 0.50
    BENCHMARK_MAX_VOLTAGE_SPREAD = 0.10
    BENCHMARK_MAX_PWM_SPREAD = 5
    BENCHMARK_START_TIMEOUT_SEC = 15.0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.benchmark_state = "IDLE"
        self.benchmark_started_at = None
        self.benchmark_start_reason = None

    def benchmark_3v(self, duration_sec=30, instance_id=None):
        """Run the common 3 V benchmark using a condition-based start."""
        return super().benchmark_3v(duration_sec=duration_sec, instance_id=instance_id)

    def execute_phase(self, phase, resume_elapsed=0.0):
        if phase.name != "BENCHMARK_3V_TEST" or resume_elapsed > 0:
            return super().execute_phase(phase, resume_elapsed=resume_elapsed)

        self.benchmark_state = "STABILIZING"
        self.benchmark_started_at = None
        self.benchmark_start_reason = None
        self._stabilize_benchmark(phase)
        if not self.running:
            return

        # Only measurements collected after the start condition belong to the
        # official benchmark. Stabilization samples are intentionally removed.
        self.measurements = []
        self.benchmark_state = "BENCHMARK_RUNNING"
        self.benchmark_started_at = time.time()
        self.benchmark_start_reason = (
            "motor voltage >= 1.50 V, measurable current >= 0.05 A, "
            "and stable voltage/PWM for 0.5 s"
        )
        super().execute_phase(phase, resume_elapsed=0.0)
        if self.abort_reason:
            self.benchmark_state = "ERROR"
        else:
            self.benchmark_state = "COMPLETE"

    def _stabilize_benchmark(self, phase):
        started = time.monotonic()
        stable_samples = []
        self.current_phase = phase
        self.current_phase_index = phase_index = self.phase_manager.current_index()
        self.phase_elapsed_before_pause = 0.0
        self.phase_started_at = time.time()
        self.serial.forward()
        self.current_pwm = self._initial_pwm_for_voltage(self.BENCHMARK_TARGET_VOLTAGE, phase)
        self.serial.set_pwm(self.current_pwm)

        while self.running:
            if time.monotonic() - started >= self.BENCHMARK_START_TIMEOUT_SEC:
                self.abort_reason = (
                    "BENCHMARK START TIMEOUT: measurable stable motor operation "
                    "was not detected within 15 seconds"
                )
                self.emergency_stop()
                self.benchmark_state = "TIMEOUT"
                return

            measurement = self._collect_measurement(phase)
            if measurement is None:
                time.sleep(self.CONTROL_INTERVAL_SEC)
                continue

            safety = self._safety_violation(measurement)
            if safety:
                self.abort_reason = safety
                self.emergency_stop()
                self.benchmark_state = "ERROR"
                return

            if self._stable_sample_ok(measurement, phase):
                stable_samples.append((time.monotonic(), measurement))
                cutoff = stable_samples[-1][0] - self.BENCHMARK_STABLE_WINDOW_SEC
                stable_samples = [item for item in stable_samples if item[0] >= cutoff]
                if (
                    stable_samples
                    and stable_samples[-1][0] - stable_samples[0][0]
                    >= self.BENCHMARK_STABLE_WINDOW_SEC
                    and self._stable_window_ok(stable_samples)
                ):
                    return
            else:
                stable_samples = []

            if phase.control == "VOLTAGE" and phase.target_voltage is not None:
                self._voltage_control(phase, measurement)
            time.sleep(self.CONTROL_INTERVAL_SEC)

    def _stable_sample_ok(self, measurement, phase):
        voltage = float(self._value(measurement, "motor_voltage", 0.0) or 0.0)
        current = self._current_from_measurement(measurement)
        return (
            voltage >= self.BENCHMARK_START_VOLTAGE
            and current >= self.BENCHMARK_MIN_CURRENT
            and self.current_pwm >= phase.pwm_min
        )

    def _stable_window_ok(self, samples):
        measurements = [measurement for _, measurement in samples]
        voltages = [
            float(self._value(m, "motor_voltage", 0.0) or 0.0)
            for m in measurements
        ]
        pwms = [
            int(self._value(m, "pwm", self.current_pwm) or self.current_pwm)
            for m in measurements
        ]
        return (
            max(voltages) - min(voltages) <= self.BENCHMARK_MAX_VOLTAGE_SPREAD
            and max(pwms) - min(pwms) <= self.BENCHMARK_MAX_PWM_SPREAD
        )
