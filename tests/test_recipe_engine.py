"""MOTOR_BREAKIN_V3 recipe catalog tests."""

from controllers.recipe_engine import RecipeEngine


def test_recipe_catalog_loads():
    engine = RecipeEngine()
    assert engine.version == "2.1"
    assert set(engine.names()) >= {
        "ATOMIC_25K",
        "TORQUE_TUNE_23K",
        "TUNE_OPTIMIZED",
        "DASH_OPTIMIZED",
        "TUNE_BASIC",
        "FINISH_BRUSH_PEAK_2V",
    }


def test_aliases_and_benchmark():
    engine = RecipeEngine()
    assert engine.get("TORQUE_TUNE").name == "TORQUE_TUNE_23K"
    assert engine.get("POWER_DASH").name == "DASH_OPTIMIZED"
    assert engine.get("BALANCE").name == "TUNE_OPTIMIZED"
    assert engine.get("TUNE_BASIC_RECIPE").name == "TUNE_BASIC"
    assert engine.get("FINISH_RECIPE").name == "FINISH_BRUSH_PEAK_2V"
    assert engine.benchmark()["target_voltage"] == 3.0
    assert engine.benchmark()["duration_sec"] == 30


def test_tune_basic_shape():
    engine = RecipeEngine()
    recipe = engine.get("TUNE_BASIC")
    assert recipe.phases[0].target_voltage == 3.0
    assert recipe.phases[1].control == "VOLTAGE_RAMP"
    assert recipe.phases[1].start_voltage == 3.0
    assert recipe.phases[1].end_voltage == 9.0
    # All TuneBasic voltage-controlled phases use the direction-specific INPUT sensor.
    for index in (0, 1, 2, 3, 5, 6, 7, 8, 10):
        assert recipe.phases[index].metadata["voltage_control_mode"] == "INPUT"
    assert recipe.phases[2].target_voltage == 9.0
    assert recipe.phases[4].pwm == 0
    assert recipe.phases[5].direction == "REV"
    assert recipe.phases[-1].target_voltage == 3.0
    assert recipe.phases[-1].duration_sec == 30


def test_finish_recipe_shape():
    engine = RecipeEngine()
    recipe = engine.get("FINISH_BRUSH_PEAK_2V")
    phase = recipe.phases[0]
    assert phase.control == "BRUSH_PEAK_APPROACH"
    assert phase.target_voltage == 2.0
    assert phase.peak_margin_ratio == 0.05
    assert phase.max_duration_sec == 1800


def test_recipe_targets_and_brushes():
    engine = RecipeEngine()
    atomic = engine.get("ATOMIC_25K")
    torque = engine.get("TORQUE_TUNE_23K")
    dash = engine.get("DASH_OPTIMIZED")
    assert atomic.target_rpm == 25000
    assert torque.target_rpm == 23000
    assert atomic.brush == "COPPER"
    assert torque.brush == "COPPER"
    assert dash.brush == "CARBON"
    assert atomic.phases[-1].control == "VOLTAGE"
    assert atomic.phases[-1].target_voltage == 3.0


def test_reverse_input_mode_is_preserved_through_voltage_ramp():
    from controllers.breakin_controller import BreakinController

    engine = RecipeEngine()
    phase = engine.get("TUNE_BASIC").phases[6]  # REV 3-to-9 V ramp
    controller = BreakinController.__new__(BreakinController)
    controller.current_pwm = 80
    controller.phase_started_at = __import__("time").time()
    controller.phase_elapsed_before_pause = 0.0
    controller.paused = False
    controller.measurements = [{
        "voltage1": 0.5,
        "voltage2": 2.0,
        "motor_voltage": -2.5,
    }]
    controller.serial = type("Serial", (), {"set_pwm": lambda self, pwm: None})()

    controller._voltage_ramp_control(phase)

    # Near ramp start, target is ~3 V. INPUT must use V5=2.0 V, not |motor_voltage|=2.5 V.
    assert controller.current_pwm >= 89
