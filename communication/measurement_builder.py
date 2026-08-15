"""
=====================================================
 MINI4WD AI SYSTEM
 MOTOR_BREAKIN_V3
 communication/measurement_builder.py
=====================================================

CSV dict -> Measurement

The firmware records direction separately from electrical magnitude.
Measurement therefore stores positive electrical magnitudes so analysis
cannot produce negative voltage/RPM/torque merely because the H-bridge
polarity changed.
=====================================================
"""

from measurement.measurement import Measurement


class MeasurementBuilder:
    """Convert validated CSV data into the immutable measurement model."""

    @staticmethod
    def _magnitude(value) -> float:
        """Return a finite, non-negative electrical magnitude."""
        try:
            return abs(float(value))
        except (TypeError, ValueError):
            return 0.0

    def build(self, data: dict) -> Measurement:
        current1 = self._magnitude(data.get("current1", 0))
        current2 = self._magnitude(data.get("current2", 0))
        motor_voltage = self._magnitude(data.get("motor_voltage", 0))

        return Measurement(
            record_type=data.get("record_type", "DATA"),
            device_model=data.get("device_model", "UNKNOWN"),
            instance_id=data.get("instance_id", "UNKNOWN"),
            elapsed_time=int(data.get("elapsed_time", 0)),
            raw_acs1=int(data.get("raw_acs1", 0)),
            raw_acs2=int(data.get("raw_acs2", 0)),
            current1=current1,
            current2=current2,
            voltage1=self._magnitude(data.get("voltage1", 0)),
            voltage2=self._magnitude(data.get("voltage2", 0)),
            motor_voltage=motor_voltage,
            pwm=int(data.get("pwm", 0)),
            direction=data.get("direction", "FWD"),
            state=data.get("state", "READY"),
            current_avg=self._magnitude(data.get("current_avg", 0)),
            power=self._magnitude(data.get("power", 0)),
            current_ripple=self._magnitude(data.get("current_ripple", 0)),
            voltage_ripple=self._magnitude(data.get("voltage_ripple", 0)),
            peak_power=self._magnitude(data.get("peak_power", 0)),
            peak_current=self._magnitude(data.get("peak_current", 0)),
            peak_voltage=self._magnitude(data.get("peak_voltage", 0)),
            peak_pwm=int(data.get("peak_pwm", 0)),
            brush_peak_current=self._magnitude(data.get("brush_peak_current", 0)),
            raw_magnetic=int(data.get("raw_magnetic", 0)),
            magnetic_level=self._magnitude(data.get("magnetic_level", 0)),
            motor_temperature=float(data.get("motor_temperature", 0)),
            session_id=data.get("session_id"),
        )
