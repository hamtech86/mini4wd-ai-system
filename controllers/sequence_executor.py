"""Hardware-agnostic recipe sequence executor.

The executor owns sequencing, conditions, skip state, progress and resume
state. Hardware/simulation behavior stays behind the adapter boundary.
"""

from dataclasses import dataclass, field
from time import time
from typing import Any, Dict, Iterable, List, Optional

from .sequence import SequenceDefinition, SequenceResult, sequences_from_recipe


@dataclass
class SequenceExecutionState:
    recipe_name: str
    recipe_version: str
    instance_id: Any = None
    sequence_index: int = 0
    paused: bool = False
    paused_elapsed_sec: float = 0.0
    results: Dict[str, Dict[str, Any]] = field(default_factory=dict)


class SequenceExecutor:
    """Execute a declarative recipe one row at a time.

    Adapter methods are optional: start_sequence, tick, stop_sequence and
    read_metric. A checkpoint store may implement save(state) and clear().
    """

    def __init__(self, adapter=None, checkpoint_store=None):
        self.adapter = adapter
        self.checkpoint_store = checkpoint_store
        self.sequences: List[SequenceDefinition] = []
        self.results: List[SequenceResult] = []
        self.state: Optional[SequenceExecutionState] = None
        self.running = False
        self.paused = False

    def load_recipe(self, recipe, enabled_ids: Optional[Iterable[str]] = None):
        enabled = None if enabled_ids is None else set(enabled_ids)
        self.sequences = sequences_from_recipe(recipe)
        if enabled is not None:
            for item in self.sequences:
                item.enabled = item.sequence_id in enabled
        self.results = [SequenceResult(item.sequence_id) for item in self.sequences]
        self.state = SequenceExecutionState(str(recipe.name).upper(), str(getattr(recipe, "version", "1")))
        return self.sequences

    def load_sequences(self, sequences: Iterable[SequenceDefinition], recipe_name="CUSTOM", recipe_version="1"):
        self.sequences = list(sequences)
        self.sequences.sort(key=lambda x: x.order)
        self.results = [SequenceResult(x.sequence_id) for x in self.sequences]
        self.state = SequenceExecutionState(recipe_name, recipe_version)
        return self.sequences

    def apply_enabled(self, enabled_ids: Iterable[str]):
        enabled = set(enabled_ids)
        for item in self.sequences:
            item.enabled = item.sequence_id in enabled
        self._mark_disabled()

    def _mark_disabled(self):
        for item, result in zip(self.sequences, self.results):
            if not item.enabled and result.status == "PENDING":
                result.status = "SKIPPED"
                result.reason = "disabled"

    def start(self, instance_id=None, resume_index=0):
        if not self.sequences or self.state is None:
            raise RuntimeError("No recipe loaded")
        if not 0 <= resume_index < len(self.sequences):
            raise ValueError("Invalid sequence index")
        self.state.instance_id = instance_id
        self.state.sequence_index = resume_index
        self.state.paused = False
        self.state.paused_elapsed_sec = 0.0
        self.running = True
        self.paused = False
        self._mark_disabled()
        self._skip_forward()
        self._save_checkpoint()
        return self.current()

    def current(self):
        if self.state is None or self.state.sequence_index >= len(self.sequences):
            return None
        return self.sequences[self.state.sequence_index]

    def _skip_forward(self):
        while self.state and self.state.sequence_index < len(self.sequences):
            item = self.sequences[self.state.sequence_index]
            result = self.results[self.state.sequence_index]
            if item.enabled and result.status not in {"SKIPPED", "COMPLETE"}:
                break
            self.state.sequence_index += 1
        if self.is_complete():
            self.running = False
            self._clear_checkpoint()

    def advance(self):
        if self.state is None:
            return None
        self.state.sequence_index += 1
        self._skip_forward()
        return self.current()

    def pause(self):
        if not self.running or self.paused:
            return False
        sequence = self.current()
        result = self.results[self.state.sequence_index]
        if result.status == "RUNNING" and result.started_at is not None:
            self.state.paused_elapsed_sec = max(0.0, time() - result.started_at)
        if sequence is not None and self.adapter and hasattr(self.adapter, "stop_sequence"):
            self.adapter.stop_sequence(sequence)
        self.paused = True
        self.state.paused = True
        self._save_checkpoint()
        return True

    def resume(self):
        if not self.running or not self.paused:
            return False
        result = self.results[self.state.sequence_index]
        if result.status == "RUNNING":
            result.started_at = time() - self.state.paused_elapsed_sec
        self.paused = False
        self.state.paused = False
        self.state.paused_elapsed_sec = 0.0
        self._save_checkpoint()
        return True

    def execute_current(self, now: Optional[float] = None):
        if not self.running or self.paused:
            return self.current()
        self._skip_forward()
        sequence = self.current()
        if sequence is None:
            return None
        now = time() if now is None else now
        result = self.results[self.state.sequence_index]
        if result.status == "PENDING":
            result.status = "RUNNING"
            result.started_at = now
            if self.adapter and hasattr(self.adapter, "start_sequence"):
                self.adapter.start_sequence(sequence)
        if self.adapter and hasattr(self.adapter, "tick"):
            self.adapter.tick(sequence)

        if self._conditions_met(sequence):
            self._complete_current(now, "condition_met")
        elif sequence.duration_sec is not None and result.started_at is not None and now - result.started_at >= sequence.duration_sec:
            self._complete_current(now, "duration_elapsed")
        self._save_checkpoint()
        return self.current()

    def stop(self, reason="stopped"):
        sequence = self.current()
        if sequence is not None and self.adapter and hasattr(self.adapter, "stop_sequence"):
            self.adapter.stop_sequence(sequence)
        self.running = False
        self.paused = False
        if self.state:
            self.state.paused = False
        self._clear_checkpoint()
        if sequence is not None and self.results and self.state.sequence_index < len(self.results):
            result = self.results[self.state.sequence_index]
            if result.status == "RUNNING":
                result.status = "STOPPED"
                result.reason = reason

    def is_complete(self):
        return self.state is not None and self.state.sequence_index >= len(self.sequences)

    def progress(self):
        if not self.sequences or self.state is None:
            return 0
        return int(min(self.state.sequence_index, len(self.sequences)) / len(self.sequences) * 100)

    def current_elapsed(self, now: Optional[float] = None):
        if self.state is None or self.is_complete():
            return 0.0
        result = self.results[self.state.sequence_index]
        if result.started_at is None:
            return 0.0
        return max(0.0, (time() if now is None else now) - result.started_at)

    def _complete_current(self, now, reason):
        sequence = self.current()
        if sequence is None:
            return
        result = self.results[self.state.sequence_index]
        result.status = "COMPLETE"
        result.ended_at = now
        result.elapsed_sec = max(0.0, now - (result.started_at or now))
        result.reason = reason
        if self.adapter and hasattr(self.adapter, "stop_sequence"):
            self.adapter.stop_sequence(sequence)
        self.advance()
        if self.is_complete():
            self.running = False
            self._clear_checkpoint()

    def _conditions_met(self, sequence):
        if not sequence.conditions:
            return False
        checks = []
        for condition in sequence.conditions:
            actual = self._read_metric(condition.metric)
            checks.append(False if actual is None else _compare(float(actual), condition.operator, condition.value))
        if any(c.group == "ANY" for c in sequence.conditions):
            return any(checks)
        return all(checks)

    def _read_metric(self, metric):
        if self.adapter and hasattr(self.adapter, "read_metric"):
            return self.adapter.read_metric(metric)
        return None

    def _save_checkpoint(self):
        if not self.checkpoint_store or not self.state:
            return
        self.state.results = {r.sequence_id: {
            "status": r.status, "started_at": r.started_at, "ended_at": r.ended_at,
            "elapsed_sec": r.elapsed_sec, "reason": r.reason,
        } for r in self.results}
        self.checkpoint_store.save(self.state)

    def _clear_checkpoint(self):
        if self.checkpoint_store and hasattr(self.checkpoint_store, "clear"):
            self.checkpoint_store.clear()


def _compare(actual, operator, expected):
    return {"<": actual < expected, "<=": actual <= expected, "==": actual == expected,
            ">=": actual >= expected, ">": actual > expected, "!=": actual != expected}[operator]
