"""
=====================================================
 MINI4WD AI SYSTEM
 MOTOR_BREAKIN_V3
 analysis/models.py
=====================================================

Analysis Engine Data Models

=====================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field

from typing import (
    Any,
    Dict,
    List,
)


@dataclass
class EstimatedValue:
    """推定値共通モデル"""
    value: float = 0.0
    unit: str = ""
    confidence: float = 0.0


@dataclass
class FeatureSet:
    """FeatureExtractor Output"""
    voltage: float = 0.0
    current: float = 0.0
    pwm: float = 0.0
    rpm: float = 0.0
    average_voltage: float = 0.0
    average_current: float = 0.0
    temperature: float = 0.0
    magnetic: float = 0.0
    direction: str = ""
    state: str = ""
    quality: float = 1.0


@dataclass
class ValidationResult:
    """Validation結果"""
    valid: bool = False
    quality_score: float = 0.0
    missing_count: int = 0
    warning_count: int = 0
    error_count: int = 0
    message: str = ""
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    anomaly_flags: List[str] = field(default_factory=list)


@dataclass
class PerformanceResult:
    """Performance解析結果"""
    estimated_rpm: EstimatedValue = field(default_factory=EstimatedValue)
    estimated_torque: EstimatedValue = field(default_factory=EstimatedValue)
    estimated_weight: EstimatedValue = field(default_factory=EstimatedValue)
    # Physical vehicle-weight suitability profile. Kept separate from the
    # legacy estimated_weight compatibility field.
    weight_suitability: Any = None


@dataclass
class BrushResult:
    """Brush解析結果"""
    peak_detected: bool = False
    peak_position: float = 0.0
    brush_condition: str = "UNKNOWN"
    confidence: float = 0.0
    explanation: str = ""


@dataclass
class StrategyResult:
    """Break-in Strategy Result"""
    recipe_name: str = ""
    recipe: str = ""
    reason: str = ""
    stages: List[Dict[str, Any]] = field(default_factory=list)
    explanation: str = ""

    def __post_init__(self):
        if not self.recipe_name and self.recipe:
            self.recipe_name = self.recipe
        if not self.recipe and self.recipe_name:
            self.recipe = self.recipe_name


BreakinStrategyResult = StrategyResult


@dataclass
class ScoreResult:
    """Score Result"""
    total_score: float = 0.0
    rank: str = "D"
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def score(self):
        return self.total_score

    @score.setter
    def score(self, value):
        self.total_score = value


@dataclass
class AnalysisResult:
    """Final Analysis Result"""
    validation: ValidationResult = field(default_factory=ValidationResult)
    performance: PerformanceResult = field(default_factory=PerformanceResult)
    brush: BrushResult = field(default_factory=BrushResult)
    strategy: StrategyResult = field(default_factory=StrategyResult)
    score: ScoreResult = field(default_factory=ScoreResult)
    analysis_version: str = "1.0"
    algorithm_version: str = "1.0"
    config_version: str = "1.0"
    recipe_version: str = "1.0"
