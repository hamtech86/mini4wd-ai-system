from analysis.weight_suitability import WeightSuitabilityAnalysis


def test_weight_profile_covers_115_to_155g():
    analyzer = WeightSuitabilityAnalysis({"performance": {"weight_suitability": {}}})
    result = analyzer.analyze(20.0)
    assert [p.weight_g for p in result.points] == list(range(115, 156, 5))
    assert result.current_reference_g == 130.0
    assert result.comparison_weight_g == 140.0


def test_required_torque_scales_with_vehicle_weight():
    analyzer = WeightSuitabilityAnalysis({"performance": {"weight_suitability": {}}})
    t130 = analyzer.required_motor_torque(130.0)
    t140 = analyzer.required_motor_torque(140.0)
    assert t140 > t130
    assert abs(t140 / t130 - 140.0 / 130.0) < 1e-9


def test_margin_decreases_with_added_weight():
    analyzer = WeightSuitabilityAnalysis({"performance": {"weight_suitability": {}}})
    result = analyzer.analyze(20.0)
    margins = {p.weight_g: p.torque_margin for p in result.points}
    assert margins[140.0] < margins[130.0]
    assert margins[155.0] < margins[140.0]
