import pytest

from measurement_310.sequence_reconciliation import (
    SequenceReconciliationStatus as S,
    reconcile_device_sequence,
)

BOOT = 0x123456789ABCDEF0


def reconcile(device_next, host_next, *, device_boot=BOOT, host_boot=BOOT,
              verified=True):
    return reconcile_device_sequence(
        device_boot_id64=device_boot,
        device_next_sequence64=device_next,
        host_boot_id64=host_boot,
        host_next_sequence64=host_next,
        device_identity_verified=verified,
    )


def test_equal_device_and_host_high_water_is_contiguous():
    r = reconcile(900, 900)
    assert r.status is S.CONTIGUOUS
    assert r.resume_from_sequence64 == 900
    assert r.gap_start_sequence64 is None


def test_host_checkpoint_rollback_does_not_rewind_device_sequence():
    # The stale host checkpoint says 100, while the live device says 140.
    # The only safe resume point is the device value; the intervening interval
    # is exposed for RawLog/Evidence reconciliation.
    r = reconcile(140, 100)
    assert r.status is S.GAP_UNATTRIBUTABLE
    assert r.resume_from_sequence64 == 140
    assert (r.gap_start_sequence64, r.gap_end_sequence64_exclusive) == (100, 140)


def test_device_sequence_behind_durable_host_high_water_fails_closed():
    r = reconcile(100, 140)
    assert r.status is S.UNRESOLVED_DEVICE_ROLLBACK
    assert r.resume_from_sequence64 is None


def test_new_verified_full_boot_id_starts_new_epoch():
    r = reconcile(0, 500, device_boot=BOOT + 1, host_boot=BOOT)
    assert r.status is S.NEW_DEVICE_EPOCH
    assert r.resume_from_sequence64 == 0


def test_missing_host_high_water_is_explicitly_unattributable():
    r = reconcile_device_sequence(
        device_boot_id64=BOOT, device_next_sequence64=80,
        host_boot_id64=BOOT, host_next_sequence64=None,
        device_identity_verified=True,
    )
    assert r.status is S.GAP_UNATTRIBUTABLE
    assert (r.gap_start_sequence64, r.gap_end_sequence64_exclusive) == (0, 80)


def test_unverified_identity_cannot_resume():
    r = reconcile(20, 20, verified=False)
    assert r.status is S.UNRESOLVED_IDENTITY
    assert r.resume_from_sequence64 is None


@pytest.mark.parametrize("device_next", [-1, True, 1 << 64])
def test_invalid_device_sequence_fails_closed(device_next):
    r = reconcile_device_sequence(
        device_boot_id64=BOOT, device_next_sequence64=device_next,
        host_boot_id64=BOOT, host_next_sequence64=0,
        device_identity_verified=True,
    )
    assert r.status is S.UNRESOLVED_INVALID


def test_uint64_max_is_valid_but_no_wrap_is_represented():
    r = reconcile((1 << 64) - 1, (1 << 64) - 1)
    assert r.status is S.CONTIGUOUS
    assert r.resume_from_sequence64 == (1 << 64) - 1
