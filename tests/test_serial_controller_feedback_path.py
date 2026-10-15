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
    serial.device_info = {
        "TYPE": "MOTOR", "MODEL": "MOTOR_BREAKIN_V3", "FW": "3.00",
        "BUILD": "TEST", "ID": "000001",
    }
    serial._identity_confirmed = True
    serial.identity_error = None
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


def test_input_control_uses_a5_voltage_for_reverse_and_terminal_keeps_motor_voltage():
    serial = SerialController()
    controller = BreakinController(serial, measurement_manager=None)
    measurement = {
        "direction": "REV",
        "voltage1": 3.1,
        "voltage2": 2.8,
        "motor_voltage": 2.2,
    }
    reverse_phase = BreakinPhase(
        "INPUT_REV", 1, 60, "REV", "VOLTAGE", 3.0,
        pwm_min=35, pwm_max=120,
    )

    controller.voltage_control_mode = "INPUT"
    assert controller._controlled_voltage(reverse_phase, measurement) == 2.8

    controller.voltage_control_mode = "TERMINAL"
    assert controller._controlled_voltage(reverse_phase, measurement) == 2.2


def test_terminal_voltage_control_converts_signed_motor_voltage_by_direction():
    controller = BreakinController(SerialController(), measurement_manager=None)
    phase_fwd = BreakinPhase("TERM_FWD", 1, 60, "FWD", "VOLTAGE", 3.0, pwm_min=35, pwm_max=120)
    phase_rev = BreakinPhase("TERM_REV", 1, 60, "REV", "VOLTAGE", 3.0, pwm_min=35, pwm_max=120)

    controller.voltage_control_mode = "TERMINAL"
    assert controller._controlled_voltage(phase_fwd, {
        "direction": "FWD", "motor_voltage": 2.4,
    }) == 2.4
    assert controller._controlled_voltage(phase_rev, {
        "direction": "REV", "motor_voltage": -2.4,
    }) == 2.4


def test_signed_negative_motor_voltage_is_accepted_by_measurement_parser():
    serial = SerialController()
    serial.connected = True
    serial.serial = FakePort([data_line(
        voltage1=0.2, voltage2=2.5, motor_voltage=-2.3, direction="REV",
    )])
    manager = MeasurementManager(serial_controller=serial)

    measurement = manager.collect()

    assert measurement is not None
    assert measurement.motor_voltage == -2.3
