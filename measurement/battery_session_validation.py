"""Validation rules for Battery measurement session assignment."""
from __future__ import annotations


class BatterySessionValidationError(ValueError):
    pass


def validate_channel_instances(ch1_instance_id: str | None, ch2_instance_id: str | None, *, all_channels: bool) -> None:
    """Validate Battery Instance assignment before starting a measurement.

    The same physical Battery may be measured on CH1 in one session and CH2 in
    another. Only simultaneous use in one STARTALL operation is forbidden.
    """
    if not all_channels:
        return
    if not ch1_instance_id or not ch2_instance_id:
        raise BatterySessionValidationError("STARTALL requires an instance for both CH1 and CH2")
    if ch1_instance_id == ch2_instance_id:
        raise BatterySessionValidationError(
            "STARTALL cannot assign the same Battery Instance to CH1 and CH2"
        )
