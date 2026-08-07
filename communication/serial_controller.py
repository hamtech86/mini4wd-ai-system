"""
Serial Controller Interface
MOTOR_BREAKIN_V3

Break-in Controller <-> Arduino communication layer.

Arduino firmware is treated as fixed.
This layer converts controller actions into existing
serial command format.
"""

try:
    import serial
except ImportError:
    serial = None


class SerialController:

    def __init__(self, serial_port="/dev/ttyACM0", baudrate=57600):
        self.serial_port = serial_port
        self.baudrate = baudrate
        self.serial = None
        self.connected = False
        self.last_pwm = 0
        self.direction = "FWD"
        self.command_log = []

    def connect(self):
        if serial is None:
            return False

        try:
            self.serial = serial.Serial(
                self.serial_port,
                self.baudrate,
                timeout=1
            )
            self.connected = True
            print("SERIAL CONNECTED", self.serial_port, self.baudrate)
            return True
        except Exception as e:
            print("SERIAL CONNECT ERROR", e)
            self.connected = False
            return False

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
        self.disconnect()

    def disconnect(self):
        if self.serial:
            self.serial.close()
        self.serial = None
        self.connected = False

    def send_command(self, command):
        self.command_log.append(command)
        print("SERIAL TX:", command)

        if self.connected and self.serial:
            self.serial.write((command + "\n").encode("utf-8"))

        return command

    def read_measurement(self):
        """Return raw measurement frame from Arduino."""
        if self.connected and self.serial and self.serial.in_waiting:
            raw = self.serial.readline()
            decoded = raw.decode("utf-8", errors="replace").strip()
            print("SERIAL RX:", decoded)
            return decoded

        return None
