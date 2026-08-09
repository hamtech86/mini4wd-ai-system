"""
Break-in Controller
MOTOR_BREAKIN_V3
"""

import time

from .phase_manager import PhaseManager


class BreakinController:

    def __init__(
        self,
        serial_controller,
        measurement_manager=None,
        analysis_engine=None,
        database=None,
        session_manager=None,
        measurement_repository=None,
    ):
        self.serial = serial_controller
        self.measurement_manager = measurement_manager
        self.analysis_engine = analysis_engine
        self.database = database
        self.session_manager = session_manager
        self.measurement_repository = measurement_repository
        self.running = False
        self.measurements = []
        self.session = None
        self.current_phase = None
        self.instance_id = None

    def start(self, recipe, instance_id=None):
        """Run a break-in for the explicitly selected motor instance."""
        self.phase_manager = PhaseManager(recipe)
        self.running = True
        self.measurements = []
        self.instance_id = instance_id

        if self.session_manager:
            if instance_id is None:
                raise ValueError("instance_id is required to start a production break-in")
            self.session = self.session_manager.start("BREAKIN", instance_id=instance_id)

        try:
            while self.running and self.phase_manager.has_next():
                phase = self.phase_manager.current_phase()
                self.execute_phase(phase)
                self.phase_manager.next_phase()

            self.stop()
            result = self.analyze(self.measurements)

            if self.session_manager:
                self.session_manager.finish("COMPLETE")

            return result

        except Exception:
            if self.session_manager and self.session is not None:
                self.session_manager.finish("ERROR")
            self.emergency_stop()
            raise

    def execute_phase(self, phase):
        self.current_phase = phase

        if phase.direction == "REV":
            self.serial.reverse()
        else:
            self.serial.forward()

        self.serial.set_pwm(phase.pwm)
        self._collect_measurement(phase)

        start = time.time()

        while self.running and time.time() - start < phase.duration_sec:
            self._collect_measurement(phase)
            time.sleep(0.1)

        self.serial.set_pwm(0)
        time.sleep(0.2)

    def _collect_measurement(self, phase):
        if not self.measurement_manager:
            return

        measurement = self.measurement_manager.collect()

        if isinstance(measurement, dict):
            measurement["phase"] = phase
            measurement["phase_pwm"] = phase.pwm
            measurement["phase_direction"] = phase.direction

        if self.measurement_repository is not None and hasattr(measurement, "session_id"):
            session_id = getattr(self.session, "session_id", None)
            if session_id:
                measurement.session_id = session_id
            self.measurement_repository.insert(measurement)

        self.measurements.append(measurement)

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
