"""Approved motor benchmark acquisition procedures.

This module adds benchmark execution without changing analysis/evaluation logic.
"""
from __future__ import annotations

import time
from .recipe import BreakinPhase
from .breakin_controller import BreakinController

STANDARD_3V30S = "STANDARD_3V30S"
FULL_PACKAGE = "FULL_PACKAGE"


def _phase(name, duration, control="VOLTAGE", pwm=0, target=3.00):
    return BreakinPhase(
        name=name,
        duration_sec=duration,
        pwm=pwm,
        direction="FWD",
        control=control,
        target_voltage=target if control == "VOLTAGE" else None,
        pwm_min=35 if control == "VOLTAGE" else 0,
        pwm_max=120 if control == "VOLTAGE" else 255,
        metadata={"benchmark_type": getattr(_phase, "benchmark_type", "")},
    )


def _collect(self, phase):
    measurement = self._collect_measurement(phase)
    if measurement is not None and self.session is not None:
        self.session.add_measurement()
    return measurement


def _safety(self, measurement):
    violation = self._safety_violation(measurement)
    if violation:
        self.abort_reason = violation
        self.emergency_stop()
        return True
    return False


def _wait_for_stable_3v(self, phase, stable_sec=2.0):
    stable_since = None
    while self.running:
        if self.paused:
            time.sleep(self.CONTROL_INTERVAL_SEC)
            continue
        measurement = _collect(self, phase)
        if _safety(self, measurement):
            return False
        if measurement is not None:
            voltage = float(self._value(measurement, "motor_voltage", 0.0) or 0.0)
            self._voltage_control(phase, measurement)
            if 2.95 <= voltage <= 3.05:
                if stable_since is None:
                    stable_since = time.monotonic()
                elif time.monotonic() - stable_since >= stable_sec:
                    return True
            else:
                stable_since = None
        time.sleep(self.CONTROL_INTERVAL_SEC)
    return False


def _timed_voltage(self, phase, duration):
    started = time.monotonic()
    while self.running and time.monotonic() - started < duration:
        if self.paused:
            time.sleep(self.CONTROL_INTERVAL_SEC)
            continue
        measurement = _collect(self, phase)
        if _safety(self, measurement):
            return False
        self._voltage_control(phase, measurement)
        time.sleep(self.CONTROL_INTERVAL_SEC)
    return self.running


def _timed_pwm(self, phase, duration):
    started = time.monotonic()
    while self.running and time.monotonic() - started < duration:
        if self.paused:
            time.sleep(self.CONTROL_INTERVAL_SEC)
            continue
        measurement = _collect(self, phase)
        if _safety(self, measurement):
            return False
        time.sleep(self.CONTROL_INTERVAL_SEC)
    return self.running


def _begin(self, benchmark_type, instance_id=None, purpose="MEASUREMENT"):
    if hasattr(self.serial, "reset_raw_log"):
        self.serial.reset_raw_log()
    self.active_instance_id = instance_id if instance_id is not None else self.selected_instance_id
    self.active_recipe_name = benchmark_type
    self.running = True
    self.paused = False
    self.measurements = []
    self.abort_reason = None
    self.current_phase = None
    self.current_phase_index = 0
    self.total_phases = 1 if benchmark_type == STANDARD_3V30S else 5
    self.phase_started_at = None
    self.current_pwm = 0
    self.benchmark_type = benchmark_type
    self.benchmark_purpose = purpose
    self.benchmark_baseline_pwm = None
    self.benchmark_phase_log = []
    if self.session_manager:
        try:
            self.session = self.session_manager.start("BREAKIN", instance_id=self.active_instance_id)
        except TypeError:
            self.session = self.session_manager.start("BREAKIN")
        if self.session is not None:
            self.session.benchmark_type = benchmark_type
            self.session.purpose = purpose
            self.session.notes = f"benchmark_type={benchmark_type}; purpose={purpose}"


def run_benchmark(self, benchmark_type=STANDARD_3V30S, instance_id=None, purpose="MEASUREMENT"):
    if benchmark_type not in (STANDARD_3V30S, FULL_PACKAGE):
        raise ValueError(f"Unsupported benchmark type: {benchmark_type}")
    _begin(self, benchmark_type, instance_id, purpose)
    stable_phase = BreakinPhase("STABLE_3V_START", 0, 60, "FWD", "VOLTAGE", 3.00, pwm_min=35, pwm_max=120)
    self.current_phase = stable_phase
    self.current_phase_index = 0
    self.current_pwm = self._initial_pwm_for_voltage(3.00, stable_phase)
    self.serial.forward()
    self.serial.set_pwm(self.current_pwm)
    if not _wait_for_stable_3v(self, stable_phase, 2.0):
        if self.session_manager and self.session: self.session.error()
        self._finalize_benchmark_raw_log()
        if self.abort_reason: raise RuntimeError(self.abort_reason)
        raise RuntimeError("Benchmark stopped before 3.00 V stability was established")

    self.benchmark_baseline_pwm = int(self.current_pwm)
    stable_measure = BreakinPhase("STABLE_3V_30S", 30, self.current_pwm, "FWD", "VOLTAGE", 3.00, pwm_min=35, pwm_max=120)
    self.current_phase = stable_measure
    self.current_phase_index = 1
    if not _timed_voltage(self, stable_measure, 30.0):
        raise RuntimeError(self.abort_reason or "Benchmark stopped")

    if benchmark_type == STANDARD_3V30S:
        self._finish_benchmark()
        return self.measurements

    plus = max(0, min(255, int(round(self.benchmark_baseline_pwm * 1.05))))
    plus_phase = BreakinPhase("PWM_PLUS_5_30S", 30, plus, "FWD", "PWM", pwm_min=0, pwm_max=255)
    self.current_phase = plus_phase; self.current_phase_index = 2; self.current_pwm = plus
    self.serial.set_pwm(plus)
    if not _timed_pwm(self, plus_phase, 30.0): raise RuntimeError(self.abort_reason or "Benchmark stopped")

    return_phase_1 = BreakinPhase("RETURN_3V_BUFFER_10S_1", 10, self.current_pwm, "FWD", "VOLTAGE", 3.00, pwm_min=35, pwm_max=120)
    self.current_phase = return_phase_1; self.current_phase_index = 3
    if not _timed_voltage(self, return_phase_1, 10.0): raise RuntimeError(self.abort_reason or "Benchmark stopped")

    minus = max(0, min(255, int(round(self.benchmark_baseline_pwm * 0.95))))
    minus_phase = BreakinPhase("PWM_MINUS_5_30S", 30, minus, "FWD", "PWM", pwm_min=0, pwm_max=255)
    self.current_phase = minus_phase; self.current_phase_index = 4; self.current_pwm = minus
    self.serial.set_pwm(minus)
    if not _timed_pwm(self, minus_phase, 30.0): raise RuntimeError(self.abort_reason or "Benchmark stopped")

    return_phase_2 = BreakinPhase("RETURN_3V_BUFFER_10S_2", 10, self.current_pwm, "FWD", "VOLTAGE", 3.00, pwm_min=35, pwm_max=120)
    self.current_phase = return_phase_2; self.current_phase_index = 5
    if not _timed_voltage(self, return_phase_2, 10.0): raise RuntimeError(self.abort_reason or "Benchmark stopped")
    self._finish_benchmark()
    return self.measurements


def _finish_benchmark(self):
    self.serial.set_pwm(0)
    self.current_pwm = 0
    self.running = False
    if self.session_manager and self.session:
        self.session.notes += f"; baseline_pwm={self.benchmark_baseline_pwm}; phases=STABLE_3V_30S,PWM_PLUS_5_30S,RETURN_3V_BUFFER_10S_1,PWM_MINUS_5_30S,RETURN_3V_BUFFER_10S_2"
        self.session.finish()
    self._finalize_benchmark_raw_log()


def _finalize_benchmark_raw_log(self):
    if hasattr(self, "_register_raw_log"):
        try:
            self._register_raw_log()
        except Exception:
            pass


def install_benchmark_support():
    def benchmark_3v(self, duration_sec=30, instance_id=None):
        benchmark_type = getattr(self, "selected_benchmark_type", STANDARD_3V30S)
        if benchmark_type == FULL_PACKAGE:
            return run_benchmark(self, FULL_PACKAGE, instance_id=instance_id)
        return run_benchmark(self, STANDARD_3V30S, instance_id=instance_id)
    BreakinController.benchmark_3v = benchmark_3v
    BreakinController.run_benchmark = run_benchmark


install_benchmark_support()
