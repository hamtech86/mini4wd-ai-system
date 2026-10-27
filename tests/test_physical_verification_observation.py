from types import SimpleNamespace

from ui.physical_verification_report import _identity_snapshot


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


def test_identity_uses_controller_state_when_verified():
    controller = SimpleNamespace(
        identity_verified=True,
        firmware_version="3.03",
        device_info={},
    )

    result = _identity_snapshot(controller, "")

    assert result["identity_verified"] is True
    assert result["identity_evidence"] == "controller_state"
