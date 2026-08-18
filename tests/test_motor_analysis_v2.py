from analysis.performance import PerformanceAnalysis
from analysis.required_torque import RequiredTorqueAnalysis, VehicleSpec
from analysis.models import FeatureSet


def test_hd_pro_nominal_benchmark_is_50():
    analysis = PerformanceAnalysis({
        "performance": {
            "rpm": {"max_voltage_ratio": 1.15},
            "index": {"log_sigma": 0.10},
            "weight": {"torque_gain": 12.0},
        }
    })
    model = {
        "motor_model_id": "HD_PRO",
        "name": "ハイパーダッシュPro",
        "nominal_rpm": 24000,
        "nominal_current_ma": 1600,
        "nominal_torque_gcm": 190,
    }
    features = FeatureSet(average_voltage=3.0, average_current=1.6, quality=1.0)
    result = analysis.analyze(features, motor_model=model, benchmark_model=model)
    assert abs(result.performance_index.value - 50.0) < 1e-6
    assert abs(result.estimated_torque.value - 190.0) < 1e-6
    assert abs(result.estimated_no_load_rpm.value - 24000.0) < 1e-6


def test_required_torque_increases_with_weight():
    analysis = RequiredTorqueAnalysis()
    light = analysis.calculate(VehicleSpec(weight_g=100))
    heavy = analysis.calculate(VehicleSpec(weight_g=150))
    assert heavy.required_torque_gcm.value > light.required_torque_gcm.value


def test_grade_adds_required_torque():
    analysis = RequiredTorqueAnalysis()
    flat = analysis.calculate(VehicleSpec(weight_g=130, grade_angle_deg=0))
    hill = analysis.calculate(VehicleSpec(weight_g=130, grade_angle_deg=10))
    assert hill.required_torque_gcm.value > flat.required_torque_gcm.value
