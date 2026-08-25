"""Generic recipe sequence definitions for MOTOR_BREAKIN_V3."""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

@dataclass(frozen=True)
class ConditionDefinition:
    metric: str
    operator: str
    value: float
    group: str = "ALL"
    def __post_init__(self):
        if self.operator not in {"<", "<=", "==", ">=", ">", "!="}:
            raise ValueError(f"Unsupported condition operator: {self.operator}")
        if self.group not in {"ALL", "ANY"}:
            raise ValueError(f"Unsupported condition group: {self.group}")

@dataclass
class SequenceDefinition:
    sequence_id: str
    order: int
    command: str
    enabled: bool = True
    direction: Optional[str] = None
    pwm: Optional[int] = None
    duration_sec: Optional[float] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    conditions: List[ConditionDefinition] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    def __post_init__(self):
        self.command = str(self.command).upper()
        if self.direction is not None: self.direction = str(self.direction).upper()
        if self.pwm is not None: self.pwm = max(0, min(255, int(self.pwm)))
        if self.duration_sec is not None: self.duration_sec = max(0.0, float(self.duration_sec))
    @classmethod
    def from_phase(cls, phase, order: int, enabled: bool = True):
        return cls(
            sequence_id=f"{order:02d}_{phase.name}", order=order,
            command=_command_from_control(phase.control), enabled=enabled,
            direction=phase.direction, pwm=phase.pwm, duration_sec=phase.duration_sec,
            parameters={
                "control": phase.control, "target_voltage": phase.target_voltage,
                "start_voltage": phase.start_voltage, "end_voltage": phase.end_voltage,
                "pwm_min": phase.pwm_min, "pwm_max": phase.pwm_max,
                "max_duration_sec": phase.max_duration_sec,
                "peak_margin_ratio": phase.peak_margin_ratio,
                "peak_min_current": phase.peak_min_current,
            }, metadata=dict(phase.metadata),
        )

@dataclass
class SequenceResult:
    sequence_id: str
    status: str = "PENDING"
    started_at: Optional[float] = None
    ended_at: Optional[float] = None
    elapsed_sec: float = 0.0
    remaining_sec: Optional[float] = None
    reason: Optional[str] = None


def _command_from_control(control: str) -> str:
    mapping = {"PWM": "FWD", "VOLTAGE": "FWD", "VOLTAGE_RAMP": "RAMP", "BRUSH_PEAK_APPROACH": "FWD"}
    return mapping.get(str(control).upper(), str(control).upper())

def sequences_from_recipe(recipe) -> List[SequenceDefinition]:
    return [SequenceDefinition.from_phase(phase, order=index) for index, phase in enumerate(recipe.phases, start=1)]
