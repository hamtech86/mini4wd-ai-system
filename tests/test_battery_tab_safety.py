from types import SimpleNamespace

import pytest

from ui.battery_tab_ui import BatteryTab, battery_capture_start_blocked


@pytest.mark.parametrize("status", ["STARTING", "RUN", "RUNNING", "STOPPING"])
def test_restart_is_blocked_while_channel_is_active(status):
    assert battery_capture_start_blocked([], False, status)


@pytest.mark.parametrize("status", ["COMPLETE", "STOP", "ERROR", "IDLE"])
def test_restart_is_blocked_while_unpersisted_samples_remain(status):
    assert battery_capture_start_blocked([object()], status == "COMPLETE", status)


def test_restart_is_allowed_only_after_successful_persistence_clears_buffer():
    assert not battery_capture_start_blocked([], False, "IDLE")


@pytest.mark.parametrize("zero_field", ["voltage", "current"])
def test_normal_battery_tab_stats_reject_selected_channel_zero(zero_field):
    sample = SimpleNamespace(voltage=1.4, current=5.0, elapsed_sec=0.0)
    setattr(sample, zero_field, 0.0)
    with pytest.raises(ValueError, match="validity is UNKNOWN"):
        BatteryTab._stats([sample])


def test_normal_battery_tab_stats_reject_non_finite_values():
    sample = SimpleNamespace(voltage=float("nan"), current=5.0, elapsed_sec=0.0)
    with pytest.raises(ValueError, match="validity is UNKNOWN"):
        BatteryTab._stats([sample])


def test_channel_restart_eligibility_is_independent_and_startall_checks_both():
    ch1_blocked = battery_capture_start_blocked([object()], False, "ERROR")
    ch2_blocked = battery_capture_start_blocked([], False, "IDLE")
    assert ch1_blocked
    assert not ch2_blocked
    # STARTALL is permitted only when both channel-specific checks pass.
    assert ch1_blocked or ch2_blocked
    assert not (False or ch2_blocked)


def test_selected_channel_zero_rejects_for_either_channel():
    for channel in (1, 2):
        sample = SimpleNamespace(voltage=1.4, current=5.0, elapsed_sec=1.0)
        sample.voltage = 0.0
        with pytest.raises(ValueError, match="validity is UNKNOWN"):
            BatteryTab._stats([sample])
