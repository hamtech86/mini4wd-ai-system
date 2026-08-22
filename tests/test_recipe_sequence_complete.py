from controllers.recipe import BreakinPhase, BreakinRecipe
from controllers.sequence import SequenceDefinition
from controllers.sequence_executor import SequenceExecutor


class Adapter:
    def __init__(self):
        self.metric = {}
        self.started = []
        self.stopped = []

    def start_sequence(self, sequence):
        self.started.append(sequence.sequence_id)

    def stop_sequence(self, sequence):
        self.stopped.append(sequence.sequence_id)

    def read_metric(self, metric):
        return self.metric.get(metric)


def make_recipe():
    return BreakinRecipe(
        name="TEST",
        version="2.1",
        phases=[
            BreakinPhase("A", duration_sec=1, pwm=64),
            BreakinPhase("B", duration_sec=10, pwm=80, conditions=[{"metric": "temperature", "operator": "<=", "value": 30}]),
            BreakinPhase("C", duration_sec=1, pwm=96),
        ],
    )


def test_disabled_rows_are_skipped_before_execution():
    adapter = Adapter()
    executor = SequenceExecutor(adapter=adapter)
    executor.load_recipe(make_recipe(), enabled_ids={"01_A", "03_C"})
    executor.start(instance_id=1)
    executor.execute_current(now=100)
    executor.execute_current(now=101.1)
    executor.execute_current(now=102.2)
    assert executor.results[1].status == "SKIPPED"
    assert executor.is_complete()
    assert adapter.started == ["01_A", "03_C"]


def test_condition_ends_sequence_early():
    adapter = Adapter()
    adapter.metric["temperature"] = 29
    executor = SequenceExecutor(adapter=adapter)
    executor.load_recipe(make_recipe())
    executor.start(instance_id=1)
    executor.execute_current(now=100)
    executor.execute_current(now=101.1)
    executor.execute_current(now=101.2)
    assert executor.results[1].status == "COMPLETE"
    assert executor.results[1].reason == "condition_met"


def test_pause_stops_and_resume_preserves_elapsed_time():
    adapter = Adapter()
    executor = SequenceExecutor(adapter=adapter)
    executor.load_recipe(make_recipe())
    executor.start(instance_id=1)
    executor.execute_current(now=100)
    executor.pause()
    assert executor.paused
    elapsed = executor.state.paused_elapsed_sec
    assert elapsed >= 0
    assert adapter.stopped == ["01_A"]
    assert executor.resume()
    assert not executor.paused
    assert executor.results[0].started_at is not None


def test_sequence_from_phase_preserves_conditions():
    phase = BreakinPhase("COND", duration_sec=20, conditions=[{"metric": "brush_peak", "operator": ">=", "value": 1.2}])
    recipe = BreakinRecipe("COND", [phase])
    sequence = recipe.sequences()[0]
    assert sequence.conditions[0].metric == "brush_peak"
    assert sequence.conditions[0].operator == ">="
