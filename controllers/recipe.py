"""
Break-in Recipe Definition
MOTOR_BREAKIN_V3

Recipe files remain declarative; this module converts them into the
controller's typed recipe model.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class BreakinPhase:
    name: str
    duration_sec: int
    pwm: int = 0
    direction: str = "FWD"
    control: str = "PWM"
    target_voltage: Optional[float] = None
    pwm_min: int = 0
    pwm_max: int = 255
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BreakinPhase":
        known = {
            "name", "duration_sec", "pwm", "direction", "control",
            "target_voltage", "pwm_min", "pwm_max"
        }
        return cls(
            name=str(data["name"]),
            duration_sec=max(0, int(data.get("duration_sec", 0))),
            pwm=max(0, min(255, int(data.get("pwm", 0)))),
            direction=str(data.get("direction", "FWD")).upper(),
            control=str(data.get("control", "PWM")).upper(),
            target_voltage=(
                None if data.get("target_voltage") is None
                else float(data["target_voltage"])
            ),
            pwm_min=max(0, min(255, int(data.get("pwm_min", 0)))),
            pwm_max=max(0, min(255, int(data.get("pwm_max", 255)))),
            metadata={k: v for k, v in data.items() if k not in known},
        )


@dataclass
class BreakinRecipe:
    name: str
    phases: List[BreakinPhase]
    description: str = ""
    brush: str = "UNKNOWN"
    family: str = "UNKNOWN"
    objective: str = "BALANCE"
    target_rpm: Optional[float] = None
    torque_priority: float = 0.5
    benchmark: Optional[str] = None
    version: str = "2.0"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def total_time(self):
        return sum(p.duration_sec for p in self.phases)

    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any], version: str = "2.0") -> "BreakinRecipe":
        target = data.get("target") or {}
        phases = [BreakinPhase.from_dict(p) for p in data.get("stages", [])]
        if not phases:
            raise ValueError(f"Recipe '{name}' has no stages")
        return cls(
            name=name,
            phases=phases,
            description=str(data.get("description", "")),
            brush=str(data.get("brush", "UNKNOWN")).upper(),
            family=str(data.get("family", "UNKNOWN")).upper(),
            objective=str(data.get("objective", "BALANCE")).upper(),
            target_rpm=(None if target.get("rpm") is None else float(target["rpm"])),
            torque_priority=float(target.get("torque_priority", 0.5)),
            benchmark=data.get("benchmark"),
            version=version,
            metadata={k: v for k, v in data.items() if k not in {
                "description", "brush", "family", "objective", "benchmark", "target", "stages"
            }},
        )


def default_speed_recipe():
    return BreakinRecipe("SPEED", [
        BreakinPhase("START", 60, 80),
        BreakinPhase("MID", 120, 150),
        BreakinPhase("HIGH", 180, 220),
    ])


def default_torque_recipe():
    return BreakinRecipe("TORQUE", [
        BreakinPhase("LOW", 120, 100),
        BreakinPhase("LOAD", 180, 180),
    ])


def default_balance_recipe():
    return BreakinRecipe("BALANCE", [
        BreakinPhase("START", 60, 90),
        BreakinPhase("MID", 120, 160),
        BreakinPhase("FINISH", 120, 210),
    ])
