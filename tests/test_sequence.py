from controllers.recipe import BreakinPhase, BreakinRecipe
from controllers.sequence import ConditionDefinition, SequenceDefinition


def test_recipe_exposes_ordered_sequences_without_changing_phases():
    recipe = BreakinRecipe(
        "TEST",
        [
            BreakinPhase("ONE", duration_sec=10, pwm=64, direction="FWD"),
            BreakinPhase("TWO", duration_sec=20, pwm=80, direction="REV"),
        ],
    )

    sequences = recipe.sequences()

    assert [item.order for item in sequences] == [1, 2]
    assert [item.command for item in sequences] == ["FWD", "FWD"]
    assert sequences[0].sequence_id == "01_ONE"
    assert sequences[1].direction == "REV"
    assert sequences[0].duration_sec == 10
    assert recipe.phases[0].pwm == 64


def test_sequence_can_be_disabled_for_future_ui_skip_support():
    item = SequenceDefinition(
        sequence_id="02_REST",
        order=2,
        command="REST",
        enabled=False,
        duration_sec=60,
    )
    assert item.enabled is False
    assert item.command == "REST"


def test_condition_definition_validates_vocabulary():
    condition = ConditionDefinition("temperature", "<=", 40.0)
    assert condition.metric == "temperature"
    assert condition.group == "ALL"
