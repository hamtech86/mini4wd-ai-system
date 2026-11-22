import math
import pytest

from analysis.battery_benchmark import analyze_5a_measurements


def rows():
    return [
        {"elapsed_time": 0.0, "voltage1": 1.40, "voltage2": 1.42, "current1": 5.0, "current2": 4.8},
        {"elapsed_time": 1.0, "voltage1": 1.30, "voltage2": 1.32, "current1": 5.2, "current2": 5.0},
    ]


def test_ch1_only_result_uses_only_ch1_values():
    result = analyze_5a_measurements(rows(), channel="CH1")
    assert result["channel"] == "CH1"
    assert result["avg_voltage"] == pytest.approx(1.35)
    assert result["avg_current"] == pytest.approx(5.1)
    assert result["avg_power"] == pytest.approx((1.40 * 5.0 + 1.30 * 5.2) / 2)


def test_ch2_only_result_uses_only_ch2_values():
    result = analyze_5a_measurements(rows(), channel="CH2")
    assert result["channel"] == "CH2"
    assert result["avg_voltage"] == pytest.approx(1.37)
    assert result["avg_current"] == pytest.approx(4.9)
    assert result["avg_power"] == pytest.approx((1.42 * 4.8 + 1.32 * 5.0) / 2)


def test_both_channels_are_returned_as_independent_results():
    source = rows()
    ch1 = analyze_5a_measurements(source, channel="CH1")
    ch2 = analyze_5a_measurements(source, channel="CH2")
    assert ch1["avg_voltage"] != ch2["avg_voltage"]
    assert ch1["avg_current"] != ch2["avg_current"]
    assert ch1["avg_power"] != ch2["avg_power"]
    assert ch1["capacity_mah"] != ch2["capacity_mah"]


@pytest.mark.parametrize("channel,selected,other", [
    ("CH1", "voltage1", "voltage2"),
    ("CH2", "voltage2", "voltage1"),
])
def test_missing_or_zero_selected_channel_does_not_fallback(channel, selected, other):
    data = [{"elapsed_time": 0.0, selected: 0.0, other: 1.4}]
    result = analyze_5a_measurements(data, channel=channel)
    assert result["avg_voltage"] is None


@pytest.mark.parametrize("channel,selected,other", [
    ("CH1", "current1", "current2"),
    ("CH2", "current2", "current1"),
])
def test_missing_selected_current_does_not_fallback(channel, selected, other):
    data = [{"elapsed_time": 0.0, selected: None, other: 5.0}]
    result = analyze_5a_measurements(data, channel=channel)
    assert result["avg_current"] is None


def test_both_selected_values_missing_produce_no_values():
    result = analyze_5a_measurements([{"elapsed_time": 0.0}], channel="CH1")
    assert result["avg_voltage"] is None
    assert result["avg_current"] is None


@pytest.mark.parametrize("bad", ["not-a-number", float("nan"), float("inf"), float("-inf")])
def test_invalid_selected_values_are_ignored_without_other_channel_fallback(bad):
    result = analyze_5a_measurements(
        [{"elapsed_time": 0.0, "voltage1": bad, "voltage2": 1.4, "current1": bad, "current2": 5.0}],
        channel="CH1",
    )
    assert result["avg_voltage"] is None
    assert result["avg_current"] is None


def test_channel_is_mandatory_and_validated():
    with pytest.raises(TypeError):
        analyze_5a_measurements(rows())
    with pytest.raises(ValueError):
        analyze_5a_measurements(rows(), channel="CH3")


def test_source_measurements_are_not_mutated():
    source = rows()
    before = [dict(row) for row in source]
    analyze_5a_measurements(source, channel="CH1")
    assert source == before
