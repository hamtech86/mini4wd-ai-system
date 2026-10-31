import pytest

from communication.rawlog_v2_alignment import align_aux_records
from communication.rawlog_v2_analysis import (
    AuxAnalysisError, ChannelCalibration, analyze_winding_resistance_cycle,
    convert_cycle_channels,
)
from communication.rawlog_v2_aux import parse_aux_line


def cycle(direction="FWD", run_state="MEASURE", a0=100, a4=110, a5=120, a1=125):
    rows = [
        parse_aux_line(f"AUX,2,s1,1,WINDING,{direction},0,{run_state},A0,510,{a0}"),
        parse_aux_line(f"AUX,2,s1,1,WINDING,{direction},0,{run_state},A4,600,{a4}"),
        parse_aux_line(f"AUX,2,s1,1,WINDING,{direction},0,{run_state},A5,500,{a5}"),
        parse_aux_line(f"AUX,2,s1,1,WINDING,{direction},0,{run_state},A1,900,{a1}"),
    ]
    return align_aux_records(rows)[0]


def calibrations():
    return {
        "A0": ChannelCalibration("A0", 0.01, -5.0, "A"),
        "A1": ChannelCalibration("A1", 0.1, 0.0, "A"),
        "A4": ChannelCalibration("A4", 0.01, 0.0, "V"),
        "A5": ChannelCalibration("A5", 0.01, 0.0, "V"),
    }


def test_converts_channels_only_with_explicit_independent_calibration():
    converted = convert_cycle_channels(cycle(), calibrations())
    assert converted["A0"].value == pytest.approx(0.1)
    assert converted["A1"].value == pytest.approx(90.0)
    assert converted["A0"].sample_id != converted["A1"].sample_id


def test_winding_resistance_uses_a0_and_direction_aware_voltage():
    result = analyze_winding_resistance_cycle(
        cycle(), calibrations(), max_skew_us=20, required_run_state="MEASURE"
    )
    assert result.valid is True
    assert result.voltage_delta_v == pytest.approx(1.0)
    assert result.current_a == pytest.approx(0.1)
    assert result.resistance_ohm == pytest.approx(10.0)
    assert result.input_sample_ids == ("s1:1:A0", "s1:1:A4", "s1:1:A5")


def test_reverse_direction_reverses_voltage_difference_order():
    result = analyze_winding_resistance_cycle(
        cycle(direction="REV"), calibrations(), max_skew_us=20,
        required_run_state="MEASURE"
    )
    assert result.valid is True
    assert result.voltage_delta_v == pytest.approx(-1.0)
    assert result.resistance_ohm == pytest.approx(10.0)


def test_a1_is_never_used_as_winding_current():
    cal = calibrations()
    del cal["A0"]
    result = analyze_winding_resistance_cycle(
        cycle(), cal, max_skew_us=20, required_run_state="MEASURE"
    )
    assert result.valid is False
    assert "A0" in result.invalid_reason


def test_skew_policy_is_mandatory_and_excess_skew_invalidates_result():
    with pytest.raises(TypeError):
        analyze_winding_resistance_cycle(cycle(), calibrations())
    result = analyze_winding_resistance_cycle(
        cycle(a0=100, a4=110, a5=140, a1=150), calibrations(),
        max_skew_us=20, required_run_state="MEASURE"
    )
    assert result.valid is False
    assert result.invalid_reason == "timestamp skew exceeds configured maximum"


def test_zero_current_is_invalid_not_zero_resistance():
    cal = calibrations()
    cal["A0"] = ChannelCalibration("A0", 0.0, 0.0, "A")
    result = analyze_winding_resistance_cycle(
        cycle(), cal, max_skew_us=20, required_run_state="MEASURE"
    )
    assert result.valid is False
    assert result.resistance_ohm is None
    assert result.invalid_reason == "A0 current is zero after calibration"


def test_invalid_calibration_is_rejected():
    with pytest.raises(AuxAnalysisError):
        ChannelCalibration("A0", float("nan"), 0.0, "A")
