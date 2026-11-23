from types import SimpleNamespace
import pytest
from analysis.battery_benchmark_session import extract_battery_benchmark


def row(t, i, v, ch="CH1"):
    return SimpleNamespace(elapsed_time=t, current1=i if ch == "CH1" else None,
                           current2=i if ch == "CH2" else None, voltage1=v if ch == "CH1" else None,
                           voltage2=v if ch == "CH2" else None, power=i*v, instance_id=ch)


def test_benchmark_extracts_features_without_scoring():
    result = extract_battery_benchmark([row(0, 5.0, 1.4), row(1000, 5.0, 1.3)], channel="CH1")
    assert result["measurement_count"] == 2
    assert result["avg_current"] == pytest.approx(5.0)
    assert result["voltage_drop"] == pytest.approx(0.1)
    assert result["capacity_mah"] == pytest.approx(5.0 / 3600 * 1000)
    assert result["energy_wh"] == pytest.approx(6.75 / 3600)
    assert result["internal_resistance_mohm"] is None
    assert result["overall_score"] is None


def test_benchmark_uses_only_the_explicit_channel_when_other_channel_is_present():
    result = extract_battery_benchmark(
        [row(0, 5, 1.4, "CH1"), row(1000, 5, 1.3, "CH2")], channel="CH1"
    )
    assert result["measurement_count"] == 1
    assert result["avg_voltage"] == pytest.approx(1.4)
    assert result["avg_current"] == pytest.approx(5.0)


def test_benchmark_requires_explicit_channel_and_never_falls_back():
    with pytest.raises(TypeError):
        extract_battery_benchmark([row(0, 5.0, 1.4)])
    with pytest.raises(ValueError):
        extract_battery_benchmark([row(0, 5.0, 1.4, "CH2")], channel="CH1")


def test_selected_channel_zero_is_unknown_not_silently_dropped():
    with pytest.raises(ValueError, match="validity is UNKNOWN"):
        extract_battery_benchmark([row(0, 0.0, 1.4, "CH1")], channel="CH1")


def test_nonselected_channel_zero_does_not_affect_selected_channel():
    source = SimpleNamespace(
        elapsed_time=0, current1=5.0, voltage1=1.4, current2=0.0, voltage2=0.0
    )
    result = extract_battery_benchmark([source], channel="CH1")
    assert result["avg_current"] == pytest.approx(5.0)
    assert result["avg_voltage"] == pytest.approx(1.4)
