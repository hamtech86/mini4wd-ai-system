"""
=====================================================
 MINI4WD AI SYSTEM
 MOTOR_BREAKIN_V3
 analysis/validation.py
=====================================================

Validation

Measurement入力品質を評価する。

責務
------
・欠損値チェック
・センサー範囲チェック
・品質スコア算出
・異常フラグ生成

解析停止は行わない。
品質低下としてResultへ渡す。
"""

from __future__ import annotations

from typing import Any

from measurement.measurement import Measurement

from analysis.models import ValidationResult


class Validation:
    """
    Measurement Validation
    """

    def __init__(
        self,
        config: dict[str, Any] | None = None,
    ):

        self.config = config or {}

    def validate(
        self,
        measurement: Measurement,
    ) -> ValidationResult:
        """
        Measurement品質確認
        """

        result = ValidationResult()

        #
        # 必須項目
        #

        required_fields = (

            "motor_voltage",

            "current_avg",

            "power",

            "pwm",

        )

        for field in required_fields:

            value = getattr(
                measurement,
                field,
                None,
            )

            if value is None:

                result.missing_count += 1


        #
        # 範囲設定
        #

        thresholds = self.config.get(
            "validation",
            {},
        )


        voltage_limit = thresholds.get(
            "max_voltage",
            6.0,
        )

        current_limit = thresholds.get(
            "max_current",
            10.0,
        )


        #
        # Voltage
        #

        voltage = getattr(
            measurement,
            "motor_voltage",
            0.0,
        )

        if voltage < 0:

            result.error_count += 1

        elif voltage > voltage_limit:

            result.warning_count += 1


        #
        # Current
        #

        current = getattr(
            measurement,
            "current_avg",
            0.0,
        )

        if current < 0:

            result.error_count += 1

        elif current > current_limit:

            result.warning_count += 1


        #
        # PWM
        #

        pwm = getattr(
            measurement,
            "pwm",
            0,
        )

        if pwm < 0 or pwm > 255:

            result.error_count += 1


        #
        # Quality Score
        #

        quality = 1.0

        quality -= (
            result.missing_count
            * 0.10
        )

        quality -= (
            result.warning_count
            * 0.05
        )

        quality -= (
            result.error_count
            * 0.20
        )

        result.quality_score = max(
            0.0,
            min(
                quality,
                1.0,
            ),
        )


        #
        # Status
        #

        result.valid = (
            result.error_count == 0
        )

        if result.valid:

            result.message = "OK"

        else:

            result.message = (
                "Validation Warning"
            )


        return result

