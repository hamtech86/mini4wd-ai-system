from communication.protocol import CSV_FIELDS
from communication.serial_controller import SerialController
from measurement.measurement_manager import MeasurementManager
from controllers.breakin_controller import BreakinController
from controllers.recipe import BreakinPhase


class FakePort:
    def __init__(self, lines):
        self.lines = [line.encode("utf-8") for line in lines]
        self.writes = []

    def write(self, data):
        self.writes.append(data)
        return len(data)

    @property
    def in_waiting(self):
        return len(self.lines)

    def readline(self):
        return self.lines.pop(0)


def data_line(**overrides):
    values = {
        "record_type": "DATA",
        "device_model": "MOTOR_BREAKIN_V3",
        "instance_id": "000011",
        "elapsed_time": 1000,
        "raw_acs1": 100,
        "raw_acs2": 101,
        "current1": 0.10,
        "current2": 0.09,
        "voltage1": 2.50,
        "voltage2": 0.20,
        "motor_voltage": 2.30,
        "pwm": 60,
        "direction": "FWD",
        "state": "RUN",
        "current_avg": 0.095,
        "power": 0.23,
        "current_ripple": 0.01,
        "voltage_ripple": 0.02,
        "peak_power": 0.30,
        "peak_current": 0.20,
        "peak_voltage": 2.50,
        "peak_pwm": 60,
        "brush_peak_current": 0.20,
        "raw_magnetic": 100,
        "magnetic_level": 2.0,
        "motor_temperature": 30.0,
    }
    values.update(overrides)
    return ",".join(str(values[field]) for field in CSV_FIELDS) + "\n"


def test_serial_controller_parses_data_for_measurement_manager_and_control():
    serial = SerialController()
    serial.connected = True
    serial.serial = FakePort([data_line()])
    manager = MeasurementManager(serial_controller=serial)

    measurement = manager.collect()

    assert measurement is not None
    assert measurement.voltage1 == 2.5
    assert measurement.voltage2 == 0.2
    assert serial.last_raw_data.startswith("DATA,")
    assert "DATA," in serial.raw_log

    controller = BreakinController(serial, measurement_manager=manager)
    controller.voltage_control_mode = "INPUT"
    controller.current_pwm = 60
    phase = BreakinPhase(
        "INPUT_FWD", 1, 60, "FWD", "VOLTAGE", 3.0,
        pwm_min=35, pwm_max=120,
    )

    controller._voltage_control(phase, measurement)

    # 3.00 V target - 2.50 V input = +0.50 V; Kp=20 -> +10 PWM.
    assert controller.current_pwm == 70
    assert serial.command_log[-1] == "PWM=70"


def test_invalid_csv_does_not_become_a_control_measurement():
    serial = SerialController()
    serial.connected = True
    serial.serial = FakePort(["DATA,too,short\n"])
    manager = MeasurementManager(serial_controller=serial)

    assert manager.collect() is None
