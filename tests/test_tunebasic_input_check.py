"""TuneBasic INPUT-mode contract and limited hardware-check recipe tests."""
from controllers.recipe_engine import RecipeEngine
import pytest

from controllers.breakin_controller import BreakinController


def test_limited_tunebasic_input_check_is_short_and_bidirectional():
    engine = RecipeEngine("config/breakin_recipes.yaml")
    recipe = engine.get("TUNE_BASIC_INPUT_3V_CHECK")

    assert recipe is not None
    assert [phase.name for phase in recipe.phases] == [
        "CHECK_FWD_INPUT_3V", "CHECK_REST_60S", "CHECK_REV_INPUT_3V"
    ]
    assert [phase.direction for phase in recipe.phases] == ["FWD", "FWD", "REV"]
    assert [phase.duration_sec for phase in recipe.phases] == [10, 60, 10]
    forward, rest, reverse = recipe.phases
    assert forward.target_voltage == reverse.target_voltage == 3.0
    assert forward.metadata.get("voltage_control_mode") == "INPUT"
    assert reverse.metadata.get("voltage_control_mode") == "INPUT"
    assert 35 <= forward.pwm_min <= forward.pwm <= forward.pwm_max <= 120
    assert 35 <= reverse.pwm_min <= reverse.pwm <= reverse.pwm_max <= 120
    assert rest.control == "PWM"
    assert rest.pwm == rest.pwm_min == rest.pwm_max == 0


def test_full_tunebasic_3v_stages_use_input_feedback_without_changing_9v_stages():
    engine = RecipeEngine("config/breakin_recipes.yaml")
    recipe = engine.get("TUNE_BASIC")
    phases = {phase.name: phase for phase in recipe.phases}

    assert phases["FWD_3V_START"].metadata.get("voltage_control_mode") == "INPUT"
    assert phases["REV_3V_START"].metadata.get("voltage_control_mode") == "INPUT"
    assert phases["BENCHMARK_3V"].metadata.get("voltage_control_mode") == "INPUT"
    # Full TuneBasic voltage phases now consistently use INPUT feedback, including 9 V holds.
    assert phases["FWD_9V_HOLD"].metadata.get("voltage_control_mode") == "INPUT"
    assert phases["REV_9V_HOLD"].metadata.get("voltage_control_mode") == "INPUT"
    assert phases["FWD_RAMP_3_TO_9V"].metadata.get("voltage_control_mode") == "INPUT"
    assert phases["REV_RAMP_3_TO_9V"].metadata.get("voltage_control_mode") == "INPUT"
    assert phases["FWD_FADEOUT"].metadata.get("voltage_control_mode") == "INPUT"
    assert phases["REV_FADEOUT"].metadata.get("voltage_control_mode") == "INPUT"


class RecordingSerial:
    def __init__(self):
        self.pwm_commands = []
        self.arm_calls = 0
        self.stop_calls = 0

    def arm(self):
        self.arm_calls += 1
        return True

    def set_pwm(self, value):
        self.pwm_commands.append(value)
        return value

    def emergency_stop(self):
        self.stop_calls += 1
        return {"stop_command": True}


def test_limited_recipe_controller_rejects_terminal_fallback_before_arm():
    engine = RecipeEngine("config/breakin_recipes.yaml")
    recipe = engine.get("TUNE_BASIC_INPUT_3V_CHECK")
    recipe.phases[2].metadata["voltage_control_mode"] = "TERMINAL"
    serial = RecordingSerial()
    controller = BreakinController(serial_controller=serial)

    with pytest.raises(RuntimeError, match="both directions require 3.00 V INPUT"):
        controller.start(recipe)

    assert serial.arm_calls == 0
    assert controller.running is False


def test_limited_input_feedback_uses_v4_and_v5_direction_channels():
    engine = RecipeEngine("config/breakin_recipes.yaml")
    recipe = engine.get("TUNE_BASIC_INPUT_3V_CHECK")
    forward, _, reverse = recipe.phases
    serial = RecordingSerial()
    controller = BreakinController(serial_controller=serial)

    controller.current_pwm = 60
    controller._voltage_control(forward, {
        "voltage1": 2.0, "voltage2": 9.0, "motor_voltage": 3.0,
    })
    assert controller.current_pwm == 80
    assert serial.pwm_commands[-1] == 80

    controller.current_pwm = 60
    controller._voltage_control(reverse, {
        "voltage1": 1.0, "voltage2": 4.0, "motor_voltage": -3.0,
    })
    assert controller.current_pwm == 40
    assert serial.pwm_commands[-1] == 40


def test_unknown_feedback_mode_fails_closed_instead_of_using_terminal_voltage():
    from controllers.recipe import BreakinPhase

    serial = RecordingSerial()
    controller = BreakinController(serial_controller=serial)
    controller.running = True
    controller.current_pwm = 60
    phase = BreakinPhase(
        name="BAD_MODE", duration_sec=10, pwm=60, direction="REV",
        control="VOLTAGE", target_voltage=3.0, pwm_min=35, pwm_max=120,
        metadata={"voltage_control_mode": "AUTO_FALLBACK"},
    )
    measurement = {"motor_voltage": -3.0, "voltage1": 1.0, "voltage2": None}
    controller._voltage_control(phase, measurement)
    controller._voltage_control(phase, measurement)
    with pytest.raises(RuntimeError, match="3 consecutive invalid control samples"):
        controller._voltage_control(phase, measurement)
    assert serial.stop_calls == 1
    assert serial.pwm_commands == []



def test_supervised_stop_proof_recipe_requires_active_fwd_input_and_external_evidence():
    engine = RecipeEngine("config/breakin_recipes.yaml")
    recipe = engine.get("STOP_PROOF_3V_INPUT")

    assert recipe is not None
    assert recipe.family == "SAFETY_VERIFICATION"
    assert len(recipe.phases) == 1
    phase = recipe.phases[0]
    assert phase.name == "STOP_PROOF_FWD_INPUT_3V"
    assert phase.direction == "FWD"
    assert phase.control == "VOLTAGE"
    assert phase.target_voltage == 3.0
    assert phase.metadata.get("voltage_control_mode") == "INPUT"
    assert 35 <= phase.pwm_min <= phase.pwm <= phase.pwm_max <= 120
    assert phase.duration_sec == 10
    assert phase.metadata.get("external_rpm_observation_required") is True
    assert phase.metadata.get("synchronized_stop_evidence_required") is True
    assert "Press the physical/UI STOP while the motor is visibly rotating" in phase.metadata.get("operator_action", "")
