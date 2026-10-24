"""Regression coverage for the current TuneBasic/STD-I execution contract.

These tests are hardware-independent. They do not authorize full TuneBasic motion;
Issue #98 remains the controlling safety gate.
"""
from pathlib import Path

import pytest

import controllers.breakin_controller as breakin_controller_module
from controllers.breakin_controller import BreakinController
from controllers.recipe_engine import RecipeEngine
from controllers.recipe import BreakinPhase


class NoCommandSerial:
    def __init__(self):
        self.commands = []

    def forward(self):
        self.commands.append("FWD")

    def reverse(self):
        self.commands.append("REV")

    def set_pwm(self, pwm):
        self.commands.append(f"PWM:{pwm}")

    def emergency_stop(self):
        self.commands.append("STOP")


@pytest.fixture
def recipe_engine():
    config = Path(__file__).resolve().parents[1] / "config" / "breakin_recipes.yaml"
    return RecipeEngine(str(config))


def test_tunebasic_has_expected_bidirectional_input_sequence(recipe_engine):
    recipe = recipe_engine.get("TUNE_BASIC")
    assert recipe is not None

    assert [phase.name for phase in recipe.phases] == [
        "FWD_3V_START",
        "FWD_RAMP_3_TO_9V",
        "FWD_9V_HOLD",
        "FWD_FADEOUT",
        "REST_FWD",
        "REV_3V_START",
        "REV_RAMP_3_TO_9V",
        "REV_9V_HOLD",
        "REV_FADEOUT",
        "REST_REV",
        "BENCHMARK_3V",
    ]
    assert [phase.duration_sec for phase in recipe.phases] == [
        30, 60, 60, 30, 60, 30, 60, 60, 30, 60, 30
    ]
    for phase in recipe.phases:
        if phase.control in {"VOLTAGE", "VOLTAGE_RAMP"}:
            assert str(phase.metadata.get("voltage_control_mode", "")).upper() == "INPUT"
    assert recipe.phases[0].direction == "FWD"
    assert recipe.phases[5].direction == "REV"
    assert recipe.phases[-1].direction == "FWD"



def test_limited_tunebasic_check_has_a_real_rest_phase_between_directions(recipe_engine):
    recipe = recipe_engine.get("TUNE_BASIC_INPUT_3V_CHECK")
    assert recipe is not None
    assert [phase.name for phase in recipe.phases] == [
        "CHECK_FWD_INPUT_3V",
        "CHECK_REST_AFTER_FWD",
        "CHECK_REV_INPUT_3V",
    ]
    rest = recipe.phases[1]
    assert rest.control == "PWM"
    assert rest.pwm == 0
    assert rest.duration_sec == 60
    assert rest.direction == "FWD"
    assert recipe.phases[0].duration_sec == 10
    assert recipe.phases[2].duration_sec == 10
    assert recipe.phases[0].direction == "FWD"
    assert recipe.phases[2].direction == "REV"


def test_full_tunebasic_remains_blocked_before_any_motor_command(recipe_engine):
    serial = NoCommandSerial()
    controller = BreakinController(serial_controller=serial)
    recipe = recipe_engine.get("TUNE_BASIC")

    with pytest.raises(RuntimeError, match="Issue #98"):
        controller.start(recipe)

    assert serial.commands == []
    assert controller.running is False


def test_tunebasic_9v_ramps_and_holds_have_explicit_input_targets(recipe_engine):
    recipe = recipe_engine.get("TUNE_BASIC")
    by_name = {phase.name: phase for phase in recipe.phases}

    assert by_name["FWD_RAMP_3_TO_9V"].start_voltage == 3.0
    assert by_name["FWD_RAMP_3_TO_9V"].end_voltage == 9.0
    assert by_name["REV_RAMP_3_TO_9V"].start_voltage == 3.0
    assert by_name["REV_RAMP_3_TO_9V"].end_voltage == 9.0
    assert by_name["FWD_9V_HOLD"].target_voltage == 9.0
    assert by_name["REV_9V_HOLD"].target_voltage == 9.0
    assert by_name["FWD_FADEOUT"].start_voltage == 9.0
    assert by_name["FWD_FADEOUT"].end_voltage == 0.0
    assert by_name["REV_FADEOUT"].start_voltage == 9.0
    assert by_name["REV_FADEOUT"].end_voltage == 0.0
    assert by_name["FWD_RAMP_3_TO_9V"].pwm_max == 245
    assert by_name["REV_RAMP_3_TO_9V"].pwm_max == 245
    assert by_name["FWD_9V_HOLD"].pwm_max == 245
    assert by_name["REV_9V_HOLD"].pwm_max == 245


def test_tunebasic_fixed_voltage_phase_uses_shared_timed_voltage_helper(monkeypatch):
    calls = []

    def fake_timed_voltage_phase(controller, phase, duration, **kwargs):
        calls.append((controller, phase, duration, kwargs))

    monkeypatch.setattr(
        breakin_controller_module, "run_timed_voltage_phase", fake_timed_voltage_phase
    )
    controller = BreakinController(serial_controller=NoCommandSerial())
    phase = BreakinPhase(
        name="FWD_3V_START",
        duration_sec=30,
        pwm=80,
        direction="FWD",
        control="VOLTAGE",
        target_voltage=3.0,
        pwm_min=35,
        pwm_max=120,
        metadata={"voltage_control_mode": "INPUT"},
    )

    controller._execute_standard_phase(phase, resume_elapsed=4.0)

    assert len(calls) == 1
    assert calls[0][0] is controller
    assert calls[0][1] is phase
    assert calls[0][2] == 30
    assert calls[0][3] == {"save_checkpoint": True, "initial_elapsed": 4.0}


def test_tunebasic_ramp_checks_safety_before_changing_pwm(monkeypatch):
    controller = BreakinController(serial_controller=NoCommandSerial())
    phase = BreakinPhase(
        name="FWD_RAMP_3_TO_9V", duration_sec=60, pwm=80,
        direction="FWD", control="VOLTAGE_RAMP", start_voltage=3.0,
        end_voltage=9.0, pwm_min=35, pwm_max=245,
        metadata={"voltage_control_mode": "INPUT"},
    )
    controller.running = True
    controller.phase_started_at = 0.0
    controller.phase_manager = type("PhaseManagerStub", (), {"current_index": lambda self: 1})()
    monkeypatch.setattr(controller, "_effective_elapsed", lambda: 0.1)
    monkeypatch.setattr(controller, "_collect_measurement", lambda _phase: {"current1": 5.2})
    monkeypatch.setattr(controller, "_safety_violation", lambda _measurement: "SAFETY: current 5.20A >= 5.00A")
    ramp_calls = []
    monkeypatch.setattr(controller, "_voltage_ramp_control", lambda _phase: ramp_calls.append(_phase.name))
    stop_calls = []
    def fake_emergency_stop():
        stop_calls.append(True)
        controller.running = False
        return {"serial_stop_attempted": True}
    monkeypatch.setattr(controller, "emergency_stop", fake_emergency_stop)

    controller._execute_standard_phase(phase)

    assert ramp_calls == []
    assert stop_calls == [True]
    assert controller.abort_reason == "SAFETY: current 5.20A >= 5.00A"
