import pytest

from ui.battery_database_ui import infer_battery_session_channel, is_legacy_channel_ambiguous


def test_session_channel_is_detected_from_channel_specific_measurement_columns():
    assert infer_battery_session_channel([
        (0.0, 1.4, None, 5.0, None, "COMPLETE"),
        (1.0, 1.3, None, 5.1, None, "COMPLETE"),
    ]) == "CH1"
    assert infer_battery_session_channel([
        (0.0, None, 1.4, None, 5.0, "COMPLETE"),
        (1.0, None, 1.3, None, 5.1, "COMPLETE"),
    ]) == "CH2"


@pytest.mark.parametrize("rows", [
    [(0.0, 1.4, 1.42, 5.0, 4.8, "COMPLETE")],
    [(0.0, 1.4, None, 5.0, None, "COMPLETE"), (1.0, None, 1.3, None, 5.1, "COMPLETE")],
    [(0.0, None, None, None, None, "COMPLETE")],
    [],
])
def test_ambiguous_or_missing_channel_identity_fails_closed(rows):
    assert infer_battery_session_channel(rows) is None


def test_legacy_session_notes_are_used_only_to_quarantine_unknown_channel():
    assert is_legacy_channel_ambiguous("Integrated Battery UI CH2; manual result registration")
    assert not is_legacy_channel_ambiguous("Integrated Battery UI; manual result registration")
    assert not is_legacy_channel_ambiguous("CH2")
