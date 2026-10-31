"""Calibrated, host-side analysis for RawLog v2 AUX acquisition cycles.

Raw AUX records remain immutable. Calibration is supplied by the caller; this
module contains no device-specific constants and never mixes A0 with A1.
Resistance is calculated only when an explicit timestamp-skew policy is
provided and the cycle passes it.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping

from .rawlog_v2_alignment import AuxAcquisitionCycle


class AuxAnalysisError(ValueError):
    """Raised when calibration or analysis policy is invalid."""


@dataclass(frozen=True)
class ChannelCalibration:
    channel: str
    scale: float
    offset: float
    unit: str

    def __post_init__(self):
        if self.channel not in {"A0", "A1", "A4", "A5"}:
            raise AuxAnalysisError(f"unsupported calibration channel: {self.channel!r}")
        if isinstance(self.scale, bool) or not isinstance(self.scale, (int, float)) or not math.isfinite(float(self.scale)):
            raise AuxAnalysisError("calibration scale must be finite")
        if isinstance(self.offset, bool) or not isinstance(self.offset, (int, float)) or not math.isfinite(float(self.offset)):
            raise AuxAnalysisError("calibration offset must be finite")
        if not isinstance(self.unit, str) or not self.unit.strip():
            raise AuxAnalysisError("calibration unit must be non-empty")


@dataclass(frozen=True)
class ChannelValue:
    channel: str
    sample_id: str
    value: float
    unit: str
    timestamp_unwrapped_us: int


@dataclass(frozen=True)
class WindingResistanceResult:
    session_id: str
    sequence: int
    valid: bool
    resistance_ohm: float | None
    voltage_delta_v: float | None
    current_a: float | None
    a4_a5_skew_us: int | None
    a0_to_voltage_skew_us: int | None
    input_sample_ids: tuple[str, ...]
    invalid_reason: str | None
    algorithm_id: str = "winding_resistance_point_v1"
    algorithm_version: str = "0.1.0"


def convert_cycle_channels(
    cycle: AuxAcquisitionCycle,
    calibrations: Mapping[str, ChannelCalibration],
) -> dict[str, ChannelValue]:
    """Convert only supplied channels with explicit per-channel calibration.

    Engineering value = adc_raw * scale + offset. No default calibration is
    provided. A0 and A1 are converted independently and never combined.
    """
    converted = {}
    for channel, sample in cycle.samples.items():
        calibration = calibrations.get(channel)
        if calibration is None:
            continue
        if calibration.channel != channel:
            raise AuxAnalysisError(
                f"calibration key/channel mismatch for {channel}: {calibration.channel}"
            )
        value = sample.adc_raw * float(calibration.scale) + float(calibration.offset)
        if not math.isfinite(value):
            raise AuxAnalysisError(f"non-finite converted value for {channel}")
        converted[channel] = ChannelValue(
            channel=channel,
            sample_id=sample.sample_id,
            value=value,
            unit=calibration.unit,
            timestamp_unwrapped_us=sample.timestamp_unwrapped_us,
        )
    return converted


def analyze_winding_resistance_cycle(
    cycle: AuxAcquisitionCycle,
    calibrations: Mapping[str, ChannelCalibration],
    *,
    max_skew_us: int,
    required_run_state: str,
) -> WindingResistanceResult:
    """Calculate one point R=|V4-V5|/|I(A0)| under explicit policy.

    max_skew_us and required_run_state are mandatory caller policy, not
    silently selected physical thresholds. Direction determines voltage
    polarity: FWD uses V4-V5; REV uses V5-V4. Absolute magnitude is used for
    resistance. A1 is never read by this calculation.
    """
    if type(max_skew_us) is not int or max_skew_us < 0:
        raise AuxAnalysisError("max_skew_us must be an explicit non-negative integer")
    if not isinstance(required_run_state, str) or not required_run_state:
        raise AuxAnalysisError("required_run_state must be explicit and non-empty")

    converted = convert_cycle_channels(cycle, calibrations)
    ids = tuple(
        converted[ch].sample_id for ch in ("A0", "A4", "A5") if ch in converted
    )

    def invalid(reason, skew=None, a0_skew=None, dv=None, current=None):
        return WindingResistanceResult(
            session_id=cycle.session_id, sequence=cycle.sequence, valid=False,
            resistance_ohm=None, voltage_delta_v=dv, current_a=current,
            a4_a5_skew_us=skew, a0_to_voltage_skew_us=a0_skew,
            input_sample_ids=ids, invalid_reason=reason,
        )

    if cycle.phase != "WINDING":
        return invalid("phase is not WINDING")
    if cycle.direction not in {"FWD", "REV"}:
        return invalid("direction must be FWD or REV")
    if cycle.run_state != required_run_state:
        return invalid("run_state does not match required measurement state")
    missing = [ch for ch in ("A0", "A4", "A5") if ch not in converted]
    if missing:
        return invalid("missing calibration or sample for " + ",".join(missing))
    if not cycle.metadata_consistent:
        return invalid(cycle.metadata_error or "cycle metadata mismatch")
    if not cycle.a4_a5_pair_valid:
        return invalid(cycle.a4_a5_pair_reason or "A4/A5 pair invalid")

    a0, a4, a5 = (converted[ch] for ch in ("A0", "A4", "A5"))
    voltage_skew = cycle.a4_a5_skew_us
    a0_skew = max(
        abs(a0.timestamp_unwrapped_us - a4.timestamp_unwrapped_us),
        abs(a0.timestamp_unwrapped_us - a5.timestamp_unwrapped_us),
    )
    if voltage_skew is None or abs(voltage_skew) > max_skew_us or a0_skew > max_skew_us:
        return invalid("timestamp skew exceeds configured maximum", voltage_skew, a0_skew)
    if a4.unit != "V" or a5.unit != "V":
        return invalid("A4 and A5 calibrations must use volts", voltage_skew, a0_skew)
    if a0.unit != "A":
        return invalid("A0 calibration must use amperes", voltage_skew, a0_skew)
    voltage_delta = (
        a4.value - a5.value if cycle.direction == "FWD" else a5.value - a4.value
    )
    current = abs(a0.value)
    if current == 0.0:
        return invalid("A0 current is zero after calibration", voltage_skew, a0_skew, voltage_delta, current)
    resistance = abs(voltage_delta) / current
    if not math.isfinite(resistance):
        return invalid("calculated resistance is non-finite", voltage_skew, a0_skew, voltage_delta, current)
    return WindingResistanceResult(
        session_id=cycle.session_id, sequence=cycle.sequence, valid=True,
        resistance_ohm=resistance, voltage_delta_v=voltage_delta,
        current_a=current, a4_a5_skew_us=voltage_skew,
        a0_to_voltage_skew_us=a0_skew, input_sample_ids=ids,
        invalid_reason=None,
    )
