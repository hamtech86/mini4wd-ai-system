"""
MOTOR_BREAKIN_V3
Phase Manager
"""

from enum import Enum, auto


class BreakinPhase(Enum):
    INITIAL = auto()
    BREAKIN = auto()
    BRUSH_FORMING = auto()
    FINISH = auto()
    EVALUATION = auto()
    COMPLETE = auto()


class PhaseManager:
    def __init__(self):
        self.phase = BreakinPhase.INITIAL

    def set_phase(self, phase: BreakinPhase):
        self.phase = phase
        return self.phase

    def next(self):
        order = list(BreakinPhase)
        index = order.index(self.phase)
        if index < len(order) - 1:
            self.phase = order[index + 1]
        return self.phase

    def reset(self):
        self.phase = BreakinPhase.INITIAL
