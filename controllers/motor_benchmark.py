"""Approved motor benchmark acquisition procedures.

This module adds benchmark execution without changing analysis/evaluation logic.
"""
from __future__ import annotations

import time
from .recipe import BreakinPhase
from .breakin_controller import BreakinController

STANDARD = "STANDARD"
FULL_PACKAGE_TYPE = "FULL_PACKAGE"
TERMINAL = "TERMINAL"
INPUT = "INPUT"

# Legacy public benchmark identifiers are retained for compatibility.
STANDARD_3V30S = "STANDARD_3V30S"
FULL_PACKAGE = "FULL_PACKAGE"

STD_T = "STD-T"
FULL_T = "Full-T"
STD_I = "STD-I"
FULL_I = "Full-I"

BENCHMARK_RECIPES = {
    STD_T: (STANDARD, TERMINAL),
    FULL_T: (FULL_PACKAGE_TYPE, TERMINAL),
    STD_I: (STANDARD, INPUT),
    FULL_I: (FULL_PACKAGE_TYPE, INPUT),
}

_LEGACY_RECIPE_ALIASES = {
    STANDARD_3V30S: STD_T,
    FULL_PACKAGE: FULL_T,
}

def benchmark_recipe_names():
    return (STD_T, FULL_T, STD_I, FULL_I)

def benchmark_recipe_spec(recipe_name):
    key = str(recipe_name).strip()
    canonical = _LEGACY_RECIPE_ALIASES.get(key, key)
    canonical_upper = canonical.upper()
    for name, spec in BENCHMARK_RECIPES.items():
        if name.upper() == canonical_upper:
            return name, spec[0], spec[1]
    raise ValueError(f"Unsupported benchmark recipe: {recipe_name}")

def _canonical_recipe_for(benchmark_type, voltage_control_mode):
    benchmark_type = str(benchmark_type).upper()
    voltage_control_mode = str(voltage_control_mode).upper()
    for name, (btype, mode) in BENCHMARK_RECIPES.items():
        if btype == benchmark_type and mode == voltage_control_mode:
            return name
    raise ValueError(
        f"Unsupported benchmark combination: "
        f"{benchmark_type} + {voltage_control_mode}"
    )


def _collect(self, phase):
    return self._collect_measurement(phase)


def _safety(self, measurement):
    violation = self._safety_violation(measurement)
    if violation:
        self.abort_reason = violation
        self.emergency_stop()
        return True
    return False


def _prepare_3v(self, phase, duration=2.0):
    """Run fixed preparation time while controlling toward 3.00 V.

    Preparation is procedural only. Measured voltage is observed and logged,
    but it is never used as a start gate, pass/fail condition, or abort rule.
    """
    self.phase_started_at = time.time()
    self.phase_elapsed_before_pause = 0.0
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


def _timed_voltage(self, phase, duration):
    self.phase_started_at = time.time()
    self.phase_elapsed_before_pause = 0.0
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
    self.phase_started_at = time.time()
    self.phase_elapsed_before_pause = 0.0
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

def _begin(
    self,
    benchmark_type,
    voltage_control_mode=TERMINAL,
    recipe_name=None,
    instance_id=None,
    purpose="MEASUREMENT",
):
    # A benchmark can be executed repeatedly on the same controller instance.
    # Reset Local Raw Log persistence state at the benchmark boundary so the
    # previous benchmark's log cannot suppress registration of this benchmark.
    if hasattr(self, "_measurement_raw_log_parts"):
        self._measurement_raw_log_parts = []
    if hasattr(self, "_registered_raw_log_ids"):
        self._registered_raw_log_ids = []
    if hasattr(self, "last_raw_log_id"):
        self.last_raw_log_id = None
    if hasattr(self, "last_raw_log_path"):
        self.last_raw_log_path = None

    if hasattr(self.serial, "reset_raw_log"):
        self.serial.reset_raw_log()
    self.active_instance_id = instance_id if instance_id is not None else self.selected_instance_id
    legacy_recipe = _LEGACY_RECIPE_ALIASES.get(str(benchmark_type).strip())
    if legacy_recipe:
        recipe_name, benchmark_type, legacy_mode = benchmark_recipe_spec(legacy_recipe)
        voltage_control_mode = legacy_mode
    elif recipe_name is None:
        recipe_name = _canonical_recipe_for(benchmark_type, voltage_control_mode)
    self.active_recipe_name = recipe_name
    self.running = True
    self.paused = False
    self.measurements = []
    self.abort_reason = None
    self.current_phase = None
    self.current_phase_index = 0
    self.total_phases = 2 if benchmark_type == STANDARD_3V30S else 6
    self.phase_started_at = None
    self.current_pwm = 0
    self.benchmark_type = str(benchmark_type).upper()
    self.voltage_control_mode = str(voltage_control_mode).upper()
    if self.voltage_control_mode not in (TERMINAL, INPUT):
        raise ValueError(f"Unsupported voltage control mode: {self.voltage_control_mode}")
    self.benchmark_purpose = purpose
    self.benchmark_baseline_pwm = None
    self.session = None
    if self.session_manager:
        try:
            self.session = self.session_manager.start("BREAKIN", instance_id=self.active_instance_id)
        except TypeError:
            self.session = self.session_manager.start("BREAKIN")
    if self.session is not None:
        self.session.benchmark_type = benchmark_type
        self.session.purpose = purpose
        self.session.notes = (
            f"benchmark_type={self.benchmark_type}; "
            f"voltage_control_mode={self.voltage_control_mode}; "
            f"recipe={self.active_recipe_name}; purpose={purpose}"
        )
    if self.measurement_manager is not None:
        self.measurement_manager.session = self.session
        if self.session is not None:
            self.measurement_manager.logger.start(self.session.session_id)
            self.measurement_manager.filters.reset()


def run_benchmark(
    self,
    benchmark_type=STANDARD,
    instance_id=None,
    purpose="MEASUREMENT",
    voltage_control_mode=TERMINAL,
    recipe_name=None,
):
    # Accept either the two-axis representation or one of the four canonical
    # recipe identifiers. Legacy STANDARD_3V30S/FULL_PACKAGE remain terminal.
    if recipe_name is not None:
        recipe_name, benchmark_type, voltage_control_mode = benchmark_recipe_spec(recipe_name)
    else:
        candidate = str(benchmark_type).strip()
        if candidate.upper() in {name.upper() for name in benchmark_recipe_names()} or candidate in _LEGACY_RECIPE_ALIASES:
            recipe_name, benchmark_type, voltage_control_mode = benchmark_recipe_spec(candidate)
        else:
            benchmark_type = str(benchmark_type).upper()
            voltage_control_mode = str(voltage_control_mode).upper()
            recipe_name = _canonical_recipe_for(benchmark_type, voltage_control_mode)
    if benchmark_type not in (STANDARD, FULL_PACKAGE_TYPE):
        raise ValueError(f"Unsupported benchmark type: {benchmark_type}")
    if voltage_control_mode not in (TERMINAL, INPUT):
        raise ValueError(f"Unsupported voltage control mode: {voltage_control_mode}")

    _begin(
        self,
        benchmark_type,
        voltage_control_mode=voltage_control_mode,
        recipe_name=recipe_name,
        instance_id=instance_id,
        purpose=purpose,
    )

    prepare_phase = BreakinPhase(
        "PREPARE_2S", 2, 0, "FWD", "VOLTAGE", 3.00, pwm_min=35, pwm_max=120
    )
    prepare_phase.metadata.update({
        "benchmark_type": self.benchmark_type,
        "voltage_control_mode": self.voltage_control_mode,
        "recipe": self.active_recipe_name,
    })
    self.current_phase = prepare_phase
    self.current_phase_index = 0
    self.current_pwm = self._initial_pwm_for_voltage(3.00, prepare_phase)
    self.serial.forward()
    self.serial.set_pwm(self.current_pwm)

    try:
        # Fixed procedural preparation interval. There is deliberately no
        # measured-voltage stability gate.
        if not _prepare_3v(self, prepare_phase, 2.0):
            raise RuntimeError(self.abort_reason or "Benchmark stopped during preparation")

        self.benchmark_baseline_pwm = int(self.current_pwm)

        baseline = BreakinPhase(
            "BASELINE_3V_30S", 30, self.current_pwm, "FWD", "VOLTAGE",
            3.00, pwm_min=35, pwm_max=120
        )
        baseline.metadata.update({
            "benchmark_type": self.benchmark_type,
            "voltage_control_mode": self.voltage_control_mode,
            "recipe": self.active_recipe_name,
        })
        self.current_phase = baseline
        self.current_phase_index = 1
        if not _timed_voltage(self, baseline, 30.0):
            raise RuntimeError(self.abort_reason or "Benchmark stopped")

        if benchmark_type == STANDARD_3V30S:
            self._finish_benchmark([prepare_phase, baseline])
            return self.measurements

        plus = max(0, min(255, int(round(self.benchmark_baseline_pwm * 1.05))))
        plus_phase = BreakinPhase(
            "PWM_PLUS_5_30S", 30, plus, "FWD", "PWM", pwm_min=0, pwm_max=255
        )
        plus_phase.metadata.update({
            "benchmark_type": self.benchmark_type,
            "voltage_control_mode": self.voltage_control_mode,
            "recipe": self.active_recipe_name,
        })
        self.current_phase = plus_phase
        self.current_phase_index = 2
        self.current_pwm = plus
        self.serial.set_pwm(plus)
        if not _timed_pwm(self, plus_phase, 30.0):
            raise RuntimeError(self.abort_reason or "Benchmark stopped")

        return_phase_1 = BreakinPhase(
            "RETURN_3V_10S_1", 10, self.current_pwm, "FWD", "VOLTAGE",
            3.00, pwm_min=35, pwm_max=120
        )
        return_phase_1.metadata.update({
            "benchmark_type": self.benchmark_type,
            "voltage_control_mode": self.voltage_control_mode,
            "recipe": self.active_recipe_name,
        })
        self.current_phase = return_phase_1
        self.current_phase_index = 3
        if not _timed_voltage(self, return_phase_1, 10.0):
            raise RuntimeError(self.abort_reason or "Benchmark stopped")

        minus = max(0, min(255, int(round(self.benchmark_baseline_pwm * 0.95))))
        minus_phase = BreakinPhase(
            "PWM_MINUS_5_30S", 30, minus, "FWD", "PWM", pwm_min=0, pwm_max=255
        )
        minus_phase.metadata.update({
            "benchmark_type": self.benchmark_type,
            "voltage_control_mode": self.voltage_control_mode,
            "recipe": self.active_recipe_name,
        })
        self.current_phase = minus_phase
        self.current_phase_index = 4
        self.current_pwm = minus
        self.serial.set_pwm(minus)
        if not _timed_pwm(self, minus_phase, 30.0):
            raise RuntimeError(self.abort_reason or "Benchmark stopped")

        return_phase_2 = BreakinPhase(
            "RETURN_3V_10S_2", 10, self.current_pwm, "FWD", "VOLTAGE",
            3.00, pwm_min=35, pwm_max=120
        )
        return_phase_2.metadata.update({
            "benchmark_type": self.benchmark_type,
            "voltage_control_mode": self.voltage_control_mode,
            "recipe": self.active_recipe_name,
        })
        self.current_phase = return_phase_2
        self.current_phase_index = 5
        if not _timed_voltage(self, return_phase_2, 10.0):
            raise RuntimeError(self.abort_reason or "Benchmark stopped")

        self._finish_benchmark([
            prepare_phase, baseline, plus_phase, return_phase_1,
            minus_phase, return_phase_2
        ])
        return self.measurements
    except Exception:
        if hasattr(self.serial, "stop_breakin"):
            self.serial.stop_breakin()
        else:
            self.serial.set_pwm(0)
        self.current_pwm = 0
        self.running = False
        if self.session is not None:
            if self.abort_reason:
                self.session.error()
            else:
                self.session.cancel()
        if self.measurement_manager is not None:
            self.measurement_manager.logger.stop()
        self._finalize_benchmark_raw_log()
        raise

def _finish_benchmark(self, phases):
    # Freeze exactly at the benchmark boundary. Serial data arriving after
    # this point (including STOP/finalization lag) is not part of the log.
    freeze = getattr(self, "_freeze_measurement_raw_log", None)
    if callable(freeze):
        freeze()
    if hasattr(self.serial, "stop_breakin"):
        self.serial.stop_breakin()
    else:
        self.serial.set_pwm(0)
    self.current_pwm = 0
    self.running = False
    phase_names = ",".join(phase.name for phase in phases)
    if self.session is not None:
        self.session.notes += f"; baseline_pwm={self.benchmark_baseline_pwm}; phases={phase_names}"
        self.session.finish()
    if self.measurement_manager is not None:
        self.measurement_manager.logger.stop()
    self._finalize_benchmark_raw_log()


def _finalize_benchmark_raw_log(self, raw_body=None):
    finalize = getattr(self, "finalize_benchmark_raw_log", None)
    if callable(finalize):
        try:
            finalize(raw_body)
        except Exception:
            # Persistence failure must not change the completed measurement
            # into a benchmark control failure.
            pass


def build_benchmark_recipe(recipe_name):
    """Build a declarative BreakinRecipe for one of the four benchmark recipes."""
    from .recipe import BreakinRecipe

    canonical, benchmark_type, voltage_control_mode = benchmark_recipe_spec(recipe_name)
    phases = [
        BreakinPhase(
            "PREPARE_2S", 2, 0, "FWD", "VOLTAGE", 3.00,
            pwm_min=35, pwm_max=120,
            metadata={
                "benchmark_type": benchmark_type,
                "voltage_control_mode": voltage_control_mode,
                "recipe": canonical,
            },
        ),
        BreakinPhase(
            "BASELINE_3V_30S", 30, 0, "FWD", "VOLTAGE", 3.00,
            pwm_min=35, pwm_max=120,
            metadata={
                "benchmark_type": benchmark_type,
                "voltage_control_mode": voltage_control_mode,
                "recipe": canonical,
            },
        ),
    ]
    if benchmark_type == FULL_PACKAGE_TYPE:
        phases.extend([
            BreakinPhase(
                "PWM_PLUS_5_30S", 30, 0, "FWD", "PWM",
                metadata={"benchmark_type": benchmark_type, "voltage_control_mode": voltage_control_mode, "recipe": canonical},
            ),
            BreakinPhase(
                "RETURN_3V_10S_1", 10, 0, "FWD", "VOLTAGE", 3.00,
                pwm_min=35, pwm_max=120,
                metadata={"benchmark_type": benchmark_type, "voltage_control_mode": voltage_control_mode, "recipe": canonical},
            ),
            BreakinPhase(
                "PWM_MINUS_5_30S", 30, 0, "FWD", "PWM",
                metadata={"benchmark_type": benchmark_type, "voltage_control_mode": voltage_control_mode, "recipe": canonical},
            ),
            BreakinPhase(
                "RETURN_3V_10S_2", 10, 0, "FWD", "VOLTAGE", 3.00,
                pwm_min=35, pwm_max=120,
                metadata={"benchmark_type": benchmark_type, "voltage_control_mode": voltage_control_mode, "recipe": canonical},
            ),
        ])
    return BreakinRecipe(
        name=canonical,
        phases=phases,
        description=f"Motor benchmark {canonical}",
        brush="UNKNOWN",
        family="BENCHMARK",
        objective="MEASUREMENT",
        benchmark=benchmark_type,
        benchmark_type=benchmark_type,
        voltage_control_mode=voltage_control_mode,
        version="3.0",
    )

def install_benchmark_support():
    def benchmark_3v(self, duration_sec=30, instance_id=None):
        selected = getattr(self, "selected_benchmark_recipe", None)
        if selected:
            return run_benchmark(self, recipe_name=selected, instance_id=instance_id)
        benchmark_type = getattr(self, "selected_benchmark_type", STANDARD_3V30S)
        return run_benchmark(self, benchmark_type, instance_id=instance_id)
    BreakinController.benchmark_3v = benchmark_3v
    BreakinController.run_benchmark = run_benchmark
    BreakinController._finish_benchmark = _finish_benchmark
    BreakinController._finalize_benchmark_raw_log = _finalize_benchmark_raw_log


install_benchmark_support()
