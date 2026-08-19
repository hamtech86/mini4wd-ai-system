from analysis.models import AnalysisResult, EstimatedValue
from analysis.result_contract import build_estimated_result


def test_build_estimated_result_uses_analysis_result_values():
    result = AnalysisResult()
    result.performance.estimated_no_load_rpm = EstimatedValue(22500, "rpm", 0.8)
    result.performance.estimated_torque = EstimatedValue(12.5, "g·cm", 0.7)
    result.performance.estimated_supported_weight = EstimatedValue(130, "g", 0.6)
    result.brush.peak_score = EstimatedValue(0, "score", 0.9)

    values = build_estimated_result(result)

    assert values["estimated_no_load_rpm"] == "22500 rpm"
    assert values["estimated_torque"] == "12.5 g·cm"
    assert values["estimated_supported_weight"] == "130 g"
    assert values["brush_peak_score"] == "0 / 10"


def test_build_estimated_result_without_analysis_result_is_empty():
    values = build_estimated_result(None)
    assert values == {
        "estimated_no_load_rpm": "--",
        "estimated_torque": "--",
        "brush_peak_score": "--",
        "estimated_supported_weight": "--",
    }
