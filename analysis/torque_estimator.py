"""
=====================================================
 MINI4WD AI SYSTEM
 MOTOR_BREAKIN_V3
 torque_estimator.py
=====================================================

Torque Estimator

The result is an estimated operating-point torque for comparison.
Canonical unit: g·cm.
"""

from __future__ import annotations

from typing import Any, Optional

from measurement.measurement import Measurement


class TorqueEstimator:
    """Estimate motor operating-point torque from calibrated model data."""

    def __init__(self, nominal_torque_gcm: Optional[float] = None, nominal_current_ma: Optional[float] = None):
        self.nominal_torque_gcm = self._positive(nominal_torque_gcm)
        self.nominal_current_a = (
            self._positive(nominal_current_ma / 1000.0)
            if nominal_current_ma is not None
            else None
        )

    @staticmethod
    def _positive(value: Any) -> Optional[float]:
        try:
            value = float(value)
        except (TypeError, ValueError):
            return None
        return value if value > 0 else None

    @property
    def available(self) -> bool:
        return self.nominal_torque_gcm is not None and self.nominal_current_a is not None

    def estimate(self, measurement: Measurement) -> Optional[float]:
        """Return estimated operating-point torque in g·cm.

        Missing model torque/current deliberately returns None rather than a
        fabricated zero. This prevents invalid torque values from propagating
        into supported-weight estimation.
        """
        if not self.available:
            return None
        current = self._positive(getattr(measurement, "current", None))
        if current is None:
            return None
        return self.nominal_torque_gcm * current / self.nominal_current_a

    def capability(self) -> Optional[float]:
        """Return the motor-model torque capability in g·cm."""
        return self.nominal_torque_gcm if self.available else None
