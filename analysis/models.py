"""Analysis Engine data models for MOTOR_BREAKIN_V3."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class EstimatedValue:
    value: float = 0.0
    unit: str = ""
    confidence: float = 0.0


@dataclass
class FeatureSet:
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
    brush_peak_current: float = 0.0
    current_ripple: float = 0.0


@dataclass
class ValidationResult:
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
    estimated_rpm: EstimatedValue = field(default_factory=EstimatedValue)
    estimated_torque: EstimatedValue = field(default_factory=EstimatedValue)
    estimated_weight: EstimatedValue = field(default_factory=EstimatedValue)


@dataclass
class BrushResult:
    peak_detected: bool = False
    peak_position: EstimatedValue = field(default_factory=EstimatedValue)
    brush_condition: str = "UNKNOWN"
    peak_score: EstimatedValue = field(default_factory=EstimatedValue)
    confidence: float = 0.0
    explanation: str = ""


@dataclass
class StrategyResult:
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
    validation: ValidationResult = field(default_factory=ValidationResult)
    performance: PerformanceResult = field(default_factory=PerformanceResult)
    brush: BrushResult = field(default_factory=BrushResult)
    strategy: StrategyResult = field(default_factory=StrategyResult)
    score: ScoreResult = field(default_factory=ScoreResult)
    analysis_version: str = "1.0"
    algorithm_version: str = "1.0"
    config_version: str = "1.0"
    recipe_version: str = "1.0"
