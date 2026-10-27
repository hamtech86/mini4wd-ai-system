from types import SimpleNamespace

from datetime import datetime, timezone\n\nfrom ui.physical_verification_report import (\n    PHYSICAL_STOP_CHOICES,\n    _identity_snapshot,\n    _physical_stop_record,\n    _record_observation_in_ui_history,\n)


def test_identity_uses_successful_info_event_even_if_current_controller_flag_is_false():
    controller = SimpleNamespace(
        identity_verified=False,
        firmware_version="3.03",
        device_model="MOTOR_BREAKIN_V3",
        device_id="000001",
        build="EXPLICIT-ARM-STOP-ACK-20261023-01",
        device_info={},
    )
    history = (
        "[2026-10-27 09:02:20 JST] Motor INFO identity verified: "
        "{'TYPE': 'MOTOR', 'MODEL': 'MOTOR_BREAKIN_V3', 'FW': '3.03'}"
    )

    result = _identity_snapshot(controller, history)

    assert result["identity_verified"] is True
    assert result["identity_evidence"] == "ui_history"
    assert result["firmware_version"] == "3.03"


def test_identity_does_not_claim_success_when_state_and_history_are_unverified():
    controller = SimpleNamespace(identity_verified=False, device_info={})

    result = _identity_snapshot(controller, "UI ready; hardware identity has not been verified.")

    assert result["identity_verified"] is False
    assert result["identity_evidence"] == "unverified_or_unavailable"
    assert result["verification_state"] == "unverified"


def test_identity_uses_controller_state_when_verified():
    controller = SimpleNamespace(
        identity_verified=True,
        firmware_version="3.03",
        device_info={},
    )

    result = _identity_snapshot(controller, "")

    assert result["identity_verified"] is True
    assert result["identity_evidence"] == "controller_state"



def test_all_physical_stop_choices_serialize_without_inference():
    recorded_at = datetime(2026, 10, 27, 0, 7, 56, tzinfo=timezone.utc)
    for label, status in PHYSICAL_STOP_CHOICES:
        result = _physical_stop_record(
            {"status": status, "status_label": label, "details": "operator note"},
            recorded_at,
        )
        assert result == {
            "status": status,
            "status_label": label,
            "details": "operator note",
            "recorded_at_utc": recorded_at.isoformat(),
            "source": "operator_input_before_upload",
        }
    assert _physical_stop_record(
        {"status": "unconfirmed", "status_label": "未確認", "details": ""},
        recorded_at,
    )["status"] == "unconfirmed"


def test_physical_observation_is_mirrored_to_visible_ui_history():
    class FakeLog:
        def __init__(self):
            self.lines = []

        def appendPlainText(self, value):
            self.lines.append(value)

    window = SimpleNamespace(ui_log=FakeLog())
    lines = ["[2026-10-27 09:07:56 JST] Physical stop observation: 未確認"]
    _record_observation_in_ui_history(window, lines)
    assert window.ui_log.lines == [lines[0]]


def test_physical_observation_history_helper_tolerates_missing_ui_log():
    _record_observation_in_ui_history(SimpleNamespace(), ["observation"])



def test_missing_controller_is_reported_as_unavailable_not_unverified():
    result = _identity_snapshot(None, "UI ready; hardware identity has not been verified.")
    assert result["identity_verified"] is False
    assert result["verification_state"] == "unavailable"
