"""
MOTOR_BREAKIN_V3
Break-in Controller integration test

Hardware-independent verification of the complete controller path.
"""

from controllers.breakin_controller import BreakinController
from controllers.recipe import BreakinPhase, BreakinRecipe


class MockSerialController:
    def __init__(self):
        self.commands = []

    def forward(self):
        self.commands.append("FORWARD")

    def reverse(self):
        self.commands.append("REVERSE")

    def set_pwm(self, pwm):
        self.commands.append(f"PWM:{pwm}")

    def stop_breakin(self):
        self.commands.append("STOP")

    def emergency_stop(self):
        self.commands.append("EMERGENCY_STOP")


class MockMeasurementManager:
    def __init__(self):
        self.count = 0

    def collect(self):
        self.count += 1
        return {"measurement": "dummy", "sample": self.count}


class MockAnalysisEngine:
    def __init__(self):
        self.measurements = []

    def analyze(self, measurement):
        self.measurements.append(measurement)
        return {"result": "dummy", "sample": measurement["sample"]}


def test_complete_breakin_controller_path():
    serial = MockSerialController()
    measurement = MockMeasurementManager()
    analysis = MockAnalysisEngine()

    controller = BreakinController(
        serial_controller=serial,
        measurement_manager=measurement,
        analysis_engine=analysis,
    )

    recipe = BreakinRecipe(
        name="TEST",
        phases=[
            BreakinPhase(
                name="PHASE1",
                duration_sec=0,
                pwm=100,
                direction="FWD",
            )
        ],
    )

    result = controller.start(recipe)

    assert len(result) == 1
    assert result[0]["result"] == "dummy"
    assert len(analysis.measurements) == 1
    assert "FORWARD" in serial.commands
    assert "PWM:100" in serial.commands
    assert "STOP" in serial.commands


def test_emergency_stop():
    serial = MockSerialController()

    controller = BreakinController(serial_controller=serial)
    controller.running = True

    controller.emergency_stop()

    assert controller.running is False
    assert "EMERGENCY_STOP" in serial.commands


def test_benchmark_phase_counts_cover_all_modes_and_legacy_aliases():
    from controllers.motor_benchmark import (
        STANDARD,
        STD_T,
        FULL_T,
        STD_I,
        FULL_I,
        benchmark_phase_count,
    )
    assert benchmark_phase_count(STANDARD) == 2
    assert benchmark_phase_count("FULL_PACKAGE") == 6
    assert benchmark_phase_count(STD_T) == 2
    assert benchmark_phase_count(FULL_T) == 6
    assert benchmark_phase_count(STD_I) == 2
    assert benchmark_phase_count(FULL_I) == 6
    assert benchmark_phase_count("STANDARD_3V30S") == 2
    assert benchmark_phase_count("FULL_PACKAGE") == 6


def test_input_voltage_direction_and_motor_voltage_are_distinct():
    from controllers.motor_benchmark import INPUT, TERMINAL
    from measurement.measurement import Measurement

    def measurement(direction, v1, v2):
        return Measurement(
            record_type="DATA", device_model="MOTOR_BREAKIN_V3", instance_id="1",
            elapsed_time=1000, raw_acs1=0, raw_acs2=0,
            current1=0.1, current2=0.1, voltage1=v1, voltage2=v2,
            motor_voltage=2.2, pwm=80, direction=direction, state="RUNNING",
            current_avg=0.1, power=0.22, current_ripple=0.01,
            voltage_ripple=0.01, peak_power=0.3, peak_current=0.2,
            peak_voltage=2.3, peak_pwm=80, brush_peak_current=0.2,
            raw_magnetic=0, magnetic_level=0.0, motor_temperature=25.0,
        )

    fwd = measurement("FWD", 3.1, 0.9)
    rev = measurement("REV", 0.9, 3.1)
    assert fwd.input_voltage == 3.1
    assert rev.input_voltage == 3.1
    assert fwd.motor_voltage == 2.2
    assert rev.motor_voltage == 2.2

    serial = MockSerialController()
    controller = BreakinController(serial)
    controller.voltage_control_mode = INPUT
    phase_fwd = BreakinPhase("FWD", 1, 0, "FWD", "VOLTAGE", 3.0, pwm_min=35, pwm_max=120)
    phase_rev = BreakinPhase("REV", 1, 0, "REV", "VOLTAGE", 3.0, pwm_min=35, pwm_max=120)
    assert controller._controlled_voltage(phase_fwd, fwd) == 3.1
    assert controller._controlled_voltage(phase_rev, rev) == 3.1

    controller.voltage_control_mode = TERMINAL
    assert controller._controlled_voltage(phase_fwd, fwd) == 2.2


def test_remaining_time_uses_sequence_executor_authoritative_value():
    from controllers.breakin_sequence_adapter import BreakinSequenceAdapter
    from controllers.sequence_executor import SequenceExecutor
    from types import SimpleNamespace

    controller = BreakinController(MockSerialController())
    adapter = BreakinSequenceAdapter(controller)
    executor = SequenceExecutor(adapter=adapter)
    executor.sequences = [SimpleNamespace(sequence_id="01", enabled=True, duration_sec=30)]
    executor.results = [SimpleNamespace(status="RUNNING", remaining_sec=17.5, sequence_id="01")]
    executor.state = SimpleNamespace(sequence_index=0)
    controller.current_phase = BreakinPhase("01", 30, 0, "FWD")
    assert controller.execution_snapshot()["remaining_time"] == 17.5
