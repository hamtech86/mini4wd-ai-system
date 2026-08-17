"""Battery Arduino serial transport.

The battery firmware is treated as immutable.  This layer only sends operator
commands and parses DATA/DEBUG frames without coupling the UI to the firmware.
"""
from dataclasses import dataclass
import csv
import io

try:
    import serial
except ImportError:  # pragma: no cover - optional until runtime
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

    def __init__(self, port="/dev/ttyACM0", baudrate=BAUDRATE):
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
        return self.send("START,ALL" if channel is None else f"START,{int(channel)}")

    def stop(self, channel=None):
        return self.send("STOP,ALL" if channel is None else f"STOP,{int(channel)}")

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
        """Best-effort parser for DATA CSV frames.

        The UI accepts both positional frames and key=value fields so the
        firmware protocol can evolve without changing the presentation layer.
        DEBUG frames are deliberately rejected here.
        """
        if not line.startswith("DATA,"):
            return None
        fields = next(csv.reader(io.StringIO(line)))
        values = {}
        for item in fields[1:]:
            if "=" in item:
                key, value = item.split("=", 1)
                values[key.strip().lower()] = value.strip()

        def num(*keys):
            for key in keys:
                value = values.get(key)
                if value is not None:
                    try:
                        return float(value)
                    except ValueError:
                        pass
            return None

        channel = num("channel", "ch")
        return BatterySample(
            channel=int(channel) if channel is not None else 0,
            voltage=num("voltage", "v", "battery_voltage"),
            current=num("current", "a", "current_a", "measured_current"),
            pwm=int(num("pwm")) if num("pwm") is not None else None,
            elapsed_sec=num("elapsed", "elapsed_sec", "time", "seconds"),
            state=values.get("state", "--"),
            raw=line,
        )
