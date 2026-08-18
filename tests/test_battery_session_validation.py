import pytest

from measurement.battery_session_validation import (
    BatterySessionValidationError,
    validate_channel_instances,
)


def test_same_instance_is_allowed_when_only_one_channel_runs():
    validate_channel_instances("BAT0001", None, all_channels=False)
    validate_channel_instances(None, "BAT0001", all_channels=False)


def test_same_instance_is_rejected_for_startall():
    with pytest.raises(BatterySessionValidationError):
        validate_channel_instances("BAT0001", "BAT0001", all_channels=True)


def test_startall_requires_both_instances():
    with pytest.raises(BatterySessionValidationError):
        validate_channel_instances("BAT0001", None, all_channels=True)


def test_different_instances_are_allowed_for_startall():
    validate_channel_instances("BAT0001", "BAT0002", all_channels=True)
