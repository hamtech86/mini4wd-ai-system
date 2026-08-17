from controllers.recipe import BreakinPhase, BreakinRecipe
from controllers.sequence_executor import SequenceExecutor


class Adapter:
    def __init__(self):
        self.started = []
        self.stopped = []
        self.metrics = {}

    def start_sequence(self, sequence):
        self.started.append(sequence.sequence_id)

    def stop_sequence(self, sequence):
        self.stopped.append(sequence.sequence_id)

    def read_metric(self, metric):
        return self.metrics.get(metric)


def recipe():
    return BreakinRecipe(
        name="TEST",
        version="1",
        phases=[
            BreakinPhase("A", duration_sec=1, pwm=64),
            BreakinPhase("B", duration_sec=1, pwm=80),
            BreakinPhase("C", duration_sec=1, pwm=96),
        ],
    )


def test_executor_runs_order_and_marks_complete():
    adapter = Adapter()
    executor = SequenceExecutor(adapter=adapter)
    executor.load_recipe(recipe())
    executor.start(instance_id=1)
    executor.execute_current(now=100.0)
    executor.execute_current(now=101.1)
    executor.execute_current(now=102.2)
    executor.execute_current(now=103.3)
    assert [r.status for r in executor.results] == ["COMPLETE", "COMPLETE", "COMPLETE"]
    assert executor.is_complete()
    assert adapter.started == ["01_A", "02_B", "03_C"]


def test_disabled_sequence_is_skipped():
    executor = SequenceExecutor(adapter=Adapter())
    executor.load_recipe(recipe(), enabled_ids={"01_A", "03_C"})
    executor.start(instance_id=1)
    assert executor.results[1].status == "SKIPPED"
    executor.execute_current(now=100.0)
    executor.execute_current(now=101.1)
    executor.execute_current(now=102.2)
    assert executor.results[1].status == "SKIPPED"
    assert executor.results[0].status == "COMPLETE"
    assert executor.results[2].status == "COMPLETE"


def test_pause_resume_does_not_change_sequence_index():
    executor = SequenceExecutor(adapter=Adapter())
    executor.load_recipe(recipe())
    executor.start(instance_id=7)
    assert executor.pause()
    assert executor.paused
    assert executor.state.sequence_index == 0
    assert executor.resume()
    assert not executor.paused
    assert executor.state.sequence_index == 0
