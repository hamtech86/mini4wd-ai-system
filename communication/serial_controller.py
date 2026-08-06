"""
Serial Controller Interface
MOTOR_BREAKIN_V3

Break-in Controller <-> Arduino communication layer.

This module provides the hardware abstraction used by
controllers.breakin_controller.
"""


class SerialController:

    def __init__(self, serial_port=None):
        self.serial_port = serial_port
        self.connected = False
        self.last_pwm = 0
        self.direction = "FWD"

    def connect(self):
        self.connected = True

    def forward(self):
        self.direction = "FWD"

    def reverse(self):
        self.direction = "REV"

    def set_pwm(self, pwm):
        self.last_pwm = max(0, min(255, int(pwm)))

    def stop_breakin(self):
        self.set_pwm(0)

    def emergency_stop(self):
        self.set_pwm(0)
        self.connected = False

    def send_command(self, command):
        """Hardware-specific serial transmission placeholder."""
        return command

    def read_measurement(self):
        """Return raw measurement frame from Arduino.

        Actual serial parsing is implemented when Arduino protocol
        is connected.
        """
        return None
