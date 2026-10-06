from controllers.breakin_controller import BreakinController
from controllers.motor_benchmark import _collect as benchmark_collect
from measurement.measurement_manager import MeasurementManager


def frame(**overrides):
    data = {
        "record_type": "DATA",
        "device_model": "MOTOR_BREAKIN_V3",
        "instance_id": "MOTOR-TEST",
        "elapsed_time": 1000,
        "raw_acs1": 100,
        "raw_acs2": 100,
        "current1": 0.10,
        "current2": 0.08,
        "voltage1": 3.00,
        "voltage2": 0.01,
        "motor_voltage": 2.99,
        "pwm": 60,
        "direction": "FWD",
        "state": "RUNNING",
        "current_avg": 0.09,
        "power": 0.27,
        "current_ripple": 0.01,
        "voltage_ripple": 0.01,
        "peak_power": 0.30,
        "peak_current": 0.20,
        "peak_voltage": 3.02,
        "peak_pwm": 60,
        "brush_peak_current": 0.20,
        "raw_magnetic": 100,
        "magnetic_level": 2.0,
        "motor_temperature": 30.0,
    }
    data.update(overrides)
    return data


class FakeSerial:
    def __init__(self, frames):
        self.frames = list(frames)
        self.commands = []

    @property
    def last_pwm(self):
        return 60

    @property
    def direction(self):
        return "FWD"

    def read_measurement(self):
        return self.frames.pop(0) if self.frames else None

    def set_pwm(self, pwm):
        self.commands.append(pwm)


def test_missing_data_is_invalid_not_zero():
    serial = FakeSerial([frame(motor_voltage=None, current1=None)])
    manager = MeasurementManager(serial_controller=serial)

    assert manager.collect() is None
    assert manager.last_measurement is None


def test_abnormal_voltage_is_invalid_and_not_used_for_control():
    serial = FakeSerial([frame(motor_voltage=999.0)])
    manager = MeasurementManager(serial_controller=serial)

    assert manager.collect() is None

    controller = BreakinController(serial_controller=serial, measurement_manager=manager)
    controller.current_pwm = 60
    phase = type("Phase", (), {"target_voltage": 3.0, "pwm_min": 35, "pwm_max": 120})()
    controller._voltage_control(phase, None)

    assert serial.commands == []


def test_abnormal_current_is_invalid_but_overcurrent_safety_value_remains_valid():
    invalid = MeasurementManager(serial_controller=FakeSerial([frame(current1=999.0)]))
    assert invalid.collect() is None

    # 5 A is the configured safety boundary and must not be hidden as INVALID.
    valid_overcurrent = MeasurementManager(serial_controller=FakeSerial([frame(current1=5.5)]))
    measurement = valid_overcurrent.collect()
    assert measurement is not None
    assert measurement.current1 == 5.5


def test_invalid_sample_is_skipped_and_next_valid_sample_is_used():
    serial = FakeSerial([frame(motor_voltage=999.0), frame(motor_voltage=2.90)])
    manager = MeasurementManager(serial_controller=serial)
    controller = BreakinController(serial_controller=serial, measurement_manager=manager)
    controller.current_pwm = 60
    phase = type(
        "Phase",
        (),
        {"target_voltage": 3.0, "pwm_min": 35, "pwm_max": 120, "direction": "FWD"},
    )()

    first = controller._collect_measurement(phase)
    assert first is None
    assert controller.current_pwm == 60
    assert serial.commands == []

    second = controller._collect_measurement(phase)
    assert second is not None
    controller._voltage_control(phase, second)
    assert controller.current_pwm != 60
    assert serial.commands == [62]


def test_benchmark_common_collection_path_skips_invalid_data():
    serial = FakeSerial([frame(motor_voltage=999.0), frame(motor_voltage=2.95)])
    manager = MeasurementManager(serial_controller=serial)
    controller = BreakinController(serial_controller=serial, measurement_manager=manager)
    phase = type("Phase", (), {"target_voltage": 3.0, "pwm_min": 35, "pwm_max": 120})()

    assert benchmark_collect(controller, phase) is None
    assert benchmark_collect(controller, phase) is not None
