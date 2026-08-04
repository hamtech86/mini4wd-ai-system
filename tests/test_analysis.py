"""
=====================================================
 MINI4WD AI SYSTEM
 MOTOR_BREAKIN_V3
 tests/test_analysis.py
=====================================================

Analysis Engine Test

Dummy Measurementを投入して
Analysis Pipeline確認を行う。
"""

from __future__ import annotations


import sys
from pathlib import Path


# =====================================================
# Project Root Path
# =====================================================

ROOT = Path(__file__).resolve().parent.parent

if str(ROOT) not in sys.path:

    sys.path.insert(
        0,
        str(ROOT)
    )


# =====================================================
# Import
# =====================================================

from analysis.analysis_engine import AnalysisEngine



# =====================================================
# Dummy Measurement
# =====================================================

class DummyMeasurement:
    """
    テスト用Measurement

    実機Measurementの代替
    """

    def __init__(self):

        self.timestamp = (
            "2026-08-04T00:00:00"
        )

        self.motor_voltage = 2.8

        self.current_avg = 1.8

        self.power = (
            self.motor_voltage
            *
            self.current_avg
        )

        self.pwm = 180

        self.rpm = 22000

        self.current_ripple = 0.15

        self.voltage_ripple = 0.05

        self.temperature = 35.0

        self.direction = "FWD"

        self.state = "RUN"

        self.device_model = (
            "TEST"
        )

        self.instance_id = (
            "TEST001"
        )



# =====================================================
# Test
# =====================================================

def main():

    print(
        "================================"
    )

    print(
        " Analysis Engine Test"
    )

    print(
        "================================"
    )


    #
    # Engine生成
    #

    engine = AnalysisEngine()


    print(
        "Engine Version:",
        engine.analysis_version
    )


    #
    # Measurement生成
    #

    measurement = DummyMeasurement()


    #
    # Analysis実行
    #

    result = engine.analyze(
        measurement
    )


    #
    # Result表示
    #

    print()

    print(
        "--- Validation ---"
    )

    print(
        "Valid:",
        result.validation.valid
    )

    print(
        "Quality:",
        result.validation.quality_score
    )


    print()

    print(
        "--- Performance ---"
    )

    print(
        "RPM:",
        result.performance
        .estimated_rpm.value
    )

    print(
        "Torque:",
        result.performance
        .estimated_torque.value
    )

    print(
        "Weight:",
        result.performance
        .estimated_weight.value
    )


    print()

    print(
        "--- Brush ---"
    )

    print(
        "Condition:",
        result.brush.brush_condition
    )

    print(
        "Confidence:",
        result.brush.confidence
    )


    print()

    print(
        "--- Strategy ---"
    )

    print(
        "Recipe:",
        result.strategy.recipe
    )

    print(
        "Reason:",
        result.strategy.reason
    )


    print()

    print(
        "--- Score ---"
    )

    print(
        "Score:",
        result.score.total_score
    )

    print(
        "Rank:",
        result.score.rank
    )


    print()

    print(
        "Analysis Test Complete"
    )



if __name__ == "__main__":

    main()

