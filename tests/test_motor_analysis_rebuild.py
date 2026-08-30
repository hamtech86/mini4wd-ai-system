from analysis.models import FeatureSet
from analysis.performance import PerformanceAnalysis


def test_cal7570_four_mandatory_outputs():
    features = FeatureSet(
        average_voltage=3.009,
        average_current=0.084,
        pwm=37,
        brush_peak_current=1.498,
    )
    spec = {
        "nominal_voltage": 2.4,
        "nominal_rpm": 15000,
        "nominal_current_ma": 1400,
        "nominal_torque_gcm": 220,
    }

    result = PerformanceAnalysis().analyze(features, spec)

    assert result.estimated_rpm_3v.value > 0
    assert result.estimated_rpm_28v.value > 0
    assert result.estimated_torque_3v.value > 0
    assert result.estimated_torque_28v.value > 0
    assert result.brush_peak_life_cycle.value == 100.0
    assert result.estimated_supported_weight.value > 0
    assert result.estimated_rpm.value == result.estimated_rpm_3v.value
    assert result.estimated_torque.value == result.estimated_torque_3v.value


if __name__ == "__main__":
    test_cal7570_four_mandatory_outputs()
    print("Cal7570 motor-analysis rebuild: PASS")
