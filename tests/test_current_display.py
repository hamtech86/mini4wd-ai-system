from types import SimpleNamespace

import pytest

from controllers.current_display import format_high_side_current, format_input_voltage


@pytest.mark.parametrize(
    ("direction", "expected"),
    [("FWD", "1.23 V"), ("REV", "4.56 V")],
)
def test_input_voltage_uses_physical_input_for_direction(direction, expected):
    measurement = SimpleNamespace(
        direction=direction,
        voltage1=1.234,
        voltage2=4.556,
        motor_voltage=-3.322,
    )
    assert format_input_voltage(measurement) == expected


def test_input_voltage_prefers_active_phase_direction():
    measurement = SimpleNamespace(direction="FWD", voltage1=1.2, voltage2=4.5)
    assert format_input_voltage(measurement, "REV") == "4.50 V"


@pytest.mark.parametrize("measurement", [None, SimpleNamespace(direction="SIDEWAYS")])
def test_input_voltage_is_unavailable_without_valid_direction(measurement):
    assert format_input_voltage(measurement) == "--"


@pytest.mark.parametrize("value", [None, "bad", float("nan"), float("inf")])
def test_input_voltage_rejects_missing_invalid_or_non_finite_values(value):
    measurement = SimpleNamespace(direction="FWD", voltage1=value, voltage2=2.0)
    assert format_input_voltage(measurement) == "--"


def test_high_side_current_uses_current1_not_average():
    measurement = SimpleNamespace(current1=0.1234, current_avg=0.4567)
    assert format_high_side_current(measurement) == "0.123 A"


def test_high_side_current_preserves_real_zero_and_missing_as_placeholder():
    assert format_high_side_current(SimpleNamespace(current1=0.0)) == "0.000 A"
    assert format_high_side_current(None) == "--"
    assert format_high_side_current(SimpleNamespace(current_avg=0.5)) == "--"
