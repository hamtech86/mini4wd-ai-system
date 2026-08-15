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
