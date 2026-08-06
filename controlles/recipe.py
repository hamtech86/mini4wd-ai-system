"""
Break-in Recipe Definition
MOTOR_BREAKIN_V3
"""

from dataclasses import dataclass
from typing import List


@dataclass
class BreakinPhase:
    name: str
    duration_sec: int
    pwm: int
    direction: str = "FWD"


@dataclass
class BreakinRecipe:
    name: str
    phases: List[BreakinPhase]

    def total_time(self):
        return sum(p.duration_sec for p in self.phases)


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
