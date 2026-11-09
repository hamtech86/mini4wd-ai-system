import json

import pytest

from measurement_310.recovery_release import (
    RecoveryReleaseError,
    release_recovery_markers,
)
from raw_log_v2 import RawLogV2Writer


def test_operator_release_requires_explicit_power_off_attestation(tmp_path):
    marker = tmp_path / ".310-rearm-inhibited"
    marker.write_text("recovery required\n", encoding="utf-8")

    with pytest.raises(RecoveryReleaseError, match="explicit main-power-off confirmation"):
        release_recovery_markers(
            tmp_path,
            operator_id="operator-1",
            decision_note="checked",
            confirm_main_power_off=False,
        )

    assert marker.exists()


def test_operator_release_records_attestation_before_removing_markers(tmp_path):
    markers = [
        tmp_path / ".310-rearm-inhibited",
        tmp_path / ".310-evidence-reconciliation-required",
    ]
    for marker in markers:
        marker.write_text("recovery required\n", encoding="utf-8")

    result = release_recovery_markers(
        tmp_path,
        operator_id="operator-1",
        decision_note="Main switch OFF; rotor visually stopped.",
        confirm_main_power_off=True,
    )

    assert result["released"] == [marker.name for marker in markers]
    assert result["automatic_resume_performed"] is False
    assert result["physical_state_evidence"] == (
        "OPERATOR_ATTESTATION_ONLY_NOT_INDEPENDENTLY_MEASURED"
    )
    assert all(not marker.exists() for marker in markers)

    audit_path = tmp_path / "recovery-operator-actions.jsonl"
    event = json.loads(audit_path.read_text(encoding="utf-8").splitlines()[0])
    assert event["operator_id"] == "operator-1"
    assert event["operator_attestation"] == "MAIN_POWER_OFF_AND_ROTOR_STOPPED"
    assert event["physical_state_evidence"] == (
        "OPERATOR_ATTESTATION_ONLY_NOT_INDEPENDENTLY_MEASURED"
    )
    assert set(event["markers"]) == {marker.name for marker in markers}


def test_operator_release_refuses_incomplete_rawlog_work(tmp_path, monkeypatch):
    marker = tmp_path / ".310-rearm-inhibited"
    marker.write_text("recovery required\n", encoding="utf-8")
    monkeypatch.setattr(
        RawLogV2Writer,
        "list_incomplete_work",
        lambda self: ["unfinished-session"],
    )

    with pytest.raises(RecoveryReleaseError, match="incomplete work remains"):
        release_recovery_markers(
            tmp_path,
            operator_id="operator-1",
            decision_note="checked",
            confirm_main_power_off=True,
        )

    assert marker.exists()
    assert not (tmp_path / "recovery-operator-actions.jsonl").exists()


def test_operator_release_refuses_symlinked_marker(tmp_path):
    target = tmp_path / "target"
    target.write_text("do not follow", encoding="utf-8")
    (tmp_path / ".310-rearm-inhibited").symlink_to(target)

    with pytest.raises(RecoveryReleaseError, match="must not be a symlink"):
        release_recovery_markers(
            tmp_path,
            operator_id="operator-1",
            decision_note="checked",
            confirm_main_power_off=True,
        )

    assert target.read_text(encoding="utf-8") == "do not follow"


def test_operator_release_requires_a_marker(tmp_path):
    with pytest.raises(RecoveryReleaseError, match="no recovery marker"):
        release_recovery_markers(
            tmp_path,
            operator_id="operator-1",
            decision_note="checked",
            confirm_main_power_off=True,
        )
