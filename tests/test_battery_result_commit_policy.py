from enum import Enum


def can_commit_official_result(*, operator_confirmed, session_result, quality_ok):
    return bool(operator_confirmed and session_result == "COMPLETE" and quality_ok)


def test_official_result_requires_explicit_operator_confirmation():
    assert not can_commit_official_result(operator_confirmed=False, session_result="COMPLETE", quality_ok=True)
    assert can_commit_official_result(operator_confirmed=True, session_result="COMPLETE", quality_ok=True)


def test_failed_or_cancelled_runs_cannot_be_promoted():
    assert not can_commit_official_result(operator_confirmed=True, session_result="ERROR", quality_ok=True)
    assert not can_commit_official_result(operator_confirmed=True, session_result="CANCEL", quality_ok=True)
    assert not can_commit_official_result(operator_confirmed=True, session_result="COMPLETE", quality_ok=False)
