from analysis.vehicle_weight import estimate_vehicle_weight


def test_reference_torque_maps_to_reference_vehicle_weight():
    estimate = estimate_vehicle_weight(0.83)
    assert estimate.center_g == 130.0
    assert estimate.minimum_g == 97.5
    assert estimate.maximum_g == 162.5
    assert estimate.tire_diameter_mm == 24.0
    assert estimate.gear_ratio == 3.5


def test_weight_scales_with_torque():
    estimate = estimate_vehicle_weight(1.66)
    assert estimate.center_g == 260.0
    assert estimate.minimum_g == 195.0
    assert estimate.maximum_g == 325.0
