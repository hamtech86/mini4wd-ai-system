"""Operator-attested release of 310 recovery inhibition markers.

This is an explicit host-side recovery action. It never opens a serial device,
sends a command, or claims that software has independently measured hardware
state. The operator must switch off motor power and verify the rotor stopped.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from raw_log_v2 import RawLogV2Writer


MARKER_NAMES = (
    ".310-rearm-inhibited",
    ".310-evidence-reconciliation-required",
)
AUDIT_NAME = "recovery-operator-actions.jsonl"
CONFIRMATION_PHRASE = "MOTOR POWER OFF"
SWITCH_VERIFICATION_PHRASE = "MOTOR SUPPLY ISOLATION VERIFIED"


class RecoveryReleaseError(RuntimeError):
    pass


def _fsync_directory(path: Path) -> None:
    fd = os.open(str(path), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def release_recovery_markers(
    root: os.PathLike[str] | str,
    *,
    operator_id: str,
    decision_note: str,
    confirm_main_power_off: bool,
    main_switch_isolation_verified: bool,
) -> dict[str, Any]:
    """Release existing recovery markers after one explicit operator attestation.

    Preconditions:
    - The RawLog root is a real directory and has no incomplete .work sessions.
    - The operator explicitly confirms motor main power is OFF and the rotor
      has stopped.
    - The action is recorded durably before marker removal.

    This is operator attestation, not independent physical safe-state evidence.
    """
    path = Path(root)
    if path.is_symlink() or not path.is_dir():
        raise RecoveryReleaseError("RawLog root must be an existing non-symlink directory")
    if confirm_main_power_off is not True:
        raise RecoveryReleaseError("explicit main-power-off confirmation is required")
    if main_switch_isolation_verified is not True:
        raise RecoveryReleaseError(
            "operator must confirm the main switch isolates motor/driver supply"
        )
    if not isinstance(operator_id, str) or not operator_id.strip():
        raise RecoveryReleaseError("operator_id must be non-empty")
    if not isinstance(decision_note, str) or not decision_note.strip():
        raise RecoveryReleaseError("decision_note must be non-empty")

    pending = RawLogV2Writer(path).list_incomplete_work()
    if pending:
        raise RecoveryReleaseError(
            "RawLog recovery is not complete; incomplete work remains: "
            + ", ".join(sorted(str(item) for item in pending))
        )

    markers: list[str] = []
    for name in MARKER_NAMES:
        marker = path / name
        if marker.is_symlink():
            raise RecoveryReleaseError(f"{name} must not be a symlink")
        if marker.exists():
            if not marker.is_file():
                raise RecoveryReleaseError(f"{name} must be a regular file")
            markers.append(name)

    if not markers:
        raise RecoveryReleaseError("no recovery marker exists; nothing to release")

    audit_path = path / AUDIT_NAME
    if audit_path.is_symlink():
        raise RecoveryReleaseError("operator audit file must not be a symlink")

    event = {
        "event": "OPERATOR_RECOVERY_MARKER_RELEASE",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "operator_id": operator_id.strip(),
        "decision_note": decision_note.strip(),
        "operator_attestation": "MAIN_POWER_OFF_AND_ROTOR_STOPPED",
        "main_switch_isolation_verification": "OPERATOR_ATTESTED",
        "physical_state_evidence": "OPERATOR_ATTESTATION_ONLY_NOT_INDEPENDENTLY_MEASURED",
        "markers": markers,
        "rawlog_incomplete_work": [],
    }
    payload = (json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")

    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(str(audit_path), flags, 0o600)
    try:
        if not os.path.isfile(audit_path):
            raise RecoveryReleaseError("operator audit path is not a regular file")
        written = 0
        while written < len(payload):
            count = os.write(fd, payload[written:])
            if count <= 0:
                raise OSError("operator audit append made no progress")
            written += count
        os.fsync(fd)
    finally:
        os.close(fd)

    # Remove only after the operator decision is durably recorded. If deletion
    # or directory fsync fails, any surviving marker continues to block ARM.
    for name in markers:
        (path / name).unlink()
    _fsync_directory(path)

    return {
        "released": markers,
        "audit_path": str(audit_path),
        "physical_state_evidence": event["physical_state_evidence"],
        "automatic_resume_performed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="existing RawLog v2 root")
    parser.add_argument("--operator-id", required=True)
    parser.add_argument("--decision-note", required=True)
    args = parser.parse_args()

    print(
        "Confirm that the motor main power switch is OFF and the rotor has stopped. "
        "This is an operator attestation, not an electrical measurement."
    )
    confirmation = input(f'Type "{CONFIRMATION_PHRASE}" to continue: ').strip()
    if confirmation != CONFIRMATION_PHRASE:
        raise SystemExit("confirmation phrase did not match; recovery markers were not changed")
    print(
        "Confirm that the main switch actually interrupts the L298N motor/driver supply "
        "according to the verified wiring."
    )
    switch_confirmation = input(
        f'Type "{SWITCH_VERIFICATION_PHRASE}" to continue: '
    ).strip()
    if switch_confirmation != SWITCH_VERIFICATION_PHRASE:
        raise SystemExit("switch-isolation confirmation did not match; markers were not changed")

    result = release_recovery_markers(
        args.root,
        operator_id=args.operator_id,
        decision_note=args.decision_note,
        confirm_main_power_off=True,
        main_switch_isolation_verified=True,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
