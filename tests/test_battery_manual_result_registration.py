import pytest

from battery_system.manual_result_registration import ManualRegistrationError, validate_manual_registration


def test_complete_quality_ok_and_operator_confirmation_are_required():
    validate_manual_registration(session_result="COMPLETE", quality_ok=True, operator_confirmed=True)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"session_result": "ERROR", "quality_ok": True, "operator_confirmed": True},
        {"session_result": "CANCEL", "quality_ok": True, "operator_confirmed": True},
        {"session_result": "COMPLETE", "quality_ok": False, "operator_confirmed": True},
        {"session_result": "COMPLETE", "quality_ok": True, "operator_confirmed": False},
    ],
)
def test_invalid_results_cannot_be_registered(kwargs):
    with pytest.raises(ManualRegistrationError):
        validate_manual_registration(**kwargs)
