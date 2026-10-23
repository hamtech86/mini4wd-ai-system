"""TuneBasic INPUT-mode contract and limited hardware-check recipe tests."""
from controllers.recipe_engine import RecipeEngine


def test_limited_tunebasic_input_check_is_short_and_bidirectional():
    engine = RecipeEngine("config/breakin_recipes.yaml")
    recipe = engine.get("TUNE_BASIC_INPUT_3V_CHECK")

    assert recipe is not None
    assert [phase.direction for phase in recipe.phases] == ["FWD", "REV"]
    assert [phase.duration_sec for phase in recipe.phases] == [10, 10]
    assert all(phase.target_voltage == 3.0 for phase in recipe.phases)
    assert all(phase.metadata.get("voltage_control_mode") == "INPUT" for phase in recipe.phases)
    assert all(35 <= phase.pwm_min <= phase.pwm_max <= 120 for phase in recipe.phases)


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
