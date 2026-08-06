"""
Break-in Controller
MOTOR_BREAKIN_V3

Controller Pipeline
Recipe
 -> Session
 -> Phase Control
 -> Arduino Control
 -> Measurement Collection
 -> Analysis Engine
 -> Result
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
    ):
        self.serial = serial_controller
        self.measurement_manager = measurement_manager
        self.analysis_engine = analysis_engine
        self.database = database
        self.session_manager = session_manager
        self.running = False
        self.measurements = []
        self.session = None


    def start(self, recipe):
        self.phase_manager = PhaseManager(recipe)
        self.running = True
        self.measurements = []

        if self.session_manager:
            self.session = self.session_manager.start("BREAKIN")

        try:
            while self.running and self.phase_manager.has_next():
                phase = self.phase_manager.current_phase()
                self.execute_phase(phase)
                self.phase_manager.next_phase()

            result = self.analyze(self.measurements)

            if self.session_manager:
                self.session_manager.finish("COMPLETE")

            return result

        except Exception:
            if self.session_manager:
                self.session_manager.finish("ERROR")
            self.emergency_stop()
            raise


    def execute_phase(self, phase):

        if phase.direction == "REV":
            self.serial.reverse()
        else:
            self.serial.forward()

        self.serial.set_pwm(phase.pwm)

        start = time.time()

        while self.running and time.time() - start < phase.duration_sec:

            if self.measurement_manager:
                measurement = self.measurement_manager.collect()
                self.measurements.append(measurement)

            time.sleep(0.1)


    def analyze(self, measurements):

        if self.analysis_engine is None:
            return measurements

        return [
            self.analysis_engine.analyze(measurement)
            for measurement in measurements
        ]


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
