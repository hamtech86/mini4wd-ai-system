from analysis.models import FeatureSet
from analysis.performance import PerformanceAnalysis


def _config():
    return {
        "performance": {
            "rpm": {"default_confidence": 0.5},
            "torque": {"current_gain": 0.0, "default_confidence": 0.0},
            "weight_suitability": {
                "min_weight_g": 115,
                "max_weight_g": 155,
                "step_g": 5,
                "reference_torque_gcm": 0.83,
                "reference_weight_g": 130,
                "comparison_weight_g": 140,
                "tire_diameter_mm": 24,
                "gear_ratio": 3.5,
                "margin_recommended": 1.15,
                "margin_acceptable": 1.00,
                "margin_limit": 0.90,
                "default_confidence": 0.40,
            },
        }
    }


def test_supported_weight_uses_motor_model_capability_not_breakin_current():
    analysis = PerformanceAnalysis(_config())
    model = {
        "nominal_torque_gcm": 0.83,
        "nominal_current_ma": 1200,
        "nominal_rpm": 23000,
        "data_confidence": 0.9,
    }

    low_current = analysis.analyze(
        FeatureSet(rpm=23000, average_current=0.10), motor_model=model
    )
    high_current = analysis.analyze(
        FeatureSet(rpm=23000, average_current=4.0), motor_model=model
    )

    assert low_current.estimated_torque.value != high_current.estimated_torque.value
    assert low_current.estimated_supported_weight.value == 130.0
    assert high_current.estimated_supported_weight.value == 130.0
    assert low_current.weight_suitability is not None
    assert [p.weight_g for p in low_current.weight_suitability.points] == [
        115.0, 120.0, 125.0, 130.0, 135.0, 140.0, 145.0, 150.0, 155.0
    ]


def test_supported_weight_increases_only_when_motor_model_torque_increases():
    analysis = PerformanceAnalysis(_config())
    weak_model = {
        "nominal_torque_gcm": 0.83,
        "nominal_current_ma": 1200,
        "data_confidence": 0.9,
    }
    strong_model = {
        "nominal_torque_gcm": 1.50,
        "nominal_current_ma": 1200,
        "data_confidence": 0.9,
    }

    weak = analysis.analyze(FeatureSet(average_current=0.1), motor_model=weak_model)
    strong = analysis.analyze(FeatureSet(average_current=0.1), motor_model=strong_model)

    assert weak.estimated_supported_weight.value == 130.0
    assert strong.estimated_supported_weight.value == 155.0
