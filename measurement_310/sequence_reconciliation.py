"""Reconcile device-owned uint64 sample sequence after host restart (310 protocol v2)."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


UINT64_MAX = 0xFFFFFFFFFFFFFFFF


class SequenceReconciliationStatus(str, Enum):
    CONTIGUOUS = "contiguous"
    GAP_UNATTRIBUTABLE = "gap_unattributable"
    NEW_DEVICE_EPOCH = "new_device_epoch"
    UNRESOLVED_DEVICE_ROLLBACK = "unresolved_device_rollback"
    UNRESOLVED_IDENTITY = "unresolved_identity"
    UNRESOLVED_INVALID = "unresolved_invalid"


@dataclass(frozen=True)
class SequenceReconciliation:
    status: SequenceReconciliationStatus
    boot_id64: Optional[int]
    resume_from_sequence64: Optional[int]
    gap_start_sequence64: Optional[int]
    gap_end_sequence64_exclusive: Optional[int]
    detail: str


def reconcile_device_sequence(
    *,
    device_boot_id64: int,
    device_next_sequence64: int,
    host_boot_id64: Optional[int],
    host_next_sequence64: Optional[int],
    device_identity_verified: bool,
) -> SequenceReconciliation:
    """Use the live device sequence as authority; a host checkpoint never rewinds it.

    host_next_sequence64 is the exclusive high-water derived by scanning durable
    RawLog and transport Evidence, not merely a cached checkpoint. If the host
    copy is older than the live device, the omitted interval is explicitly
    unattributable until the append-only evidence inventory is reconciled.
    """
    def unresolved(status: SequenceReconciliationStatus, detail: str):
        return SequenceReconciliation(status, None, None, None, None, detail)

    for name, value in (
        ("device_boot_id64", device_boot_id64),
        ("device_next_sequence64", device_next_sequence64),
    ):
        if isinstance(value, bool) or not isinstance(value, int):
            return unresolved(SequenceReconciliationStatus.UNRESOLVED_INVALID, f"{name} is not an integer")
        maximum = 0xFFFFFFFFFFFFFFFF
        minimum = 1 if name == "device_boot_id64" else 0
        if not minimum <= value <= maximum:
            return unresolved(SequenceReconciliationStatus.UNRESOLVED_INVALID, f"{name} is out of range")
    if not device_identity_verified:
        return unresolved(SequenceReconciliationStatus.UNRESOLVED_IDENTITY,
                          "HELLO did not verify the committed full boot identity")
    if (host_boot_id64 is not None and
            (isinstance(host_boot_id64, bool) or not isinstance(host_boot_id64, int)
             or not 1 <= host_boot_id64 <= 0xFFFFFFFFFFFFFFFF)):
        return unresolved(SequenceReconciliationStatus.UNRESOLVED_INVALID, "host_boot_id64 is invalid")
    if (host_next_sequence64 is not None and
            (isinstance(host_next_sequence64, bool) or not isinstance(host_next_sequence64, int)
             or not 0 <= host_next_sequence64 <= UINT64_MAX)):
        return unresolved(SequenceReconciliationStatus.UNRESOLVED_INVALID, "host_next_sequence64 is invalid")

    if host_boot_id64 is None:
        if host_next_sequence64 is not None:
            return unresolved(SequenceReconciliationStatus.UNRESOLVED_IDENTITY,
                              "host sequence high-water has no verified boot identity")
        return SequenceReconciliation(
            SequenceReconciliationStatus.GAP_UNATTRIBUTABLE,
            device_boot_id64, device_next_sequence64, 0, device_next_sequence64,
            "no durable host high-water exists; prior device sequence is unattributable",
        )

    if host_boot_id64 != device_boot_id64:
        return SequenceReconciliation(
            SequenceReconciliationStatus.NEW_DEVICE_EPOCH, device_boot_id64,
            device_next_sequence64, None, None,
            "verified full boot identity changed; sequence is scoped to the new device epoch",
        )

    if host_next_sequence64 is None:
        return SequenceReconciliation(
            SequenceReconciliationStatus.GAP_UNATTRIBUTABLE, device_boot_id64,
            device_next_sequence64, 0, device_next_sequence64,
            "same device epoch but no durable host sequence high-water exists",
        )
    if device_next_sequence64 < host_next_sequence64:
        return unresolved(
            SequenceReconciliationStatus.UNRESOLVED_DEVICE_ROLLBACK,
            "live device sequence is lower than durable host high-water for the same boot identity",
        )
    if device_next_sequence64 == host_next_sequence64:
        return SequenceReconciliation(
            SequenceReconciliationStatus.CONTIGUOUS, device_boot_id64,
            device_next_sequence64, None, None,
            "device and durable host sequence high-water match",
        )
    return SequenceReconciliation(
        SequenceReconciliationStatus.GAP_UNATTRIBUTABLE, device_boot_id64,
        device_next_sequence64, host_next_sequence64, device_next_sequence64,
        "device advanced beyond durable host records; gap must be recorded before resuming",
    )
