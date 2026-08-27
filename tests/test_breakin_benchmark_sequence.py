from controllers.breakin_controller import BreakinController


class FakeSerial:
    def __init__(self):
        self.commands = []

    def forward(self):
        self.commands.append("forward")

    def set_pwm(self, pwm):
        self.commands.append(("pwm", pwm))

    def stop_breakin(self):
        self.commands.append("stop")


class FakeMeasurementManager:
    def __init__(self):
        self.calls = 0

    def collect(self):
        self.calls += 1
        return {
            "motor_voltage": 3.0,
            "current1": 0.1,
            "current2": 0.1,
            "motor_temperature": 25.0,
            "rpm": 1000.0,
        }


class FakeAnalysisEngine:
    def __init__(self):
        self.inputs = []

    def analyze(self, measurement):
        self.inputs.append(measurement)
        return measurement


def test_benchmark_defaults_to_30_seconds():
    controller = BreakinController(FakeSerial())
    assert controller.BENCHMARK_DURATION_SEC == 30.0
    assert controller.BENCHMARK_SETTLE_SEC == 1.0


def test_benchmark_settling_samples_are_not_analysis_input(monkeypatch):
    serial = FakeSerial()
    measurements = FakeMeasurementManager()
    analysis = FakeAnalysisEngine()
    controller = BreakinController(
        serial,
        measurement_manager=measurements,
        analysis_engine=analysis,
    )

    times = iter([0.0, 0.1, 1.0, 1.1, 1.2, 1.3])
    monkeypatch.setattr("controllers.breakin_controller.time.time", lambda: next(times))
    monkeypatch.setattr("controllers.breakin_controller.time.sleep", lambda _seconds: None)

    result = controller.benchmark_3v(duration_sec=0.2)

    assert result
    assert controller.measurements == controller.benchmark_measurements
    assert all(item["phase"].name == "BENCHMARK_3V_30S" for item in controller.measurements)
    assert len(analysis.inputs) == len(controller.benchmark_measurements)
    assert len(controller.measurements) < measurements.calls
