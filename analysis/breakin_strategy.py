"""MOTOR_BREAKIN_V3 break-in strategy selector.

This module recommends a recipe; it never drives PWM. Recipe execution is
owned by BreakinController.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from analysis.models import StrategyResult


class BreakinStrategy:
    def __init__(self, config_path="config/breakin_recipes.yaml"):
        self.config_path = None
        self.recipes: dict[str, Any] = {}
        self.aliases: dict[str, str] = {}
        if isinstance(config_path, (str, Path)):
            self.config_path = Path(config_path)
            self.load()
        elif isinstance(config_path, dict):
            self.recipes = config_path.get("recipes", {})
            self.aliases = {str(k).upper(): str(v).upper() for k, v in config_path.get("aliases", {}).items()}
        else:
            raise TypeError("Invalid breakin recipe config")

    def load(self):
        if self.config_path is None:
            return
        if not self.config_path.exists():
            raise FileNotFoundError(self.config_path)
        with self.config_path.open("r", encoding="utf-8") as stream:
            config = yaml.safe_load(stream) or {}
        self.recipes = config.get("recipes", {}) or {}
        self.aliases = {str(k).upper(): str(v).upper() for k, v in (config.get("aliases", {}) or {}).items()}

    def analyze(self, performance, brush=None) -> StrategyResult:
        return self.select(performance, brush)

    @staticmethod
    def _value(obj, name, default=0.0):
        value = getattr(obj, name, default)
        return getattr(value, "value", value)

    def select(self, performance, brush=None) -> StrategyResult:
        rpm = float(self._value(performance, "estimated_rpm", getattr(performance, "rpm", 0.0)))
        torque = float(self._value(performance, "estimated_torque", 0.0))
        brush_name = str(brush or "").upper()
        if not brush_name:
            brush_name = str(getattr(performance, "brush", "")).upper()

        if brush_name == "CARBON":
            recipe_name = "DASH_OPTIMIZED"
            reason = "Carbon-brush Dash optimization"
        elif torque >= 20 and rpm < 23000:
            recipe_name = "TORQUE_TUNE_23K"
            reason = "Torque priority for a copper-brush motor below the 23k class"
        elif rpm >= 25000:
            recipe_name = "ATOMIC_25K"
            reason = "High-speed copper-brush optimization around the 25k class"
        else:
            recipe_name = "TUNE_OPTIMIZED"
            reason = "General copper-brush optimization without a hard RPM pass line"

        recipe = self.recipes.get(recipe_name, {})
        return StrategyResult(
            recipe_name=recipe_name,
            reason=reason,
            stages=recipe.get("stages", []),
            explanation=recipe.get("description", ""),
        )
