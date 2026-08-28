"""Hardware-independent tests for condition-based benchmark start."""

from controllers.benchmark_controller import BenchmarkBreakinController


def _controller():
    return BenchmarkBreakinController(serial_controller=None)


def test_stable_sample_requires_start_voltage_and_current():
    controller = _controller()
    controller.current_pwm = 60
    phase = type("Phase", (), {"pwm_min": 35})()

    assert controller._stable_sample_ok(
        {"motor_voltage": 1.50, "current_avg": 0.20}, phase
    )
    assert controller._stable_sample_ok(
        {"motor_voltage": 2.60, "current_avg": 0.20}, phase
    )
    assert not controller._stable_sample_ok(
        {"motor_voltage": 1.49, "current_avg": 0.20}, phase
    )
    assert not controller._stable_sample_ok(
        {"motor_voltage": 2.60, "current_avg": 0.01}, phase
    )


def test_stable_window_rejects_large_voltage_or_pwm_change():
    controller = _controller()
    samples = [
        (0.0, {"motor_voltage": 1.50, "pwm": 60}),
        (0.1, {"motor_voltage": 1.54, "pwm": 62}),
        (0.2, {"motor_voltage": 1.52, "pwm": 61}),
    ]
    assert controller._stable_window_ok(samples)

    voltage_bad = samples + [(0.3, {"motor_voltage": 1.70, "pwm": 61})]
    assert not controller._stable_window_ok(voltage_bad)

    pwm_bad = samples + [(0.3, {"motor_voltage": 1.52, "pwm": 70})]
    assert not controller._stable_window_ok(pwm_bad)
