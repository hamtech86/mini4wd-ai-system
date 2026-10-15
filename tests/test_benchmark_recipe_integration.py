from types import SimpleNamespace

import pytest

import app.main as main_module
import controllers.motor_benchmark as motor_benchmark
from controllers.breakin_controller import BreakinController
from controllers.recipe_engine import RecipeEngine
from controllers.recipe import BreakinPhase


RECIPES = {
    "STD-T": ("STANDARD", "TERMINAL", 2),
    "Full-T": ("FULL_PACKAGE", "TERMINAL", 6),
    "STD-I": ("STANDARD", "INPUT", 2),
    "Full-I": ("FULL_PACKAGE", "INPUT", 6),
}


class FakeCheck:
    def __init__(self, checked=True):
        self._checked = checked

    def isChecked(self):
        return self._checked


class FakeSerial:
    def __init__(self):
        self.commands = []

    def require_identified_device(self):
        return None

    def reset_raw_log(self):
        self.commands.append("RESET_RAW_LOG")

    def forward(self):
        self.commands.append("FORWARD")

    def set_pwm(self, value):
        self.commands.append(f"PWM={value}")

    def stop_breakin(self):
        self.commands.append("STOP")


@pytest.mark.parametrize("recipe_name", RECIPES)
def test_ui_recipe_selection_routes_selected_recipe_to_benchmark_start(recipe_name):
    captured = []
    window = SimpleNamespace(
        recipe=SimpleNamespace(itemData=lambda index: recipe_name, currentData=lambda: recipe_name),
        _load_benchmark_sequence=lambda name: setattr(
            window, "loaded_recipe", name
        ),
        _load_recipe_sequence=lambda name: setattr(window, "loaded_recipe", name),
        _current_recipe_name=lambda: recipe_name,
        sequence_checks=[(recipe_name, FakeCheck(True))],
        _start_benchmark=lambda name: captured.append(name),
        sequence_status=SimpleNamespace(setText=lambda value: None),
    )

    main_module.MainWindow._recipe_selection_changed(window, 0)
    assert window.loaded_recipe == recipe_name

    main_module.MainWindow._execute_selected_sequences(window)
    assert captured == [recipe_name]


@pytest.mark.parametrize(
    ("recipe_name", "expected_type", "expected_mode", "phase_count"),
    [(name, *spec) for name, spec in RECIPES.items()],
)
def test_recipe_build_preserves_type_mode_phase_and_record_metadata(
    monkeypatch, recipe_name, expected_type, expected_mode, phase_count
):
    engine = RecipeEngine()
    recipe = engine.get_benchmark(recipe_name)
    assert recipe.name == recipe_name
    assert recipe.benchmark_type == expected_type
    assert recipe.voltage_control_mode == expected_mode
    assert len(recipe.phases) == phase_count
    assert all(phase.metadata["recipe"] == recipe_name for phase in recipe.phases)
    assert all(phase.metadata["benchmark_type"] == expected_type for phase in recipe.phases)
    assert all(phase.metadata["voltage_control_mode"] == expected_mode for phase in recipe.phases)

    serial = FakeSerial()
    controller = BreakinController(serial)
    controller._require_identified_device = lambda: None
    observed_phases = []
    monkeypatch.setattr(motor_benchmark, "_prepare_3v", lambda self, phase, duration=2.0: observed_phases.append(phase) or True)
    monkeypatch.setattr(motor_benchmark, "_timed_voltage", lambda self, phase, duration: observed_phases.append(phase) or True)
    monkeypatch.setattr(motor_benchmark, "_timed_pwm", lambda self, phase, duration: observed_phases.append(phase) or True)

    def capture_finish(phases):
        controller.captured_execution_phases = list(phases)
        controller.running = False

    monkeypatch.setattr(BreakinController, "_finish_benchmark", lambda self, phases: capture_finish(phases))
    result = controller.run_benchmark(recipe_name=recipe_name, instance_id=11)

    assert result == []
    assert controller.active_recipe_name == recipe_name
    assert controller.benchmark_type == expected_type
    assert controller.voltage_control_mode == expected_mode
    assert controller.active_instance_id == 11
    assert len(controller.captured_execution_phases) == phase_count
    assert all(phase.metadata["recipe"] == recipe_name for phase in controller.captured_execution_phases)
    assert all(phase.metadata["benchmark_type"] == expected_type for phase in controller.captured_execution_phases)
    assert all(phase.metadata["voltage_control_mode"] == expected_mode for phase in controller.captured_execution_phases)


@pytest.mark.parametrize(
    ("recipe_name", "expected_mode"),
    [("STD-T", "TERMINAL"), ("Full-T", "TERMINAL"), ("STD-I", "INPUT"), ("Full-I", "INPUT")],
)
def test_each_recipe_mode_drives_expected_feedback_and_pwm_decision(recipe_name, expected_mode):
    recipe = RecipeEngine().get_benchmark(recipe_name)
    controller = BreakinController(FakeSerial())
    controller.voltage_control_mode = recipe.voltage_control_mode
    controller.current_pwm = 60
    phase = BreakinPhase(
        "FWD_CHECK", 1, 60, "FWD", "VOLTAGE", 3.0, pwm_min=35, pwm_max=120
    )
    measurement = {
        "direction": "FWD",
        "voltage1": 2.5,
        "voltage2": 0.4,
        "motor_voltage": 2.5,
    }

    controller._voltage_control(phase, measurement)

    assert controller.voltage_control_mode == expected_mode
    assert controller.current_pwm == 70
    assert controller.serial.commands[-1] == "PWM=70"



def test_explicit_full_i_recipe_is_not_overwritten_by_legacy_full_package_alias():
    controller = BreakinController(FakeSerial())
    controller._require_identified_device = lambda: None

    motor_benchmark._begin(
        controller,
        "FULL_PACKAGE",
        voltage_control_mode="INPUT",
        recipe_name="Full-I",
        instance_id=11,
    )

    assert controller.active_recipe_name == "Full-I"
    assert controller.benchmark_type == "FULL_PACKAGE"
    assert controller.voltage_control_mode == "INPUT"
    assert controller.total_phases == 6
