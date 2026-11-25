import pytest

from ui.battery_database_ui import infer_battery_session_channel, is_legacy_channel_ambiguous


def test_session_channel_requires_explicit_scope_key():
    assert infer_battery_session_channel(["BATTERY:CH1"]) == "CH1"
    assert infer_battery_session_channel(["BATTERY:CH2", "BATTERY:CH2"]) == "CH2"


@pytest.mark.parametrize("scope_keys", [
    [],
    [None],
    ["BATTERY:CH1", None],
    ["BATTERY:CH1", "BATTERY:CH2"],
    ["CH1"],
    ["voltage1"],
    ["", "BATTERY:CH1"],
])
def test_missing_or_ambiguous_scope_key_fails_closed(scope_keys):
    assert infer_battery_session_channel(scope_keys) is None


def test_measurement_scope_keys_must_all_match_session_scope():
    assert infer_battery_session_channel(["BATTERY:CH1", "BATTERY:CH1", "BATTERY:CH1"]) == "CH1"
    assert infer_battery_session_channel(["BATTERY:CH1", "BATTERY:CH1", None]) is None
    assert infer_battery_session_channel(["BATTERY:CH1", "BATTERY:CH1", "BATTERY:CH2"]) is None
    assert infer_battery_session_channel(["BATTERY:CH2", "BATTERY:CH1"]) is None


def test_legacy_session_notes_are_used_only_to_quarantine_unknown_channel():
    assert is_legacy_channel_ambiguous("Integrated Battery UI CH2; manual result registration")
    assert not is_legacy_channel_ambiguous("Integrated Battery UI; manual result registration")
    assert not is_legacy_channel_ambiguous("CH2")
