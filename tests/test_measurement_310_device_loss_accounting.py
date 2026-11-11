import json

import pytest

from measurement_310.device_loss_accounting import (
    CHANNEL_ORDER,
    DeviceEpochClockUnwrapper,
    DeviceLossAccountingError,
    DeviceLossWindowAccumulator,
    load_latest_device_clock_checkpoint,
)


def batch(start_us, statuses=None):
    statuses = statuses or [0] * 12
    offsets = [0, 100, 200, 300, 400, 500, 25000, 25100, 25200, 25300, 25400, 25500]
    samples = []
    for i, channel in enumerate(CHANNEL_ORDER * 2):
        samples.append({
            "sample_sequence64": i,
            "timestamp_us_u32": (start_us + offsets[i]) & 0xFFFFFFFF,
            "channel_code": channel,
            "acquisition_status": statuses[i],
        })
    return samples


def ten_batches(acc, *, first_us=0, status_overrides=None, gap_at=None):
    summaries = []
    for cycle in range(10):
        statuses = [0] * 12
        if status_overrides and cycle == 0:
            for index, value in status_overrides.items():
                statuses[index] = value
        summaries.extend(acc.add_batch(
            batch(first_us + cycle * 100000, statuses),
            gap_slots=12 if gap_at == cycle else 0,
        ))
    return summaries


def test_full_one_second_window_reports_each_channel_and_half_open_boundary():
    acc = DeviceLossWindowAccumulator(boot_id64=123, stage_context_token=9)
    assert ten_batches(acc) == []
    completed = acc.add_batch(batch(1_000_000))
    assert len(completed) == 1
    window = completed[0]
    assert window.start_elapsed_us == 0
    assert window.end_elapsed_us == 1_000_000
    assert window.status == "PASS"
    for channel in window.channels:
        assert channel.expected == 20
        assert channel.attempted == 20
        assert channel.valid == 20
        assert channel.invalid == 0
        assert channel.missing == 0
        assert channel.status == "PASS"


def test_not_acquired_is_missing_not_an_attempt():
    acc = DeviceLossWindowAccumulator(boot_id64=123, stage_context_token=9)
    ten_batches(acc, status_overrides={1: 3})
    window = acc.add_batch(batch(1_000_000))[0]
    a1 = next(item for item in window.channels if item.channel == "A1")
    assert a1.expected == 20
    assert a1.attempted == 19
    assert a1.valid == 19
    assert a1.invalid == 0
    assert a1.not_acquired == 1
    assert a1.missing == 1


def test_conversion_failures_are_attempted_and_invalid():
    acc = DeviceLossWindowAccumulator(boot_id64=123, stage_context_token=9)
    ten_batches(acc, status_overrides={0: 1, 7: 2})
    window = acc.add_batch(batch(1_000_000))[0]
    a0 = next(item for item in window.channels if item.channel == "A0")
    a1 = next(item for item in window.channels if item.channel == "A1")
    assert (a0.attempted, a0.valid, a0.invalid, a0.missing) == (20, 19, 1, 0)
    assert (a1.attempted, a1.valid, a1.invalid, a1.missing) == (20, 19, 1, 0)


def test_sequence_gap_marks_affected_window_unattributable():
    acc = DeviceLossWindowAccumulator(boot_id64=123, stage_context_token=9)
    ten_batches(acc, gap_at=1)
    window = acc.add_batch(batch(1_000_000))[0]
    assert window.status == "UNATTRIBUTABLE"
    assert all(item.status == "UNATTRIBUTABLE" for item in window.channels)
    assert all(item.missing is None for item in window.channels)
    # The window-global gap total is repeated on each channel record for context;
    # it is not a per-channel count and must not be summed across channels.
    assert all(item.unattributable_slots == 12 for item in window.channels)


def test_micros_wrap_is_extended_within_device_epoch():
    start = 0xFFFF0000
    acc = DeviceLossWindowAccumulator(boot_id64=123, stage_context_token=9)
    ten_batches(acc, first_us=start)
    window = acc.add_batch(batch(start + 1_000_000))[0]
    assert window.status == "PASS"
    assert all(item.expected == 20 and item.missing == 0 for item in window.channels)


def test_partial_terminal_window_is_unattributable_not_filled_with_guesses():
    acc = DeviceLossWindowAccumulator(boot_id64=123, stage_context_token=9)
    acc.add_batch(batch(0))
    window = acc.finalize()
    assert window is not None
    assert window.status == "UNATTRIBUTABLE"
    assert all(item.expected is None and item.missing is None for item in window.channels)
    with pytest.raises(DeviceLossAccountingError):
        acc.add_batch(batch(100000))


def test_wrong_channel_order_fails_closed():
    acc = DeviceLossWindowAccumulator(boot_id64=123, stage_context_token=9)
    samples = batch(0)
    samples[2]["channel_code"] = 2
    with pytest.raises(DeviceLossAccountingError, match="channel order"):
        acc.add_batch(samples)



def test_device_epoch_clock_unwraps_micros_across_uint32_wrap():
    clock = DeviceEpochClockUnwrapper(boot_id64=123)
    assert clock.add(0xFFFFFFF0) == 0
    assert clock.add(0x00000020) == 0x30
    assert clock.elapsed_us == 0x30


def test_device_epoch_clock_rejects_ambiguous_backward_jump():
    clock = DeviceEpochClockUnwrapper(boot_id64=123)
    clock.add(2_000_000)
    with pytest.raises(DeviceLossAccountingError, match="ambiguous"):
        clock.add(1_000_000)



def _clock_record(sequence, timestamp, elapsed, *, epoch="000000000000007B"):
    return {
        "record_type": "ADC_SAMPLE",
        "device_epoch_id": epoch,
        "device_sample_sequence": sequence,
        "device_timestamp_us_u32": timestamp,
        "device_elapsed_us": elapsed,
        "validity": "valid",
    }


def test_load_latest_device_clock_checkpoint_from_durable_rawlog_records(tmp_path):
    first = tmp_path / "published-a" / "records.jsonl"
    second = tmp_path / ".work" / "session-b" / "records.jsonl"
    first.parent.mkdir(parents=True)
    second.parent.mkdir(parents=True)
    first.write_text(
        json.dumps(_clock_record(10, 100_000, 0)) + "\n" +
        json.dumps(_clock_record(11, 200_000, 100_000)) + "\n",
        encoding="utf-8",
    )
    second.write_text(
        json.dumps(_clock_record(12, 300_000, 200_000)) + "\n",
        encoding="utf-8",
    )

    checkpoint = load_latest_device_clock_checkpoint(tmp_path, 123)
    assert checkpoint is not None
    assert checkpoint.sample_sequence64 == 12
    assert checkpoint.timestamp_us_u32 == 300_000
    assert checkpoint.elapsed_us == 200_000


def test_load_latest_device_clock_checkpoint_rejects_discontinuous_elapsed(tmp_path):
    path = tmp_path / "published" / "records.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(_clock_record(10, 100_000, 0)) + "\n" +
        json.dumps(_clock_record(11, 200_000, 900_000)) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(DeviceLossAccountingError, match="discontinuous"):
        load_latest_device_clock_checkpoint(tmp_path, 123)


def test_device_epoch_clock_restores_durable_checkpoint():
    clock = DeviceEpochClockUnwrapper(
        boot_id64=123,
        checkpoint_timestamp_us_u32=0xFFFFFFF0,
        checkpoint_elapsed_us=50,
    )
    assert clock.add(0x00000020) == 0x30 + 50


def test_loss_window_checkpoint_marks_current_window_unattributable():
    acc = DeviceLossWindowAccumulator(
        boot_id64=123,
        checkpoint_timestamp_us_u32=500_000,
        checkpoint_elapsed_us=100_000,
    )
    assert acc.window_elapsed_us == 100_000
    assert 0 in acc._unattributable_windows
