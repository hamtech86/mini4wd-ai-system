"""
=====================================================
 MINI4WD AI SYSTEM
 MOTOR_BREAKIN_V3
 analysis/models.py
=====================================================

Analysis Engine Common Data Models

Compatible V1.0

=====================================================
"""

from __future__ import annotations


from dataclasses import dataclass, field

from typing import (
    Any,
    Dict,
    List,
)



# =====================================================
# Estimated Value
# =====================================================

@dataclass
class EstimatedValue:
    """
    推定値共通形式

    value
    unit
    confidence
    """

    value: float = 0.0

    unit: str = ""

    confidence: float = 0.0



# =====================================================
# Feature Set
# =====================================================

@dataclass
class FeatureSet:
    """
    FeatureExtractor Output
    """

    voltage: float = 0.0

    current: float = 0.0

    pwm: float = 0.0

    rpm: float = 0.0

    temperature: float = 0.0

    magnetic: float = 0.0

    direction: str = ""

    state: str = ""

    quality: float = 1.0



# =====================================================
# Validation Result
# =====================================================

@dataclass
class ValidationResult:
    """
    Validation結果
    """

    valid: bool = False

    quality: float = 0.0


    missing_count: int = 0

    warning_count: int = 0

    anomaly_count: int = 0

    out_of_range_count: int = 0

    sensor_error_count: int = 0


    quality_score: float = 0.0

    confidence: float = 0.0


    warnings: List[str] = field(
        default_factory=list
    )

    anomaly_flags: List[str] = field(
        default_factory=list
    )

    errors: List[str] = field(
        default_factory=list
    )



# =====================================================
# Performance Result
# =====================================================

@dataclass
class PerformanceResult:
    """
    性能解析結果
    """

    estimated_rpm: EstimatedValue = field(
        default_factory=EstimatedValue
    )

    estimated_torque: EstimatedValue = field(
        default_factory=EstimatedValue
    )

    estimated_weight: EstimatedValue = field(
        default_factory=EstimatedValue
    )


    rpm: float = 0.0

    torque: float = 0.0

    weight: float = 0.0



# =====================================================
# Brush Result
# =====================================================

@dataclass
class BrushResult:
    """
    ブラシ解析結果
    """

    peak_detected: bool = False

    peak_position: float = 0.0

    brush_condition: str = "UNKNOWN"

    confidence: float = 0.0


    explanation: str = ""



# =====================================================
# Strategy Result
# =====================================================

@dataclass
class StrategyResult:
    """
    Break-in Strategy Result
    """

    recipe: str = ""

    reason: str = ""

    stages: List[Dict[str, Any]] = field(
        default_factory=list
    )


    explanation: str = ""


    @property
    def recipe_name(self):

        return self.recipe



# 旧名称互換

BreakinStrategyResult = StrategyResult



# =====================================================
# Score Result
# =====================================================

@dataclass
class ScoreResult:
    """
    Scoring Result
    """

    score: float = 0.0

    rank: str = "D"


    details: Dict[str, Any] = field(
        default_factory=dict
    )


    explanation: str = ""



# =====================================================
# Analysis Result
# =====================================================

@dataclass
class AnalysisResult:
    """
    Analysis Final Result
    """

    validation: ValidationResult = field(
        default_factory=ValidationResult
    )

    performance: PerformanceResult = field(
        default_factory=PerformanceResult
    )

    brush: BrushResult = field(
        default_factory=BrushResult
    )

    strategy: StrategyResult = field(
        default_factory=StrategyResult
    )

    score: ScoreResult = field(
        default_factory=ScoreResult
    )


    analysis_version: str = "1.0"

    algorithm_version: str = "1.0"

    config_version: str = "1.0"

    recipe_version: str = "1.0"

