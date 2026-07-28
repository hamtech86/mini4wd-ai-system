"""
=====================================================
 MINI4WD AI SYSTEM
 MOTOR_BREAKIN_V3
 breakin_controller.py
=====================================================

Break-in Controller

UIと各Controllerを接続する。

UIはこのControllerのみを使用する。
"""

from __future__ import annotations

from measurement.measurement_session import MeasurementType

from controllers.session_controller import SessionController
from controllers.serial_controller import SerialController
from controllers.database_controller import DatabaseController


class BreakinController:
    """
    Break-in System Controller
    """

    def __init__(self):

        self.session = SessionController()

        self.serial = SerialController()

        self.database = DatabaseController()

        #
        # Measurement通知
        #

        self.serial.on_measurement = self._on_measurement

    # -------------------------------------------------
    # Connection
    # -------------------------------------------------

    def connect(
        self,
        port: str,
        baudrate: int = 57600,
    ):

        self.serial.connect(
            port,
            baudrate,
        )

    def disconnect(self):

        self.serial.disconnect()

    @property
    def is_connected(self):

        return self.serial.is_connected

    # -------------------------------------------------
    # Session
    # -------------------------------------------------

    def start_breakin(self):

        session = self.session.start(
            MeasurementType.BREAKIN
        )

        self.serial.start_session(
            MeasurementType.BREAKIN
        )

        return session

    def stop_breakin(self):

        self.session.finish()

        self.serial.finish_session()

    # -------------------------------------------------
    # Communication
    # -------------------------------------------------

    def update(self):

        return self.serial.update()

    # -------------------------------------------------
    # Arduino Command
    # -------------------------------------------------

    def send_command(self, command: str):

        self.serial.send(command)

    def set_pwm(self, pwm: int):

        self.send_command(f"PWM,{pwm}")

    def set_direction(self, direction: str):

        self.send_command(f"DIR,{direction}")

    def start_motor(self):

        self.send_command("START")

    def stop_motor(self):

        self.send_command("STOP")

    # -------------------------------------------------
    # Internal
    # -------------------------------------------------

    def _on_measurement(self, measurement):

        #
        # Database保存
        #

        self.database.save_measurement(
            measurement
        )

        #
        # 将来
        #
        # AnalysisController
        # UI通知
        # CSV Export
        #

