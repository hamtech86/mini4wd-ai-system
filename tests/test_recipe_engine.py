"""MOTOR_BREAKIN_V3 recipe catalog tests."""

from controllers.recipe_engine import RecipeEngine


def test_recipe_catalog_loads():
    engine = RecipeEngine()
    assert engine.version == "2.0"
    assert set(engine.names()) == {
        "ATOMIC_25K",
        "TORQUE_TUNE_23K",
        "TUNE_OPTIMIZED",
        "DASH_OPTIMIZED",
        "MOTOR_DRIVE_TEST",
    }


def test_aliases_and_benchmark():
    engine = RecipeEngine()
    assert engine.get("TORQUE_TUNE").name == "TORQUE_TUNE_23K"
    assert engine.get("POWER_DASH").name == "DASH_OPTIMIZED"
    assert engine.get("BALANCE").name == "TUNE_OPTIMIZED"
    assert engine.benchmark()["target_voltage"] == 3.0


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
