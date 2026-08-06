"""
Serial Controller Interface
MOTOR_BREAKIN_V3

Break-in Controller <-> Arduino communication layer.

Arduino firmware is treated as fixed.
This layer converts controller actions into existing
serial command format.
"""


class SerialController:

    def __init__(self, serial_port=None):
        self.serial_port = serial_port
        self.connected = False
        self.last_pwm = 0
        self.direction = "FWD"
        self.command_log = []

    def connect(self):
        self.connected = True

    def forward(self):
        self.direction = "FWD"
        self.send_command("DIR,FWD")

    def reverse(self):
        self.direction = "REV"
        self.send_command("DIR,REV")

    def set_pwm(self, pwm):
        self.last_pwm = max(0, min(255, int(pwm)))
        self.send_command(f"PWM,{self.last_pwm}")

    def stop_breakin(self):
        self.set_pwm(0)
        self.send_command("STOP")

    def emergency_stop(self):
        self.set_pwm(0)
        self.send_command("STOP")
        self.connected = False

    def send_command(self, command):
        """Send command to Arduino.

        Current implementation keeps a command log until
        the physical serial backend is enabled.
        """
        self.command_log.append(command)
        return command

    def read_measurement(self):
        """Return raw measurement frame from Arduino.

        Measurement parsing remains unchanged.
        """
        return None
