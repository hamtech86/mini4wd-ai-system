from analysis.battery_analysis import analyze_benchmark_result


def test_analysis_maps_canonical_benchmark_values():
    benchmark = {
        "result_id": 12,
        "session_id": "BAT-001",
        "instance_id": "NEO-01",
        "measurement_count": 100,
        "avg_voltage": 1.12,
        "avg_current": 4.95,
        "avg_power": 5.54,
        "max_current": 5.1,
        "max_power": 5.8,
        "discharge_time_s": 600.0,
        "capacity_mah": 820.0,
        "energy_wh": 9.1,
        "start_voltage": 1.339,
        "end_voltage": 1.173,
        "voltage_drop": 0.166,
        "voltage_stddev": 0.015,
        "current_stddev": 0.08,
        "power_stddev": 0.11,
        "internal_resistance_mohm": None,
    }

    result = analyze_benchmark_result(benchmark)

    assert result.benchmark_id == 12
    assert result.session_id == "BAT-001"
    assert result.instance_id == "NEO-01"
    assert result.capacity_mah == 820.0
    assert result.energy_wh == 9.1
    assert result.discharge_time_s == 600.0
    assert result.start_voltage == 1.339
    assert result.end_voltage == 1.173
    assert result.voltage_drop == 0.166
    assert result.voltage_drop_rate == (1.339 - 1.173) / 1.339
    assert result.internal_resistance_mohm is None
    assert result.stability == "UNSCORED"
    assert result.rank is None
    assert "internal_resistance_not_evaluated" in result.warnings
    assert "evaluation_thresholds_not_configured" in result.warnings
    assert "start_voltage_unavailable" not in result.warnings
    assert "end_voltage_unavailable" not in result.warnings
    assert "voltage_drop_rate_unavailable" not in result.warnings


def test_analysis_does_not_mutate_benchmark_input():
    benchmark = {
        "result_id": 1,
        "measurement_count": 1,
        "avg_voltage": 1.2,
        "avg_current": 5.0,
        "avg_power": 6.0,
        "start_voltage": 1.2,
        "end_voltage": 1.1,
        "voltage_drop": 0.1,
        "voltage_stddev": 0.0,
        "current_stddev": 0.0,
        "power_stddev": 0.0,
    }
    before = dict(benchmark)

    analyze_benchmark_result(benchmark)

    assert benchmark == before


def test_analysis_marks_missing_canonical_voltage_inputs():
    benchmark = {
        "result_id": 4,
        "measurement_count": 0,
        "avg_voltage": 1.1,
        "avg_current": 4.0,
        "avg_power": 4.4,
        "voltage_drop": None,
    }

    result = analyze_benchmark_result(benchmark)

    assert result.start_voltage is None
    assert result.end_voltage is None
    assert result.voltage_drop_rate is None
    assert "no_measurements" in result.warnings
    assert "start_voltage_unavailable" in result.warnings
    assert "end_voltage_unavailable" in result.warnings
    assert "voltage_drop_unavailable" in result.warnings
    assert "voltage_drop_rate_unavailable" in result.warnings
