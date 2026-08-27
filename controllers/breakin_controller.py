"""Break-in Controller - MOTOR_BREAKIN_V3.

Recipe -> Phase Control -> Arduino -> Measurement -> Analysis.

The controller also owns a small, restart-safe recipe checkpoint so a long
recipe can resume from the interrupted phase instead of restarting at phase 1.
"""

import json
import time
from pathlib import Path

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
    CHECKPOINT_PATH = Path("data/breakin_resume.json")

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
        self.paused = False
        self.measurements = []
        self.session = None
        self.current_phase = None
        self.current_pwm = 0
        self.abort_reason = None
        self.phase_started_at = None
        self.phase_elapsed_before_pause = 0.0
        self.pause_started_at = None
        self.current_phase_index = 0
        self.total_phases = 0
        self.selected_instance_id = None
        self.active_instance_id = None
        self.active_recipe_name = None
        self.last_brush_peak_current = 0.0
        self.brush_peak_target_current = 0.0
        self.brush_peak_reached = False

    # ------------------------- checkpoint / resume -------------------------
    def _save_checkpoint(self):
        if not self.current_phase or not self.active_recipe_name:
            return
        self.CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "recipe": self.active_recipe_name,
            "instance_id": self.active_instance_id,
            "phase_index": self.current_phase_index,
            "phase_name": self.current_phase.name,
            "phase_elapsed_sec": self.phase_elapsed_sec(),
            "current_pwm": self.current_pwm,
            "direction": self.current_phase.direction,
            "paused": self.paused,
            "updated_at": time.time(),
        }
        tmp = self.CHECKPOINT_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.CHECKPOINT_PATH)

    def resume_checkpoint(self):
        if not self.CHECKPOINT_PATH.exists():
            return None
        try:
            return json.loads(self.CHECKPOINT_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return None

    def clear_checkpoint(self):
        try:
            self.CHECKPOINT_PATH.unlink(missing_ok=True)
        except OSError:
            pass

    def pause(self):
        if not self.running or self.paused:
            return False
        self.phase_elapsed_before_pause = self.phase_elapsed_sec()
        self.paused = True
        self.pause_started_at = time.time()
        self.serial.set_pwm(0)
        self._save_checkpoint()
        return True

    def resume(self):
        if not self.running or not self.paused:
            return False
        self.paused = False
        self.phase_started_at = time.time()
        self.pause_started_at = None
        if self.current_phase.direction == "REV":
            self.serial.reverse()
        else:
            self.serial.forward()
        self.serial.set_pwm(self.current_pwm)
        self._save_checkpoint()
        return True

    def resume_from_checkpoint(self, recipe, instance_id=None):
        checkpoint = self.resume_checkpoint()
        if not checkpoint:
            raise RuntimeError("No resumable break-in checkpoint")
        recipe_name = str(getattr(recipe, "name", "")).upper()
        checkpoint_name = str(checkpoint.get("recipe", "")).upper()
        if recipe_name != checkpoint_name:
            raise RuntimeError("Resume rejected: recipe mismatch")
        expected_instance = checkpoint.get("instance_id")
        actual_instance = instance_id if instance_id is not None else self.selected_instance_id
        if expected_instance != actual_instance:
            raise RuntimeError("Resume rejected: motor instance mismatch")
        return self.start(recipe, instance_id=actual_instance, resume=True)

    def start(self, recipe, instance_id=None, resume=False):
        instance_id = instance_id if instance_id is not None else self.selected_instance_id
        self.active_instance_id = instance_id
        self.active_recipe_name = str(recipe.name).upper()
        self.phase_manager = PhaseManager(recipe)
        self.running = True
        self.paused = False
        self.measurements = []
        self.abort_reason = None
        self.current_phase = None
        self.current_phase_index = 0
        self.total_phases = len(recipe.phases)
        self.phase_started_at = None
        self.phase_elapsed_before_pause = 0.0
        self.last_brush_peak_current = 0.0
        self.brush_peak_target_current = 0.0
        self.brush_peak_reached = False

        checkpoint = self.resume_checkpoint() if resume else None
        if checkpoint:
            index = int(checkpoint.get("phase_index", 0))
            if index < 0 or index >= self.total_phases:
                raise RuntimeError("Resume rejected: invalid phase index")
            self.phase_manager.set_index(index)
            self.current_phase_index = index

        if self.session_manager:
            try:
                self.session = self.session_manager.start("BREAKIN", instance_id=instance_id)
            except TypeError:
                self.session = self.session_manager.start("BREAKIN")
        try:
            while self.running and self.phase_manager.has_next():
                self.execute_phase(
                    self.phase_manager.current_phase(),
                    resume_elapsed=(float(checkpoint.get("phase_elapsed_sec", 0.0)) if checkpoint else 0.0),
                )
                checkpoint = None
                if not self.running:
                    break
                self.clear_checkpoint()
                self.phase_manager.next_phase()
                self.current_phase_index = self.phase_manager.current_index()
            if self.abort_reason:
                raise RuntimeError(self.abort_reason)
            if self.running:
                self.stop()
                self.clear_checkpoint()
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
        phase = BreakinPhase(
            name="BENCHMARK_3V_TEST", duration_sec=float(duration_sec), pwm=80,
            direction="FWD", control="VOLTAGE", target_voltage=3.00,
            pwm_min=35, pwm_max=120,
        )
        recipe = BreakinRecipe(
            name="MOTOR_BENCHMARK_TEST", description="Standalone 3 V motor benchmark test",
            brush="UNKNOWN", family="BENCHMARK", objective="MEASUREMENT", phases=[phase],
            target_rpm=None, torque_priority=0.50, version="2.1",
        )
        return self.start(recipe, instance_id=instance_id)

    def execute_phase(self, phase, resume_elapsed=0.0):
        self.current_phase = phase
        self.current_phase_index = self.phase_manager.current_index()
        self.abort_reason = None
        self.phase_elapsed_before_pause = max(0.0, float(resume_elapsed or 0.0))
        self.phase_started_at = time.time()
        if phase.direction == "REV":
            self.serial.reverse()
        else:
            self.serial.forward()
        self.current_pwm = max(phase.pwm_min, min(phase.pwm_max, phase.pwm))
        if phase.control in ("VOLTAGE", "VOLTAGE_RAMP", "BRUSH_PEAK_APPROACH"):
            target = phase.start_voltage if phase.control == "VOLTAGE_RAMP" else phase.target_voltage
            self.current_pwm = self._initial_pwm_for_voltage(target or 0.0, phase)
        if resume_elapsed > 0:
            checkpoint = self.resume_checkpoint() or {}
            self.current_pwm = int(checkpoint.get("current_pwm", self.current_pwm))
        self.serial.set_pwm(self.current_pwm)

        measurement = self._collect_measurement(phase)
        safety = self._safety_violation(measurement)
        if safety:
            self.abort_reason = safety
            self.emergency_stop()
            return
        if phase.control == "BRUSH_PEAK_APPROACH":
            self._execute_brush_peak_approach(phase, resume_elapsed)
        else:
            self._execute_standard_phase(phase, resume_elapsed)
        self.serial.set_pwm(0)
        time.sleep(0.2)

    def _effective_elapsed(self):
        return self.phase_elapsed_before_pause + self.phase_elapsed_sec()

    def _execute_standard_phase(self, phase, resume_elapsed=0.0):
        while self.running and self._effective_elapsed() < phase.duration_sec:
            if self.paused:
                time.sleep(self.CONTROL_INTERVAL_SEC)
                continue
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
            self._save_checkpoint()
            time.sleep(self.CONTROL_INTERVAL_SEC)

    def _execute_brush_peak_approach(self, phase, resume_elapsed=0.0):
        peak = self._estimate_brush_peak_current()
        if peak < phase.peak_min_current:
            self.abort_reason = f"BRUSH PEAK APPROACH requires benchmark peak >= {phase.peak_min_current:.3f} A; measured {peak:.3f} A"
            self.emergency_stop()
            return
        target = peak * (1.0 - phase.peak_margin_ratio)
        self.brush_peak_target_current = target
        max_duration = phase.max_duration_sec or phase.duration_sec or 1800
        while self.running and self._effective_elapsed() < max_duration:
            if self.paused:
                time.sleep(self.CONTROL_INTERVAL_SEC)
                continue
            measurement = self._collect_measurement(phase)
            current = self._current_from_measurement(measurement)
            if current > self.last_brush_peak_current:
                self.last_brush_peak_current = current
            if current >= target:
                self.brush_peak_reached = True
                self.serial.set_pwm(0)
                self.clear_checkpoint()
                return
            self._voltage_control(phase, measurement)
            safety = self._safety_violation(measurement)
            if safety:
                self.abort_reason = safety
                self.emergency_stop()
                return
            self._save_checkpoint()
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
        return max(phase.pwm_min, min(phase.pwm_max, int(round((target_voltage / 9.0) * 180.0))))

    def _voltage_ramp_control(self, phase):
        elapsed = self._effective_elapsed()
        duration = max(phase.duration_sec, 0.001)
        ratio = max(0.0, min(1.0, elapsed / duration))
        start = phase.start_voltage if phase.start_voltage is not None else 0.0
        end = phase.end_voltage if phase.end_voltage is not None else 0.0
        target = start + (end - start) * ratio
        error_target = BreakinPhase(name=phase.name, duration_sec=phase.duration_sec,
            pwm=self.current_pwm, direction=phase.direction, control="VOLTAGE",
            target_voltage=target, pwm_min=phase.pwm_min, pwm_max=phase.pwm_max)
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
        new_pwm = max(phase.pwm_min, min(phase.pwm_max, self.current_pwm + int(round(self.VOLTAGE_KP * error))))
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

    def _get_active_motor_model(self):
        """Return the master Motor Model for the selected Motor Instance."""
        if self.database is None or self.active_instance_id is None:
            return None
        try:
            from database.repository.motor_instance_repository import MotorInstanceRepository
            from database.repository.motor_repository import MotorRepository
            instance = MotorInstanceRepository(self.database).get_by_id(self.active_instance_id)
            if not instance:
                return None
            model_id = instance.get("motor_model_id")
            if model_id is None:
                return None
            return MotorRepository(self.database).get_by_id(model_id)
        except Exception:
            return None

    def analyze(self, measurements):
        if self.analysis_engine is None:
            return measurements
        motor_model = self._get_active_motor_model()
        return [
            self.analysis_engine.analyze(measurement, motor_model=motor_model)
            for measurement in measurements
        ]

    def stop(self):
        self.running = False
        self.paused = False
        if hasattr(self.serial, "stop_breakin"):
            self.serial.stop_breakin()
        self.serial.set_pwm(0)

    def emergency_stop(self):
        self.running = False
        self.paused = False
        self._save_checkpoint()
        if hasattr(self.serial, "emergency_stop"):
            self.serial.emergency_stop()
        else:
            self.stop()
