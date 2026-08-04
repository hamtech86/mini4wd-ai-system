"""
=====================================================
 MINI4WD AI SYSTEM
 MOTOR_BREAKIN_V3
 analysis/feature_extractor.py
=====================================================

Feature Extractor

MeasurementからFeatureSetを生成する。

責務
----
・Measurementを変更しない
・Analysisで使用する特徴量を抽出する
・評価・判定は行わない
"""

from __future__ import annotations

from measurement.measurement import Measurement

from analysis.models import FeatureSet


class FeatureExtractor:
    """
    Feature抽出クラス
    """

    def extract(
        self,
        measurement: Measurement,
    ) -> FeatureSet:
        """
        MeasurementからFeatureSet生成
        """

        features = FeatureSet()

        #
        # 基本特徴量
        #

        features.average_voltage = getattr(
            measurement,
            "motor_voltage",
            0.0,
        )

        features.average_current = getattr(
            measurement,
            "current_avg",
            0.0,
        )

        features.average_power = getattr(
            measurement,
            "power",
            0.0,
        )

        features.current_ripple = getattr(
            measurement,
            "current_ripple",
            0.0,
        )

        features.voltage_ripple = getattr(
            measurement,
            "voltage_ripple",
            0.0,
        )

        features.pwm = getattr(
            measurement,
            "pwm",
            0.0,
        )

        #
        # 将来センサー
        #

        features.rpm = getattr(
            measurement,
            "rpm",
            0.0,
        )

        features.temperature = getattr(
            measurement,
            "motor_temperature",
            0.0,
        )

        features.magnetic = getattr(
            measurement,
            "magnetic_level",
            0.0,
        )

        return features

