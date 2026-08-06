"""
Break-in Controller
MOTOR_BREAKIN_V3

Controller Pipeline
Recipe
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
    ):
        self.serial = serial_controller
        self.measurement_manager = measurement_manager
        self.analysis_engine = analysis_engine
        self.database = database
        self.running = False


    def start(self, recipe):
        self.phase_manager = PhaseManager(recipe)
        self.running = True

        measurements = []

        while self.running and self.phase_manager.has_next():
            phase = self.phase_manager.current_phase()

            self.execute_phase(phase)

            if self.measurement_manager:
                measurements.append(
                    self.measurement_manager.collect()
                )

            self.phase_manager.next_phase()

        self.stop()

        return self.analyze(measurements)


    def execute_phase(self, phase):

        if phase.direction == "REV":
            self.serial.reverse()
        else:
            self.serial.forward()

        self.serial.set_pwm(phase.pwm)

        start = time.time()

        while self.running and time.time() - start < phase.duration_sec:
            time.sleep(0.1)


    def analyze(self, measurements):

        if self.analysis_engine is None:
            return measurements

        results = []

        for measurement in measurements:
            results.append(
                self.analysis_engine.analyze(measurement)
            )

        return results


    def stop(self):
        self.running = False

        if hasattr(self.serial, "stop_breakin"):
            self.serial.stop_breakin()

        self.serial.set_pwm(0)


    def emergency_stop(self):
        self.stop()

        if hasattr(self.serial, "emergency_stop"):
            self.serial.emergency_stop()
