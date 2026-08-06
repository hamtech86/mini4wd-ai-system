"""
Break-in Phase Manager
MOTOR_BREAKIN_V3

Phase sequence control
"""


class PhaseManager:

    def __init__(self, recipe):
        self.recipe = recipe
        self.index = 0

    def reset(self):
        self.index = 0

    def has_next(self):
        return self.index < len(self.recipe.phases)

    def current_phase(self):
        if not self.has_next():
            return None
        return self.recipe.phases[self.index]

    def next_phase(self):
        if self.has_next():
            self.index += 1
        return self.current_phase()

    def progress(self):
        if not self.recipe.phases:
            return 0
        return int(self.index / len(self.recipe.phases) * 100)

    def total_phases(self):
        return len(self.recipe.phases)

    def current_index(self):
        return self.index

    def is_complete(self):
        return not self.has_next()
