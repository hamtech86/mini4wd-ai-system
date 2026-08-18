from analysis.weight_suitability import WeightSuitabilityAnalysis


def test_weight_suitability_profile_range_and_step():
    analysis = WeightSuitabilityAnalysis(
        {
            "performance": {
                "weight_suitability": {
                    "min_weight_g": 115,
                    "max_weight_g": 155,
                    "step_g": 5,
                    "reference_torque_gcm": 0.83,
                    "reference_weight_g": 130,
                    "comparison_weight_g": 140,
                }
            }
        }
    )

    result = analysis.analyze(0.83)

    assert [point.weight_g for point in result.points] == [
        115.0, 120.0, 125.0, 130.0, 135.0, 140.0, 145.0, 150.0, 155.0
    ]
    assert result.current_reference_g == 130.0
    assert result.comparison_weight_g == 140.0
    assert result.points[3].required_torque_gcm == 0.83
    assert result.points[5].required_torque_gcm > result.points[3].required_torque_gcm


def test_weight_suitability_margin_statuses_are_derived_from_torque():
    analysis = WeightSuitabilityAnalysis(
        {
            "performance": {
                "weight_suitability": {
                    "min_weight_g": 115,
                    "max_weight_g": 155,
                    "step_g": 5,
                    "reference_torque_gcm": 0.83,
                    "reference_weight_g": 130,
                    "margin_recommended": 1.15,
                    "margin_acceptable": 1.00,
                    "margin_limit": 0.90,
                }
            }
        }
    )

    result = analysis.analyze(0.83)
    by_weight = {point.weight_g: point for point in result.points}

    assert by_weight[115.0].status == "RECOMMENDED"
    assert by_weight[130.0].status == "ACCEPTABLE"
    assert by_weight[140.0].status == "LIMIT"
    assert by_weight[155.0].status == "UNSUITABLE"
