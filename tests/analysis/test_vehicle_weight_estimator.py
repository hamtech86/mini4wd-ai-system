from analysis.vehicle_weight_estimator import (
    VehicleAssumptions,
    estimate_torque_equivalent_weight,
)


def test_tt2_nominal_torque_equivalent_weight():
    result = estimate_torque_equivalent_weight(
        210.0,
        VehicleAssumptions(
            tire_diameter_mm=24.0,
            gear_ratio=3.5,
            drivetrain_efficiency=0.85,
        ),
    )

    assert round(result.wheel_torque_gcm, 3) == 624.75
    assert round(result.torque_equivalent_weight_g, 3) == 520.625


def test_default_assumptions_are_24mm_and_3_5_to_1():
    result = estimate_torque_equivalent_weight(210.0)
    assert result.torque_equivalent_weight_g == 520.625


def test_negative_torque_is_rejected():
    try:
        estimate_torque_equivalent_weight(-1.0)
    except ValueError:
        pass
    else:
        raise AssertionError("negative torque must raise ValueError")
