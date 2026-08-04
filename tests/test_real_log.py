"""
=====================================================
 MINI4WD AI SYSTEM
 MOTOR_BREAKIN_V3
 tests/test_real_log.py
=====================================================

Real CSV Log Analysis Test

Arduino CSV
    ↓
CSVParser
    ↓
Measurement
    ↓
AnalysisEngine
    ↓
Result
"""

from __future__ import annotations


import sys
from pathlib import Path


# =====================================================
# Project Root
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

from communication.csv_parser import CSVParser

from analysis.analysis_engine import (
    AnalysisEngine
)



# =====================================================
# Sample Arduino CSV
# =====================================================

TEST_LINE = (
    "DATA,"
    "MOTOR_BREAKIN_V3,"
    "TEST001,"
    "120,"
    "512,"
    "510,"
    "1.8,"
    "1.7,"
    "2.8,"
    "2.8,"
    "2.8,"
    "180,"
    "FWD,"
    "RUN,"
    "1.75,"
    "4.9,"
    "0.12,"
    "0.05,"
    "5.2,"
    "2.1,"
    "2.8,"
    "180,"
    "2.0,"
    "500,"
    "NORMAL,"
    "35.0"
)



# =====================================================
# Test
# =====================================================

def main():

    print(
        "=============================="
    )

    print(
        " Real Log Analysis Test"
    )

    print(
        "=============================="
    )


    #
    # Parser
    #

    parser = CSVParser()


    data = parser.parse(
        TEST_LINE
    )


    print()

    print(
        "CSV Parse OK"
    )


    #
    # Analysis
    #

    engine = AnalysisEngine()


    result = engine.analyze(
        data
    )


    print()

    print(
        "--- Result ---"
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


    print(
        "Brush:",
        result.brush.brush_condition
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
        "Real Log Test Complete"
    )



if __name__ == "__main__":

    main()

