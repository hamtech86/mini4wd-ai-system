"""
MOTOR_BREAKIN_V3
Break-in Controller

実機ブレイクイン制御フロー管理
"""

from enum import Enum, auto

from measurement.measurement_session import MeasurementType
from controlles.session_controller import SessionController
from controlles.serial_controller import SerialController
from controlles.database_controller import DatabaseController
from controlles.phase_manager import PhaseManager, BreakinPhase
from controlles.recipe_manager import RecipeManager
from controlles.command_sender import CommandSender


class BreakinState(Enum):
    IDLE = auto()
    READY = auto()
    RUNNING = auto()
    PAUSED = auto()
    COMPLETE = auto()
    ERROR = auto()


class BreakinController:
    """Break-in process controller"""

    def __init__(self):
        self.session = SessionController()
        self.serial = SerialController()
        self.database = DatabaseController()

        self.phase = PhaseManager()
        self.recipe = RecipeManager()
        self.command = CommandSender(self.serial)

        self.state = BreakinState.IDLE
        self.measurements = []
        self.on_measurement = None
        self.on_state_changed = None

        self.serial.on_measurement = self.receive_measurement

    def _set_state(self, state):
        self.state = state
        if self.on_state_changed:
            self.on_state_changed(state)

    def initialize(self):
        self._set_state(BreakinState.IDLE)

    def connect_device(self, port="/dev/ttyACM0", baudrate=57600):
        self._set_state(BreakinState.READY)
        return self.serial.connect(port, baudrate)

    def disconnect_device(self):
        return self.serial.disconnect()

    def start_breakin(self, profile=None):
        self.session.start(MeasurementType.BREAKIN)
        self.phase.set_phase(BreakinPhase.BREAKIN)
        self.command.start()
        self._set_state(BreakinState.RUNNING)

    def pause(self):
        self.command.send("PAUSE")
        self._set_state(BreakinState.PAUSED)

    def resume(self):
        self.command.send("RESUME")
        self._set_state(BreakinState.RUNNING)

    def stop_breakin(self):
        self.command.stop()
        self.session.finish()
        self._set_state(BreakinState.COMPLETE)

    def receive_measurement(self, data):
        self.measurements.append(data)
        self.database.save_measurement(data)
        if self.on_measurement:
            self.on_measurement(data)

    def run_analysis(self):
        return None

    def save_session(self):
        return self.session.session

    def shutdown(self):
        self.stop_breakin()
        self.disconnect_device()
