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


def test_benchmark_stops_after_three_consecutive_invalid_samples():
    serial = FakeSerial([
        frame(voltage1=14.0, motor_voltage=13.5),
        frame(voltage1=14.1, motor_voltage=13.6),
        frame(voltage1=14.0, motor_voltage=13.5),
        frame(),
    ])
    manager = MeasurementManager(serial_controller=serial)
    controller = BreakinController(serial_controller=serial, measurement_manager=manager)
    controller.running = True
    controller.current_pwm = 60
    phase = type("Phase", (), {"target_voltage": 3.0, "pwm_min": 35, "pwm_max": 120})()

    assert benchmark_collect(controller, phase) is None
    assert controller.running is True
    assert benchmark_collect(controller, phase) is None
    assert controller.running is True
    assert benchmark_collect(controller, phase) is None

    assert controller.running is False
    assert controller.current_pwm == 0
    assert "3 consecutive invalid measurements" in controller.abort_reason
    assert serial.commands[-1] == 0
    # A fourth queued sample must not be needed to trigger the stop.
    assert len(serial.frames) == 1


def test_valid_sample_resets_consecutive_invalid_count():
    serial = FakeSerial([
        frame(voltage1=14.0, motor_voltage=13.5),
        frame(voltage1=14.0, motor_voltage=13.5),
        frame(motor_voltage=2.95),
        frame(voltage1=14.0, motor_voltage=13.5),
    ])
    manager = MeasurementManager(serial_controller=serial)
    controller = BreakinController(serial_controller=serial, measurement_manager=manager)
    controller.running = True
    phase = type("Phase", (), {"target_voltage": 3.0, "pwm_min": 35, "pwm_max": 120})()

    assert benchmark_collect(controller, phase) is None
    assert benchmark_collect(controller, phase) is None
    assert benchmark_collect(controller, phase) is not None
    assert controller._consecutive_invalid_measurements == 0
    assert benchmark_collect(controller, phase) is None
    assert controller.running is True
    assert controller._consecutive_invalid_measurements == 1


def test_missing_or_nonfinite_current_avg_is_invalid_not_zero():
    for invalid in (None, "", "NaN", float("inf")):
        manager = MeasurementManager(
            serial_controller=FakeSerial([frame(current_avg=invalid)])
        )
        assert manager.collect() is None


def test_normal_breakin_stops_after_three_consecutive_invalid_samples():
    serial = FakeSerial([frame(current_avg=None)] * 3 + [frame()])
    manager = MeasurementManager(serial_controller=serial)
    controller = BreakinController(serial, measurement_manager=manager)
    controller.running = True
    controller.current_pwm = 60
    phase = type(
        "Phase",
        (),
        {"target_voltage": 3.0, "pwm_min": 35, "pwm_max": 120,
         "direction": "FWD", "control": "VOLTAGE", "start_voltage": None},
    )()

    assert controller._collect_measurement(phase) is None
    assert controller.running is True
    assert controller._collect_measurement(phase) is None
    assert controller.running is True
    assert controller._collect_measurement(phase) is None

    assert controller.running is False
    assert controller.current_pwm == 0
    assert "3 consecutive invalid measurements" in controller.abort_reason
    assert 0 in serial.commands


def test_zero_voltage_is_invalid_feedback_during_driven_voltage_phase():
    serial = FakeSerial([frame(voltage1=0.0, motor_voltage=0.0)])
    manager = MeasurementManager(serial_controller=serial)
    controller = BreakinController(serial, measurement_manager=manager)
    controller.current_pwm = 60
    phase = type(
        "Phase",
        (),
        {"target_voltage": 3.0, "pwm_min": 35, "pwm_max": 120,
         "direction": "FWD", "control": "VOLTAGE", "start_voltage": None},
    )()

    assert controller._collect_measurement(phase) is None


def test_sequence_adapter_uses_shared_three_invalid_measurement_stop():
    from types import SimpleNamespace
    from controllers.breakin_sequence_adapter import BreakinSequenceAdapter
    from controllers.sequence_executor import SequenceExecutor

    serial = FakeSerial([frame(current_avg=None)] * 3)
    serial.require_identified_device = lambda: None
    serial.forward = lambda: serial.commands.append("FWD")
    serial.reverse = lambda: serial.commands.append("REV")
    controller = BreakinController(serial, measurement_manager=MeasurementManager(serial_controller=serial))
    adapter = BreakinSequenceAdapter(controller)
    executor = SequenceExecutor(adapter=adapter)
    sequence = SimpleNamespace(
        sequence_id="INPUT-FWD", direction="FWD", pwm=60, duration_sec=1,
        metadata={}, parameters={
            "control": "VOLTAGE", "target_voltage": 3.0,
            "pwm_min": 35, "pwm_max": 120,
            "voltage_control_mode": "INPUT",
        },
    )

    adapter.start_sequence(sequence)
    adapter.tick(sequence)
    adapter.tick(sequence)
    adapter.tick(sequence)

    assert controller.running is False
    assert executor.running is False
    assert controller.current_pwm == 0
    assert "3 consecutive invalid measurements" in controller.abort_reason
    assert 0 in serial.commands



def test_three_consecutive_unusable_samples_count_across_validation_layers():
    # 1st: DATA-frame range failure; 2nd: frame parses but active voltage
    # feedback is invalid; 3rd: DATA frame is incomplete. The shared safety
    # counter counts unusable acquisition cycles, not one specific fault type.
    serial = FakeSerial([
        frame(voltage1=14.0, motor_voltage=13.5),
        frame(voltage1=0.0, motor_voltage=0.0),
        frame(current_avg=None),
        frame(),
    ])
    manager = MeasurementManager(serial_controller=serial)
    controller = BreakinController(serial, measurement_manager=manager)
    controller.running = True
    controller.current_pwm = 60
    phase = type(
        "Phase",
        (),
        {"target_voltage": 3.0, "pwm_min": 35, "pwm_max": 120,
         "direction": "FWD", "control": "VOLTAGE", "start_voltage": None},
    )()

    assert controller._collect_measurement(phase) is None
    assert controller.running is True
    assert controller._collect_measurement(phase) is None
    assert controller.running is True
    assert controller._collect_measurement(phase) is None
    assert controller.running is False
    assert controller.current_pwm == 0
    assert "3 consecutive invalid measurements" in controller.abort_reason
    assert len(serial.frames) == 1



def test_serial_receive_timeout_none_three_times_triggers_shared_safety_stop():
    from communication.serial_controller import SerialController

    class TimeoutPort:
        def __init__(self):
            self.ready = False
            self.timeout_reads = 0
            self.writes = []
            self.timeout = 0.01
            self.closed = False

        @property
        def in_waiting(self):
            return 1 if self.ready else 0

        def readline(self):
            # Simulate readline timing out after the receive path sees a
            # pending read opportunity. The empty result must become None.
            self.ready = False
            self.timeout_reads += 1
            return b""

        def write(self, data):
            self.writes.append(data.decode("utf-8"))
            return len(data)

        def close(self):
            self.closed = True

    serial = SerialController()
    port = TimeoutPort()
    serial.connected = True
    serial.serial = port
    serial.device_info = {
        "TYPE": "MOTOR", "MODEL": "MOTOR_BREAKIN_V3", "FW": "3.00",
        "BUILD": "TEST", "ID": "000001",
    }
    serial._identity_confirmed = True
    serial.identity_error = None
    manager = MeasurementManager(serial_controller=serial)
    controller = BreakinController(serial, measurement_manager=manager)
    controller.running = True
    controller.current_pwm = 60
    phase = type(
        "Phase",
        (),
        {"target_voltage": 3.0, "pwm_min": 35, "pwm_max": 120,
         "direction": "FWD", "control": "VOLTAGE", "start_voltage": None},
    )()

    for expected_failures in (1, 2, 3):
        port.ready = True
        assert controller._collect_measurement(phase) is None
        assert controller._consecutive_invalid_measurements == expected_failures
        if expected_failures < 3:
            assert controller.running is True

    assert port.timeout_reads == 3
    assert controller.running is False
    assert controller.current_pwm == 0
    assert "3 consecutive invalid measurements" in controller.abort_reason
    assert "PWM=0" in port.writes
    assert "STOP" in port.writes
    assert port.closed is True
