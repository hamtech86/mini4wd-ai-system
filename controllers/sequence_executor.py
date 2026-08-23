"""Hardware-agnostic sequence execution state machine.

The executor deliberately does not send motor commands. It coordinates
ordered recipe rows, enabled/skip state, conditions, pause/resume checkpoints,
and delegates the actual operation to an adapter supplied by the caller.

Phase transition rule:
* Same direction: keep the motor running and hand the next PWM/control value
  directly to the adapter. No implicit STOP is inserted.
* Direction change: STOP, wait a fixed safety interval, then start the next
  phase.
"""

from dataclasses import dataclass
from time import time
from typing import Any, Iterable, List, Optional

from .sequence import SequenceDefinition, SequenceResult, sequences_from_recipe


DEFAULT_DIRECTION_CHANGE_PAUSE_SEC = 1.0


@dataclass
class SequenceExecutionState:
    recipe_name: str
    recipe_version: str
    instance_id: Any = None
    sequence_index: int = 0
    paused: bool = False


class SequenceExecutor:
    """Execute a declarative recipe one sequence at a time."""

    def __init__(self, adapter=None, checkpoint_store=None):
        self.adapter = adapter
        self.checkpoint_store = checkpoint_store
        self.sequences: List[SequenceDefinition] = []
        self.results: List[SequenceResult] = []
        self.state: Optional[SequenceExecutionState] = None
        self.running = False
        self.paused = False
        self.transition_pause_until: Optional[float] = None
        self.direction_change_pause_sec = DEFAULT_DIRECTION_CHANGE_PAUSE_SEC

    def load_recipe(self, recipe, enabled_ids: Optional[Iterable[str]] = None):
        enabled = None if enabled_ids is None else set(enabled_ids)
        self.sequences = sequences_from_recipe(recipe)
        if enabled is not None:
            for item in self.sequences:
                item.enabled = item.sequence_id in enabled
        self.results = [SequenceResult(item.sequence_id) for item in self.sequences]
        self.state = SequenceExecutionState(
            recipe_name=str(recipe.name).upper(),
            recipe_version=str(getattr(recipe, "version", "1")),
        )
        self.transition_pause_until = None
        return self.sequences

    def skip_disabled(self):
        for item, result in zip(self.sequences, self.results):
            if not item.enabled and result.status == "PENDING":
                result.status = "SKIPPED"
                result.reason = "disabled"

    def start(self, instance_id=None, resume_index=0):
        if not self.sequences or self.state is None:
            raise RuntimeError("No recipe loaded")
        if resume_index < 0 or resume_index >= len(self.sequences):
            raise ValueError("Invalid sequence index")
        self.state.instance_id = instance_id
        self.state.sequence_index = resume_index
        self.state.paused = False
        self.running = True
        self.paused = False
        self.transition_pause_until = None
        self.skip_disabled()
        return self.current()

    def current(self):
        if self.state is None or self.state.sequence_index >= len(self.sequences):
            return None
        return self.sequences[self.state.sequence_index]

    def _next_enabled_index(self, start_index):
        for index in range(start_index, len(self.sequences)):
            if self.sequences[index].enabled:
                return index
        return None

    def advance(self):
        if self.state is None:
            return None
        next_index = self._next_enabled_index(self.state.sequence_index + 1)
        self.state.sequence_index = len(self.sequences) if next_index is None else next_index
        return self.current()

    def pause(self):
        if not self.running or self.paused:
            return False
        self.paused = True
        if self.state:
            self.state.paused = True
            self._save_checkpoint()
        return True

    def resume(self):
        if not self.running or not self.paused:
            return False
        self.paused = False
        if self.state:
            self.state.paused = False
            self._save_checkpoint()
        return True

    def execute_current(self, now: Optional[float] = None):
        """Perform one scheduler step without blocking the caller."""
        if not self.running or self.paused:
            return self.current()
        sequence = self.current()
        if sequence is None:
            self.running = False
            return None

        now = time() if now is None else now

        # Direction-change safety pause is deliberately non-blocking so the
        # Qt/UI scheduler remains responsive.
        if self.transition_pause_until is not None:
            if now < self.transition_pause_until:
                self._save_checkpoint()
                return sequence
            self.transition_pause_until = None

        result = self.results[self.state.sequence_index]
        if result.status == "SKIPPED":
            self.advance()
            return self.current()

        if result.status == "PENDING":
            result.status = "RUNNING"
            result.started_at = now
            if self.adapter and hasattr(self.adapter, "start_sequence"):
                self.adapter.start_sequence(sequence)

        if self.adapter and hasattr(self.adapter, "tick"):
            self.adapter.tick(sequence)

        if self._conditions_met(sequence):
            self._complete_current(now, "condition_met")
        elif sequence.duration_sec is not None and now - result.started_at >= sequence.duration_sec:
            self._complete_current(now, "duration_elapsed")

        self._save_checkpoint()
        return self.current()

    def stop(self, reason="stopped"):
        sequence = self.current()
        if sequence is not None and self.adapter and hasattr(self.adapter, "stop_sequence"):
            self.adapter.stop_sequence(sequence)
        self.running = False
        self.transition_pause_until = None
        if self.state:
            self.state.paused = False
        self._clear_checkpoint()

    def is_complete(self):
        return self.state is not None and self.state.sequence_index >= len(self.sequences)

    def progress(self):
        if not self.sequences or self.state is None:
            return 0
        completed = sum(1 for result in self.results if result.status in ("COMPLETE", "SKIPPED"))
        enabled = sum(1 for item in self.sequences if item.enabled)
        return 0 if enabled == 0 else int(min(completed, enabled) / enabled * 100)

    def _complete_current(self, now, reason):
        sequence = self.current()
        if sequence is None:
            return
        result = self.results[self.state.sequence_index]
        result.status = "COMPLETE"
        result.ended_at = now
        result.elapsed_sec = max(0.0, now - (result.started_at or now))
        result.reason = reason

        next_index = self._next_enabled_index(self.state.sequence_index + 1)
        if next_index is None:
            if self.adapter and hasattr(self.adapter, "stop_sequence"):
                self.adapter.stop_sequence(sequence)
            self.state.sequence_index = len(self.sequences)
            self.running = False
            self._clear_checkpoint()
            return

        next_sequence = self.sequences[next_index]
        current_direction = str(sequence.direction or "FWD").upper()
        next_direction = str(next_sequence.direction or "FWD").upper()
        self.state.sequence_index = next_index

        if current_direction != next_direction:
            if self.adapter and hasattr(self.adapter, "stop_sequence"):
                self.adapter.stop_sequence(sequence)
            pause_sec = self._direction_change_pause(next_sequence)
            self.transition_pause_until = now + pause_sec
        else:
            # Same direction: deliberately do NOT call stop_sequence(). The
            # next start_sequence() changes PWM/control directly.
            self.transition_pause_until = None

    def _direction_change_pause(self, sequence):
        params = sequence.parameters or {}
        try:
            value = float(params.get("direction_change_pause_sec", self.direction_change_pause_sec))
        except (TypeError, ValueError):
            value = self.direction_change_pause_sec
        return max(0.0, value)

    def _conditions_met(self, sequence):
        if not sequence.conditions:
            return False
        values = []
        for condition in sequence.conditions:
            actual = self._read_metric(condition.metric)
            if actual is None:
                values.append(False)
                continue
            values.append(_compare(float(actual), condition.operator, condition.value))
        groups = {condition.group for condition in sequence.conditions}
        if "ANY" in groups:
            return any(values)
        return all(values)

    def _read_metric(self, metric):
        if self.adapter and hasattr(self.adapter, "read_metric"):
            return self.adapter.read_metric(metric)
        return None

    def _save_checkpoint(self):
        if self.checkpoint_store and self.state:
            self.checkpoint_store.save(self.state)

    def _clear_checkpoint(self):
        if self.checkpoint_store and hasattr(self.checkpoint_store, "clear"):
            self.checkpoint_store.clear()


def _compare(actual, operator, expected):
    return {
        "<": actual < expected,
        "<=": actual <= expected,
        "==": actual == expected,
        ">=": actual >= expected,
        ">": actual > expected,
        "!=": actual != expected,
    }[operator]
