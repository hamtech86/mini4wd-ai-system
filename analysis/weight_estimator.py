"""
=====================================================
 MINI4WD AI SYSTEM
 MOTOR_BREAKIN_V3
 weight_estimator.py
=====================================================

Weight Estimator

推定トルク・回転数から
対応可能な車重を推定する。

Measurementは変更しない。
"""

from __future__ import annotations


class WeightEstimator:
    """
    対応車重推定
    """

    def __init__(self):
        pass

    def estimate(
        self,
        rpm: float,
        torque: float,
    ) -> float:
        """
        Parameters
        ----------
        rpm : float
            推定無負荷回転数

        torque : float
            推定トルク

        Returns
        -------
        float
            推定対応車重[g]
        """

        #
        # TODO
        # 推定アルゴリズム実装
        #

        supported_weight = 0.0

        return supported_weight

