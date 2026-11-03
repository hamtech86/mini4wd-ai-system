import json

import pytest

from measurement_310.loss_accounting import (
    Observation, Window, canonical_json, summarize,
)


def obs(t, disposition="valid", channel="CH1", boot=9):
    return Observation(channel, boot, t, disposition)


def test_counts_valid_invalid_missing_and_excess_separately():
    result = summarize(Window("CH1", 9, 10, 20, 5), [
        obs(10), obs(11), obs(12, "invalid"), obs(13), obs(19),
        obs(14, "duplicate"), obs(15, "conflicting_duplicate"),
    ])
    assert (result.attempts, result.valid, result.invalid) == (5, 4, 1)
    assert (result.duplicates, result.conflicts) == (1, 1)
    assert result.missing == 0
    assert result.excess == 0


def test_gap_is_represented_by_known_expected_count_not_synthetic_sample():
    result = summarize(Window("CH1", 9, 0, 100, 4), [obs(1), obs(2), obs(4)])
    assert result.valid == 3
    assert result.missing == 1


def test_unknown_expected_count_keeps_missing_unknown():
    result = summarize(Window("CH1", 9, 0, 100, None), [obs(1)])
    assert result.missing is None


def test_half_open_window_and_epoch_channel_isolation():
    result = summarize(Window("CH1", 9, 10, 20, 2), [
        obs(10), obs(19), obs(20), obs(12, boot=10),
        obs(13, channel="CH2"),
    ])
    assert result.valid == 2
    assert result.missing == 0


def test_unattributable_is_separate_and_not_assigned_to_window():
    result = summarize(Window("CH1", 9, 0, 10, 1), [
        obs(2), obs(3, channel=None), obs(None, boot=None),
    ])
    assert result.valid == 1
    assert result.unattributable == 2
    assert result.missing == 0


def test_identical_input_has_byte_identical_canonical_output():
    window = Window("CH1", 9, 0, 10, 3)
    inputs = [obs(1), obs(2, "invalid"), obs(3, "duplicate")]
    first = canonical_json(summarize(window, inputs))
    second = canonical_json(summarize(window, inputs))
    assert first == second
    assert json.loads(first)["digest_sha256"]


def test_unknown_disposition_is_rejected():
    with pytest.raises(ValueError):
        summarize(Window("CH1", 9, 0, 10, 1), [obs(1, "mystery")])


@pytest.mark.parametrize("expected", [-1, True])
def test_invalid_expected_count_is_rejected(expected):
    with pytest.raises(ValueError):
        summarize(Window("CH1", 9, 0, 10, expected), [])
