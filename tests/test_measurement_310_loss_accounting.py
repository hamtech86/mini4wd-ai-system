import json

import pytest

from measurement_310.loss_accounting import (
    Observation, Window, canonical_json, summarize, summarize_many,
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


def test_excess_is_counted_when_observed_attempts_exceed_expected():
    result = summarize(Window("CH1", 9, 0, 10, 1), [obs(1), obs(2, "invalid")])
    assert result.excess == 1
    assert result.missing == 0


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


def test_malformed_observation_numeric_fields_are_unattributable():
    result = summarize(Window("CH1", 9, 0, 10, 1), [
        obs(2), obs(3.5), obs(4, boot=True),
    ])
    assert result.valid == 1
    assert result.unattributable == 2


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


@pytest.mark.parametrize("expected", [1.5, "2"])
def test_non_integer_expected_count_is_rejected(expected):
    with pytest.raises(TypeError):
        summarize(Window("CH1", 9, 0, 10, expected), [])


@pytest.mark.parametrize("start,end", [(0.5, 10), (0, 10.5), (10, 10), (11, 10)])
def test_invalid_window_bounds_are_rejected(start, end):
    with pytest.raises((TypeError, ValueError)):
        summarize(Window("CH1", 9, start, end, 1), [])



def test_batch_counts_unattributable_observation_once_across_channels():
    windows = [
        Window("CH1", 9, 0, 10, 1),
        Window("CH2", 9, 0, 10, 1),
    ]
    batch = summarize_many(windows, [
        obs(1, channel="CH1"),
        obs(2, channel="CH2"),
        obs(3, channel=None),
    ])
    assert [item.valid for item in batch.summaries] == [1, 1]
    assert [item.unattributable for item in batch.summaries] == [0, 0]
    assert batch.unattributable == 1


def test_batch_counts_missing_timestamp_once_across_windows():
    windows = [
        Window("CH1", 9, 0, 10, 0),
        Window("CH2", 9, 0, 10, 0),
    ]
    batch = summarize_many(windows, [obs(None)])
    assert batch.unattributable == 1
    assert sum(item.unattributable for item in batch.summaries) == 0


def test_batch_assigns_epoch_and_time_scoped_observations_once():
    windows = [
        Window("CH1", 9, 0, 10, 1),
        Window("CH1", 9, 10, 20, 1),
        Window("CH1", 10, 0, 10, 1),
    ]
    batch = summarize_many(windows, [
        obs(1, boot=9), obs(11, boot=9), obs(1, boot=10),
        obs(30, boot=9),
    ])
    assert [item.valid for item in batch.summaries] == [1, 1, 1]
    assert batch.unattributable == 0


def test_batch_rejects_overlapping_windows_for_same_channel_epoch():
    with pytest.raises(ValueError, match="overlapping"):
        summarize_many([
            Window("CH1", 9, 0, 10, 1),
            Window("CH1", 9, 9, 20, 1),
        ], [])
