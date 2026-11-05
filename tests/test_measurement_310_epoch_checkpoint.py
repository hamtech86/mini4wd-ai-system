import json

import pytest

from measurement_310.epoch_checkpoint import (
    CheckpointStatus as S,
    EpochCheckpoint,
    decode_checkpoint,
    encode_checkpoint,
    resolve_checkpoint,
    restore_sequence_tracker,
    write_checkpoint_atomic,
)


def cp(boot=0x1234567800000001, extended=65537):
    return EpochCheckpoint(boot, extended, extended & 0xFFFF)


def test_round_trip_preserves_full_boot_id_and_sequence():
    original = cp()
    assert decode_checkpoint(encode_checkpoint(original)) == original


def test_session_boundary_does_not_reset_same_boot_epoch():
    raw = encode_checkpoint(cp(extended=70001))
    for _session_boundary in ("HELLO", "ARM", "STOP", "new-session"):
        result = resolve_checkpoint(raw, cp().boot_id64)
        assert result.status is S.RESUME_SAME_EPOCH
        assert result.checkpoint.extended_sequence == 70001


def test_low32_collision_is_not_same_epoch():
    old = cp(boot=0x0000000100000001)
    new_boot = 0x0000000200000001
    result = resolve_checkpoint(encode_checkpoint(old), new_boot)
    assert result.status is S.UNRESOLVED_BOOT_MISMATCH
    assert result.checkpoint is None


def test_new_epoch_requires_independent_reboot_confirmation():
    old = cp(boot=0x0000000100000001)
    raw = encode_checkpoint(old)
    new_boot = 0x0000000200000001
    result = resolve_checkpoint(raw, new_boot, reboot_confirmed=True)
    assert result.status is S.NEW_CONFIRMED_EPOCH


@pytest.mark.parametrize("raw,status", [
    (None, S.UNRESOLVED_MISSING),
    (b"", S.UNRESOLVED_CORRUPT),
    (b'{"payload":', S.UNRESOLVED_CORRUPT),
    (b'{"payload":{},"sha256":"bad"}', S.UNRESOLVED_CORRUPT),
])
def test_missing_or_corrupt_checkpoint_is_unresolved(raw, status):
    result = resolve_checkpoint(raw, cp().boot_id64)
    assert result.status is status
    assert result.checkpoint is None


def test_checksum_detects_payload_tampering():
    data = json.loads(encode_checkpoint(cp()))
    data["payload"]["extended_sequence"] += 1
    raw = json.dumps(data).encode()
    with pytest.raises(ValueError):
        decode_checkpoint(raw)


@pytest.mark.xfail(strict=True, reason="T03 blocker: checkpoint checksum has no independent freshness witness")
def test_authentic_older_checkpoint_for_same_boot_is_not_accepted_after_rollback():
    boot = 0x1234567800000001
    older = encode_checkpoint(cp(boot=boot, extended=65537))
    newer = encode_checkpoint(cp(boot=boot, extended=131074))

    # Both checkpoints are authentic and checksum-valid. Simulate restoring
    # the older persisted bytes after the newer checkpoint had been committed.
    assert decode_checkpoint(newer).extended_sequence > decode_checkpoint(older).extended_sequence
    resolution = resolve_checkpoint(older, boot)

    # Correct behavior must reject/unresolve the stale checkpoint unless an
    # independent high-water witness proves it current. Current resolver
    # returns RESUME_SAME_EPOCH and rewinds to 65537.
    assert resolution.status is not S.RESUME_SAME_EPOCH


@pytest.mark.parametrize("fault", [
    "after_temp_write", "after_file_fsync", "after_replace", "before_dir_fsync"
])
def test_atomic_write_fault_boundaries_never_yield_unparseable_final(tmp_path, fault):
    target = tmp_path / "checkpoint.json"
    old = cp(extended=100)
    new = cp(extended=101)
    write_checkpoint_atomic(target, old)
    old_bytes = target.read_bytes()

    with pytest.raises(OSError):
        write_checkpoint_atomic(target, new, fault_at=fault)

    # Before replace, old checkpoint remains; after replace, new checkpoint is
    # visible but durability is unconfirmed. Both are parseable; caller must
    # treat post-replace/pre-dir-fsync failure as uncertain and fail closed.
    current = decode_checkpoint(target.read_bytes())
    if fault in ("after_temp_write", "after_file_fsync"):
        assert current == old
        assert target.read_bytes() == old_bytes
    else:
        assert current == new


def test_checkpoint_rejects_inconsistent_wire_sequence():
    with pytest.raises(ValueError):
        EpochCheckpoint(1, 65537, 0)


def test_invalid_boot_identity_is_unresolved():
    assert resolve_checkpoint(None, -1).status is S.UNRESOLVED_INVALID


@pytest.mark.parametrize("raw", [b"[]", b'"string"', b'{"payload": [], "sha256": "x"}'])
def test_non_object_checkpoint_payload_fails_closed(raw):
    result = resolve_checkpoint(raw, cp().boot_id64)
    assert result.status is S.UNRESOLVED_CORRUPT
    assert result.checkpoint is None



def test_same_epoch_checkpoint_restores_tracker_but_not_prior_payload():
    raw = encode_checkpoint(cp(extended=65536))
    resolution, tracker = restore_sequence_tracker(raw, cp().boot_id64)
    assert resolution.status is S.RESUME_SAME_EPOCH
    assert tracker is not None
    replay = tracker.observe(0, b"cannot-prove-duplicate")
    assert replay.disposition.value == "unverified_replay"
    assert not replay.accepted
    next_frame = tracker.observe(1, b"next")
    assert next_frame.extended_sequence == 65537
    assert next_frame.accepted


def test_missing_or_mismatched_checkpoint_never_creates_tracker():
    missing, tracker = restore_sequence_tracker(None, cp().boot_id64)
    assert missing.status is S.UNRESOLVED_MISSING
    assert tracker is None
    mismatch, tracker = restore_sequence_tracker(
        encode_checkpoint(cp(boot=0x0000000100000001)),
        0x0000000200000001,
    )
    assert mismatch.status is S.UNRESOLVED_BOOT_MISMATCH
    assert tracker is None
