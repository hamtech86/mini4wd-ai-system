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


def test_high_side_current_formatter_uses_current1_not_average():
    from types import SimpleNamespace

    from controllers.current_display import format_high_side_current

    measurement = SimpleNamespace(current1=0.123, current_avg=0.456)
    assert format_high_side_current(measurement) == "0.123 A"


def test_high_side_current_formatter_preserves_measured_zero():
    from types import SimpleNamespace

    from controllers.current_display import format_high_side_current

    assert format_high_side_current(SimpleNamespace(current1=0.0)) == "0.000 A"


def test_high_side_current_formatter_returns_placeholder_when_measurement_missing():
    from types import SimpleNamespace

    from controllers.current_display import format_high_side_current

    assert format_high_side_current(None) == "--"
    assert format_high_side_current(SimpleNamespace()) == "--"
    assert format_high_side_current(SimpleNamespace(current1=None)) == "--"


def test_high_side_current_formatter_returns_placeholder_when_value_not_convertible():
    from types import SimpleNamespace

    from controllers.current_display import format_high_side_current

    assert format_high_side_current(SimpleNamespace(current1="not-a-number")) == "--"
    assert format_high_side_current(SimpleNamespace(current1=object())) == "--"


def test_high_side_current_formatter_rejects_non_finite_values():
    from types import SimpleNamespace

    from controllers.current_display import format_high_side_current

    assert format_high_side_current(SimpleNamespace(current1=float("nan"))) == "--"
    assert format_high_side_current(SimpleNamespace(current1=float("inf"))) == "--"


def test_main_high_side_current_formatter_is_used_by_all_display_paths():
    """Guard the four Main display call sites without requiring a Qt session."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    app_source = (root / "app" / "main.py").read_text()
    ui_source = (root / "ui" / "main_window.py").read_text()

    # EXECUTION CURRENT + LIVE DATA A, and legacy UI LIVE DATA A + Result CURRENT.
    assert app_source.count("format_high_side_current(m)") == 2
    assert ui_source.count("format_high_side_current(m)") == 1
    assert ui_source.count("format_high_side_current(measurement)") == 1

    # current_avg remains available as a data field, but is not used as a display source.
    for source in (app_source, ui_source):
        assert "getattr(m,'current_avg',0)" not in source
        assert "getattr(m, 'current_avg', 0)" not in source
        assert "getattr(measurement, 'current_avg', 0)" not in source
