"""Performance estimation from measured motor voltage/current."""
from __future__ import annotations

from typing import Any

from analysis.models import EstimatedValue, FeatureSet, PerformanceResult


class PerformanceAnalysis:
    """Estimate motor performance from measurement-derived V/I features.

    Important distinction:
      - ``average_current`` in a break-in run is primarily no-load/friction
        current. It must NOT be treated as the motor's available load torque.
      - ``brush_peak_current`` is the strongest load/brush-contact current
        signal currently exposed by MOTOR_BREAKIN_V3, so it is used as the
        individual-motor performance signal when available.

    The torque estimate remains an estimate. RPM measured values are never
    consumed.
    """

    WEIGHT_PER_TORQUE = 1.0726072607

    # Tamiya published recommended-load reference points. Torque is converted
    # from mN*m to g*cm with 1 mN*m = 10.19716213 g*cm. Midpoints are used as
    # the reference because the manufacturer's values are ranges.
    REFERENCE_MOTORS = {
        "TORQUE TUNE 2": {
            "nominal_voltage": 2.4,
            "nominal_rpm": 13500.0,
            "nominal_current_ma": 1850.0,
            "nominal_torque_gcm": 18.3549,
        },
        "ATOMIC TUNE 2": {
            "nominal_voltage": 2.4,
            "nominal_rpm": 13800.0,
            "nominal_current_ma": 2000.0,
            "nominal_torque_gcm": 16.3155,
        },
        "REV TUNE 2": {
            "nominal_voltage": 2.4,
            "nominal_rpm": 14300.0,
            "nominal_current_ma": 1800.0,
            "nominal_torque_gcm": 13.9661,
        },
    }

    def __init__(self, config: dict[str, Any]):
        self.config = config

    @staticmethod
    def _positive(value: Any) -> float:
        try:
            return max(0.0, float(value))
        except (TypeError, ValueError):
            return 0.0

    @classmethod
    def _reference_spec(cls, motor_spec: dict[str, Any]) -> dict[str, float]:
        """Fill missing master values from the published motor family spec."""
        spec = dict(motor_spec or {})
        name = str(spec.get("name", "")).upper().replace("-", " ").strip()
        for key, reference in cls.REFERENCE_MOTORS.items():
            if key in name:
                for field, value in reference.items():
                    if cls._positive(spec.get(field)) <= 0:
                        spec[field] = value
                break
        return spec

    def analyze(self, features: FeatureSet, motor_spec: dict[str, Any] | None = None) -> PerformanceResult:
        result = PerformanceResult()
        motor_spec = self._reference_spec(motor_spec or {})

        voltage = self._positive(features.average_voltage or features.voltage)
        average_current = self._positive(features.average_current or features.current)
        brush_peak_current = self._positive(getattr(features, "brush_peak_current", 0.0))

        nominal_voltage = self._positive(motor_spec.get("nominal_voltage")) or 2.4
        nominal_rpm = self._positive(motor_spec.get("nominal_rpm"))
        nominal_current = self._positive(motor_spec.get("nominal_current_ma")) / 1000.0
        nominal_torque = self._positive(motor_spec.get("nominal_torque_gcm"))

        # RPM remains an estimate from the motor family reference. Measured
        # RPM is deliberately ignored by contract.
        rpm_cfg = self.config.get("performance", {}).get("rpm", {})
        gain = self._positive(rpm_cfg.get("voltage_gain"))
        if nominal_rpm > 0 and nominal_voltage > 0:
            rpm_30 = nominal_rpm * 3.0 / nominal_voltage
            rpm_28 = nominal_rpm * 2.8 / nominal_voltage
        elif voltage > 0:
            rpm_30 = voltage * gain * 3.0 / voltage
            rpm_28 = voltage * gain * 2.8 / voltage
        else:
            rpm_30 = rpm_28 = 0.0

        # ---------------------------------------------------------------
        # Torque model
        # ---------------------------------------------------------------
        # Previous implementation used average_current directly. In this
        # break-in setup that current is largely no-load/friction current,
        # which produced values such as ~0.82 g*cm for a Torque-Tuned 2.
        # That is not a useful motor-capability indicator.
        #
        # Use the independently tracked brush/load peak when available and
        # normalize it against the manufacturer's recommended-load current.
        # This gives an individual-motor estimate while retaining a known
        # physical reference point. The ratio is bounded to suppress isolated
        # ADC spikes from dominating the result.
        if nominal_current > 0 and nominal_torque > 0 and brush_peak_current > 0:
            load_ratio = brush_peak_current / nominal_current
            load_ratio = max(0.50, min(1.25, load_ratio))
            torque_reference = nominal_torque * load_ratio
            confidence = 0.65
        elif nominal_current > 0 and nominal_torque > 0:
            # No peak signal: retain the published capability rather than
            # falsely interpreting no-load current as output torque.
            torque_reference = nominal_torque
            confidence = 0.45
        else:
            # Last-resort legacy fallback. It is explicitly low-confidence.
            torque_gain = self._positive(
                self.config.get("performance", {}).get("torque", {}).get("current_gain")
            )
            torque_reference = average_current * torque_gain
            confidence = 0.20

        # Reference-voltage estimates. Keep the established project contract
        # of independent 3.0 V and 2.8 V estimates, normalized from the motor
        # family's 2.4 V reference point. These are estimates, not measured
        # torque values.
        torque_30 = torque_reference * 3.0 / nominal_voltage if nominal_voltage > 0 else 0.0
        torque_28 = torque_reference * 2.8 / nominal_voltage if nominal_voltage > 0 else 0.0

        result.estimated_rpm_3v = EstimatedValue(rpm_30, "rpm", confidence)
        result.estimated_rpm_28v = EstimatedValue(rpm_28, "rpm", confidence)
        result.estimated_torque_3v = EstimatedValue(torque_30, "g·cm", confidence)
        result.estimated_torque_28v = EstimatedValue(torque_28, "g·cm", confidence)

        result.estimated_no_load_rpm = result.estimated_rpm_3v
        result.estimated_torque = result.estimated_torque_3v
        result.estimated_supported_weight = EstimatedValue(
            max(0.0, torque_30 * self.WEIGHT_PER_TORQUE), "g", confidence
        )
        return result
