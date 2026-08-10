"""MOTOR_BREAKIN_V3 recipe engine.

The engine owns recipe loading/validation only. It deliberately does not
send hardware commands; BreakinController executes the resulting recipe.
"""

from pathlib import Path

import yaml

from .recipe import BreakinRecipe


class RecipeEngine:
    def __init__(self, config_path="config/breakin_recipes.yaml"):
        self.config_path = Path(config_path)
        self.version = ""
        self.common = {}
        self.aliases = {}
        self.recipes = {}
        self.load()

    def load(self):
        with self.config_path.open("r", encoding="utf-8") as stream:
            config = yaml.safe_load(stream) or {}
        self.version = str(config.get("version", "1.0"))
        self.common = config.get("common", {}) or {}
        self.aliases = {str(k).upper(): str(v).upper() for k, v in (config.get("aliases", {}) or {}).items()}
        self.recipes = {
            str(name).upper(): BreakinRecipe.from_dict(str(name).upper(), data, self.version)
            for name, data in (config.get("recipes", {}) or {}).items()
        }
        self.validate()
        return self.recipes

    def validate(self):
        if not self.recipes:
            raise ValueError("No break-in recipes are defined")
        for name, recipe in self.recipes.items():
            if recipe.brush not in {"COPPER", "CARBON", "UNKNOWN"}:
                raise ValueError(f"{name}: unsupported brush type {recipe.brush}")
            for phase in recipe.phases:
                if phase.pwm < 0 or phase.pwm > 255:
                    raise ValueError(f"{name}/{phase.name}: PWM out of range")
                if phase.control == "VOLTAGE":
                    if phase.target_voltage is None or phase.target_voltage <= 0:
                        raise ValueError(f"{name}/{phase.name}: invalid target voltage")
                    if phase.pwm_min > phase.pwm_max:
                        raise ValueError(f"{name}/{phase.name}: invalid PWM limits")

    def names(self):
        return list(self.recipes.keys())

    def get(self, name):
        key = str(name).upper()
        key = self.aliases.get(key, key)
        return self.recipes.get(key)

    def benchmark(self):
        return dict(self.common.get("benchmark", {}) or {})

    def safety(self):
        return dict(self.common.get("safety", {}) or {})
