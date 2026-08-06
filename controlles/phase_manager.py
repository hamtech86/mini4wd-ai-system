"""
Break-in Phase Manager
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
        self.index += 1
        return self.current_phase()

    def progress(self):
        if not self.recipe.phases:
            return 0
        return int(self.index / len(self.recipe.phases) * 100)
