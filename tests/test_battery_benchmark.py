import pytest

from analysis.battery_benchmark import analyze_5a_measurements


def test_5a_benchmark_extracts_features_without_scoring():
    rows = [
        {"elapsed_time": 0.0, "voltage1": 1.40, "current1": 5.0},
        {"elapsed_time": 1.0, "voltage1": 1.39, "current1": 5.0},
        {"elapsed_time": 2.0, "voltage1": 1.38, "current1": 5.0},
    ]
    result = analyze_5a_measurements(rows)

    assert result["measurement_count"] == 3
    assert result["avg_voltage"] == pytest.approx(1.39)
    assert result["avg_current"] == pytest.approx(5.0)
    assert result["max_current"] == pytest.approx(5.0)
    assert result["discharge_time_s"] == pytest.approx(2.0)
    assert result["voltage_drop"] == pytest.approx(0.02)
    assert result["capacity_mah"] == pytest.approx(10.0 / 3600.0 * 1000.0)
    assert result["energy_wh"] is not None
    assert result["overall_score"] is None
    assert result["internal_resistance_mohm"] is None


def test_two_channels_are_averaged_per_measurement():
    rows = [
        {"elapsed_time": 0.0, "voltage1": 1.40, "voltage2": 1.42, "current1": 5.0, "current2": 4.8},
        {"elapsed_time": 1.0, "voltage1": 1.30, "voltage2": 1.32, "current1": 5.2, "current2": 5.0},
    ]
    result = analyze_5a_measurements(rows)
    assert result["avg_voltage"] == pytest.approx(1.36)
    assert result["avg_current"] == pytest.approx(5.0)
    assert result["discharge_time_s"] == pytest.approx(1.0)
