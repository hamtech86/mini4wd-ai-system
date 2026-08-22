"""Battery Arduino serial transport.

This is the transport from the physically verified Battery 5A standalone
implementation. The Arduino firmware/protocol is intentionally unchanged.
"""
from dataclasses import dataclass
import csv
import io
try:
    import serial
except ImportError:
    serial = None

@dataclass
class BatterySample:
    channel: int = 0
    voltage: float | None = None
    current: float | None = None
    pwm: int | None = None
    elapsed_sec: float | None = None
    state: str = "--"
    raw: str = ""

class BatterySerial:
    BAUDRATE = 57600
    DEFAULT_PORT = "/dev/ttyUSB0"
    def __init__(self, port=DEFAULT_PORT, baudrate=BAUDRATE):
        self.port = port
        self.baudrate = baudrate
        self.serial = None
        self.connected = False
        self.last_error = ""
    def connect(self):
        if serial is None:
            self.last_error = "pyserial is not installed"
            return False
        try:
            self.serial = serial.Serial(self.port, self.baudrate, timeout=0.1)
            self.connected = True
            self.last_error = ""
            return True
        except Exception as exc:
            self.connected = False
            self.serial = None
            self.last_error = f"{type(exc).__name__}: {exc}"
            return False
    def disconnect(self):
        if self.serial:
            try:
                self.serial.close()
            finally:
                self.serial = None
        self.connected = False
    def send(self, command):
        if not self.connected or not self.serial:
            return False
        self.serial.write((command + "\n").encode("utf-8"))
        return True
    def start(self, channel=None):
        return self.send("STARTALL" if channel is None else f"START{int(channel)}")
    def stop(self, channel=None):
        return self.send("STOPALL" if channel is None else f"STOP{int(channel)}")
    def read_lines(self):
        if not self.connected or not self.serial:
            return []
        lines = []
        while self.serial.in_waiting:
            raw = self.serial.readline()
            text = raw.decode("utf-8", errors="replace").strip()
            if text:
                lines.append(text)
        return lines
    @staticmethod
    def parse_data(line):
        if not line.startswith("DATA,"):
            return None
        fields = next(csv.reader(io.StringIO(line)))
        if len(fields) < 10:
            return None
        try:
            channel = int(fields[2].strip().upper().replace("CH", ""))
            elapsed_ms = float(fields[3])
            current = float(fields[4])
            voltage = float(fields[5])
            pwm = int(float(fields[7]))
            state = fields[9].strip() or "--"
        except (ValueError, IndexError):
            return None
        return BatterySample(channel=channel, voltage=voltage, current=current,
                             pwm=pwm, elapsed_sec=elapsed_ms / 1000.0,
                             state=state, raw=line)
