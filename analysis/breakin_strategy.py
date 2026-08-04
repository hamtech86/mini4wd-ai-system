"""
=====================================================
 MINI4WD AI SYSTEM
 MOTOR_BREAKIN_V3
 breakin_strategy.py
=====================================================

Break-in Strategy

Analysis Engine Plugin

役割:

Feature / Performance
        ↓
BreakinStrategy
        ↓
StrategyResult


注意:
このクラスはPWM制御を行わない。

Controller側が
Recipeを使用して制御する。

=====================================================
"""


from __future__ import annotations


from pathlib import Path

from typing import Any

import yaml


from analysis.models import StrategyResult



class BreakinStrategy:
    """
    Break-in Strategy Analyzer
    """



    def __init__(
        self,
        config_path="config/breakin_recipes.yaml",
    ):

        self.config_path = None

        self.recipes: dict[str, Any] = {}


        #
        # YAML path
        #

        if isinstance(
            config_path,
            (str, Path)
        ):

            self.config_path = Path(
                config_path
            )

            self.load()


        #
        # Already loaded config
        #

        elif isinstance(
            config_path,
            dict
        ):

            self.recipes = config_path.get(
                "recipes",
                {}
            )


        else:

            raise TypeError(
                "Invalid breakin recipe config"
            )



    # =================================================
    # Load Config
    # =================================================

    def load(self):

        if self.config_path is None:

            return


        if not self.config_path.exists():

            raise FileNotFoundError(
                self.config_path
            )


        with open(
            self.config_path,
            "r",
            encoding="utf-8"
        ) as f:

            config = yaml.safe_load(f)


        self.recipes = config.get(
            "recipes",
            {}
        )



    # =================================================
    # Analysis Engine Interface
    # =================================================

    def analyze(
        self,
        performance,
        brush=None,
    ) -> StrategyResult:
        """
        AnalysisEngine入口

        """

        return self.select(
            performance,
            brush
        )



    # =================================================
    # Recipe Selection
    # =================================================

    def select(
        self,
        performance,
        brush=None,
    ) -> StrategyResult:
        """
        Recipe選択

        FeatureSet / PerformanceResult
        両対応

        """


        #
        # PerformanceResult
        #

        if hasattr(
            performance,
            "estimated_rpm"
        ):


            rpm = (
                performance
                .estimated_rpm
                .value
            )


            torque = (
                performance
                .estimated_torque
                .value
            )



        #
        # FeatureSet
        #

        else:


            rpm = getattr(
                performance,
                "rpm",
                0.0
            )


            #
            # V1.0ではFeatureから
            # torque推定なし
            #

            torque = 0.0



        #
        # Recipe Decision
        #

        if rpm >= 25000:


            recipe_name = (
                "POWER_DASH"
            )

            reason = (
                "High rotation "
                "priority recipe"
            )



        elif torque >= 20:


            recipe_name = (
                "TORQUE_TUNE"
            )

            reason = (
                "Torque priority "
                "recipe"
            )



        else:


            recipe_name = (
                "BALANCE"
            )

            reason = (
                "Balanced recipe"
            )



        recipe = self.recipes.get(
            recipe_name,
            {}
        )


        stages = recipe.get(
            "stages",
            []
        )



        return StrategyResult(

            recipe_name=recipe_name,

            reason=reason,

            stages=stages

        )

