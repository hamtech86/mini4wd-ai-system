"""
MOTOR_BREAKIN_V3
Recipe Manager
"""


class RecipeManager:
    def __init__(self):
        self.recipes = {
            "SPEED": {},
            "TORQUE": {},
            "BALANCE": {},
        }

    def get_recipe(self, name: str):
        return self.recipes.get(name.upper())

    def register_recipe(self, name: str, recipe: dict):
        self.recipes[name.upper()] = recipe
