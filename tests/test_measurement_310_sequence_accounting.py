import pytest

from measurement_310.sequence_accounting import (
    DeviceSequenceTracker,
    SequenceDisposition as D,
)


def test_normal_progression_and_uint16_wrap_are_contiguous():
    tracker = DeviceSequenceTracker(0x1234567800000001)
    values = [
        tracker.observe(65534, b"a"),
        tracker.observe(65535, b"b"),
        tracker.observe(0, b"c"),
        tracker.observe(1, b"d"),
    ]
    assert [x.disposition for x in values] == [D.FIRST, D.NEXT, D.WRAP, D.NEXT]
    assert [x.extended_sequence for x in values] == [65534, 65535, 65536, 65537]
    assert all(x.accepted for x in values)


def test_exact_duplicate_is_deduplicated_without_advancing():
    tracker = DeviceSequenceTracker(7)
    tracker.observe(12, b"sample")
    result = tracker.observe(12, b"sample")
    assert result.disposition is D.DUPLICATE
    assert not result.accepted
    assert tracker.last_extended_sequence == 12


def test_same_sequence_with_different_payload_is_conflict():
    tracker = DeviceSequenceTracker(7)
    tracker.observe(12, b"sample-a")
    result = tracker.observe(12, b"sample-b")
    assert result.disposition is D.CONFLICTING_DUPLICATE
    assert not result.accepted
    assert tracker.last_extended_sequence == 12


def test_gap_is_counted_without_synthesizing_samples():
    tracker = DeviceSequenceTracker(7)
    tracker.observe(100, b"a")
    result = tracker.observe(104, b"e")
    assert result.disposition is D.GAP
    assert result.forward_delta == 4
    assert result.missing_count == 3
    assert result.extended_sequence == 104


@pytest.mark.parametrize("delta", [32767, 32768, 32769])
def test_half_range_boundary_is_not_misclassified(delta):
    tracker = DeviceSequenceTracker(7)
    tracker.observe(0, b"a")
    result = tracker.observe(delta, b"b")
    if delta == 32767:
        assert result.accepted
        assert result.disposition is D.GAP
        assert result.missing_count == 32766
    elif delta == 32768:
        assert result.disposition is D.AMBIGUOUS_DELTA
        assert not result.accepted
        assert result.extended_sequence is None
    else:
        assert result.disposition is D.STALE_OR_BACKWARD
        assert not result.accepted
        assert result.extended_sequence is None
    assert tracker.last_extended_sequence == 0


def test_tracker_does_not_rebase_after_ambiguous_or_stale_frame():
    tracker = DeviceSequenceTracker(7)
    tracker.observe(1000, b"a")
    tracker.observe((1000 + 32768) & 0xFFFF, b"ambiguous")
    tracker.observe(999, b"stale")
    accepted = tracker.observe(1001, b"next")
    assert accepted.disposition is D.NEXT
    assert accepted.extended_sequence == 1001


def test_boot_id64_is_full_width_and_validated():
    a = DeviceSequenceTracker(0x0000000100000001)
    b = DeviceSequenceTracker(0x0000000200000001)
    assert a.boot_id64 != b.boot_id64
    with pytest.raises(ValueError):
        DeviceSequenceTracker(1 << 64)
    with pytest.raises(TypeError):
        DeviceSequenceTracker(True)


@pytest.mark.parametrize("sequence", [-1, 65536])
def test_wire_sequence_range_is_enforced(sequence):
    tracker = DeviceSequenceTracker(7)
    with pytest.raises(ValueError):
        tracker.observe(sequence, b"x")


def test_payload_must_be_immutable_bytes():
    tracker = DeviceSequenceTracker(7)
    with pytest.raises(TypeError):
        tracker.observe(1, bytearray(b"x"))
