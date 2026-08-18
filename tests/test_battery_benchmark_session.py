from types import SimpleNamespace
import pytest
from analysis.battery_benchmark_session import extract_battery_benchmark


def row(t, i, v, ch="CH1"):
    return SimpleNamespace(elapsed_time=t, current1=i if ch == "CH1" else 0.0,
                           current2=i if ch == "CH2" else 0.0, voltage1=v if ch == "CH1" else 0.0,
                           voltage2=v if ch == "CH2" else 0.0, power=i*v, instance_id=ch)


def test_benchmark_extracts_features_without_scoring():
    result = extract_battery_benchmark([row(0, 5.0, 1.4), row(1000, 5.0, 1.3)])
    assert result["measurement_count"] == 2
    assert result["avg_current"] == pytest.approx(5.0)
    assert result["voltage_drop"] == pytest.approx(0.1)
    assert result["capacity_mah"] == pytest.approx(5.0 / 3600 * 1000)
    assert result["energy_wh"] == pytest.approx(6.75 / 3600)
    assert result["internal_resistance_mohm"] is None
    assert result["overall_score"] is None


def test_benchmark_never_combines_channels():
    with pytest.raises(ValueError):
        extract_battery_benchmark([row(0, 5, 1.4, "CH1"), row(1000, 5, 1.3, "CH2")])
