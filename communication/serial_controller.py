"""
Serial Controller Interface
MOTOR_BREAKIN_V3

Break-in Controller <-> Arduino communication layer.

Arduino firmware MOTOR_BREAKIN_V3.00 protocol:
  FWD
  REV
  PWM=<0..255>
  STOP
"""

try:
    import serial
except ImportError:
    serial = None

import time

from communication.raw_log_collector import RawLogCollector


class SerialController:

    def __init__(self, serial_port="/dev/ttyACM0", baudrate=57600):
        self.serial_port = serial_port
        self.baudrate = baudrate
        self.serial = None
        self.connected = False
        self.last_pwm = 0
        self.direction = "FWD"
        self.command_log = []
        self.last_raw_data = None
        self.raw_log_collector = RawLogCollector()

    @property
    def raw_log(self):
        """Exact raw serial text captured for the current measurement."""
        return self.raw_log_collector.snapshot()

    @property
    def has_raw_log(self):
        return self.raw_log_collector.has_data

    def reset_raw_log(self):
        """Start a new raw-log capture for the next measurement."""
        self.raw_log_collector.reset()

    def freeze_raw_log(self):
        """Return the current measurement capture and discard the live buffer."""
        snapshot = self.raw_log_collector.snapshot()
        self.raw_log_collector.reset()
        return snapshot

    def connect(self):
        if serial is None:
            return False

        try:
            self.serial = serial.Serial(
                self.serial_port,
                self.baudrate,
                timeout=1
            )
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
            # Opening an Arduino Uno serial port resets the board. Wait for
            # firmware startup before reporting the port as ready.
            time.sleep(2.0)
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
            self.raw_log_collector.reset()
            self.connected = True
            print("SERIAL CONNECTED", self.serial_port, self.baudrate)
            return True
        except Exception as e:
            print("SERIAL CONNECT ERROR", e)
            self.connected = False
            return False

    def forward(self):
        self.direction = "FWD"
        return self.send_command("FWD")

    def reverse(self):
        self.direction = "REV"
        return self.send_command("REV")

    def set_pwm(self, pwm):
        self.last_pwm = max(0, min(255, int(pwm)))
        return self.send_command(f"PWM={self.last_pwm}")

    def stop_breakin(self):
        self.set_pwm(0)
        return self.send_command("STOP")

    def emergency_stop(self):
        """Best-effort STOP sequence; successful writes do not prove physical stop."""
        was_connected = bool(self.connected and self.serial)
        errors = []

        # Try each safety action independently: a failed PWM=0 write must not
        # prevent the explicit STOP command or serial cleanup from being tried.
        try:
            self.set_pwm(0)
        except Exception as exc:
            errors.append(("PWM=0", exc))
            print("EMERGENCY STOP WARNING (PWM=0):", exc)

        try:
            self.send_command("STOP")
        except Exception as exc:
            errors.append(("STOP", exc))
            print("EMERGENCY STOP WARNING (STOP):", exc)

        try:
            self.disconnect()
        except Exception as exc:
            errors.append(("disconnect", exc))
            print("EMERGENCY STOP WARNING (disconnect):", exc)
        finally:
            # Keep software connection state fail-closed even if close() raises.
            self.serial = None
            self.connected = False

        # True means writes/cleanup raised no exceptions and a connection was
        # present at entry. It is NOT firmware acknowledgement or physical-stop proof.
        return was_connected and not errors

    def disconnect(self):
        serial_handle = self.serial
        try:
            if serial_handle:
                serial_handle.close()
        finally:
            self.serial = None
            self.connected = False

    def send_command(self, command):
        self.command_log.append(command)
        print("SERIAL TX:", command)

        if self.connected and self.serial:
            self.serial.write((command + "\n").encode("utf-8"))

        return command

    def read_measurement(self):
        """Read the newest DATA frame and retain the exact raw CSV string."""
        if not (self.connected and self.serial):
            return None

        latest_data = None
        while self.serial.in_waiting:
            raw = self.serial.readline()
            decoded = raw.decode("utf-8", errors="replace")
            if not decoded:
                continue
            self.raw_log_collector.append(decoded)
            line = decoded.strip()
            if not line:
                continue
            print("SERIAL RX:", line)
            if line.startswith("DATA,"):
                latest_data = line

        if latest_data is not None:
            self.last_raw_data = latest_data

        return latest_data
