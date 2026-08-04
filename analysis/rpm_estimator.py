"""
=====================================================
 MINI4WD AI SYSTEM
 MOTOR_BREAKIN_V3
 rpm_estimator.py
=====================================================

RPM Estimator

Measurementから推定無負荷回転数を算出する。

Measurementのデータは変更しない。
"""

from __future__ import annotations

from measurement.measurement import Measurement


class RPMEstimator:
    """
    推定無負荷回転数
    """

    def __init__(self):
        pass

    def estimate(
        self,
        measurement: Measurement,
    ) -> float:
        """
        推定無負荷回転数を算出する。

        Parameters
        ----------
        measurement : Measurement
            Measurementデータ

        Returns
        -------
        float
            推定無負荷回転数[rpm]
        """

        #
        # TODO:
        # 解析アルゴリズム実装
        #
        # 使用候補
        # ・motor_voltage
        # ・current_avg
        # ・power
        # ・brush_peak_current
        # ・motor_temperature
        #

        estimated_rpm = 0.0

        return estimated_rpm

