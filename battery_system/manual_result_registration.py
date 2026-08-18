"""Manual confirmation gate for official Battery benchmark registration."""
from __future__ import annotations


class ManualRegistrationError(ValueError):
    pass


def validate_manual_registration(*, session_result: str, quality_ok: bool, operator_confirmed: bool) -> None:
    """Raise unless a measured result is explicitly approved for persistence."""
    if session_result != "COMPLETE":
        raise ManualRegistrationError("only COMPLETE sessions may be registered")
    if not quality_ok:
        raise ManualRegistrationError("measurement quality is not acceptable")
    if not operator_confirmed:
        raise ManualRegistrationError("operator confirmation is required")
