"""Host-side full boot-epoch checkpoint validation for 310-5.

This is a host persistence helper only. It does not alter RawLog or firmware.
A changed full boot_id64 starts a new epoch only when the caller supplies
independent confirmation that a real MCU reboot occurred.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Optional


class CheckpointStatus(str, Enum):
    RESUME_SAME_EPOCH = "resume_same_epoch"
    NEW_CONFIRMED_EPOCH = "new_confirmed_epoch"
    UNRESOLVED_MISSING = "unresolved_missing"
    UNRESOLVED_CORRUPT = "unresolved_corrupt"
    UNRESOLVED_BOOT_MISMATCH = "unresolved_boot_mismatch"
    UNRESOLVED_INVALID = "unresolved_invalid"


@dataclass(frozen=True)
class EpochCheckpoint:
    boot_id64: int
    extended_sequence: int
    wire_sequence: int

    def __post_init__(self):
        if isinstance(self.boot_id64, bool) or not isinstance(self.boot_id64, int):
            raise TypeError("boot_id64 must be an integer")
        if not 0 <= self.boot_id64 <= 0xFFFFFFFFFFFFFFFF:
            raise ValueError("boot_id64 must fit uint64")
        if isinstance(self.extended_sequence, bool) or not isinstance(self.extended_sequence, int):
            raise TypeError("extended_sequence must be an integer")
        if self.extended_sequence < 0:
            raise ValueError("extended_sequence cannot be negative")
        if isinstance(self.wire_sequence, bool) or not isinstance(self.wire_sequence, int):
            raise TypeError("wire_sequence must be an integer")
        if not 0 <= self.wire_sequence <= 0xFFFF:
            raise ValueError("wire_sequence must fit uint16")
        if self.extended_sequence & 0xFFFF != self.wire_sequence:
            raise ValueError("wire sequence must equal low 16 bits of extended sequence")


@dataclass(frozen=True)
class CheckpointResolution:
    status: CheckpointStatus
    checkpoint: Optional[EpochCheckpoint]
    detail: str


def _canonical_payload(checkpoint: EpochCheckpoint) -> bytes:
    body = {
        "format": "310-host-epoch-checkpoint-v1",
        "boot_id64": checkpoint.boot_id64,
        "extended_sequence": checkpoint.extended_sequence,
        "wire_sequence": checkpoint.wire_sequence,
    }
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")


def encode_checkpoint(checkpoint: EpochCheckpoint) -> bytes:
    payload = _canonical_payload(checkpoint)
    envelope = {
        "payload": json.loads(payload.decode("utf-8")),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    return (json.dumps(envelope, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def decode_checkpoint(raw: bytes) -> EpochCheckpoint:
    if not isinstance(raw, bytes):
        raise TypeError("checkpoint bytes required")
    envelope = json.loads(raw.decode("utf-8"))
    if set(envelope) != {"payload", "sha256"}:
        raise ValueError("invalid checkpoint envelope")
    payload = envelope["payload"]
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if not isinstance(envelope["sha256"], str) or not hashlib.compare_digest(
        hashlib.sha256(canonical).hexdigest(), envelope["sha256"]
    ):
        raise ValueError("checkpoint checksum mismatch")
    if payload.get("format") != "310-host-epoch-checkpoint-v1":
        raise ValueError("unsupported checkpoint format")
    if set(payload) != {"format", "boot_id64", "extended_sequence", "wire_sequence"}:
        raise ValueError("unexpected checkpoint fields")
    return EpochCheckpoint(
        boot_id64=payload["boot_id64"],
        extended_sequence=payload["extended_sequence"],
        wire_sequence=payload["wire_sequence"],
    )


def resolve_checkpoint(
    raw: Optional[bytes],
    observed_boot_id64: int,
    *,
    reboot_confirmed: bool = False,
) -> CheckpointResolution:
    """Resolve checkpoint against full observed boot ID; never infer reboot."""
    if isinstance(observed_boot_id64, bool) or not isinstance(observed_boot_id64, int):
        return CheckpointResolution(CheckpointStatus.UNRESOLVED_INVALID, None,
                                    "observed boot_id64 is not an integer")
    if not 0 <= observed_boot_id64 <= 0xFFFFFFFFFFFFFFFF:
        return CheckpointResolution(CheckpointStatus.UNRESOLVED_INVALID, None,
                                    "observed boot_id64 is outside uint64")
    if raw is None:
        return CheckpointResolution(CheckpointStatus.UNRESOLVED_MISSING, None,
                                    "checkpoint absent; sequence continuity is unproven")
    try:
        checkpoint = decode_checkpoint(raw)
    except (ValueError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
        return CheckpointResolution(CheckpointStatus.UNRESOLVED_CORRUPT, None,
                                    f"checkpoint cannot be trusted: {exc}")
    if checkpoint.boot_id64 == observed_boot_id64:
        return CheckpointResolution(CheckpointStatus.RESUME_SAME_EPOCH, checkpoint,
                                    "full boot ID matches; preserve sequence across sessions")
    if reboot_confirmed:
        return CheckpointResolution(CheckpointStatus.NEW_CONFIRMED_EPOCH, None,
                                    "full boot ID changed and reboot independently confirmed")
    return CheckpointResolution(CheckpointStatus.UNRESOLVED_BOOT_MISMATCH, None,
                                "full boot ID changed but reboot is not independently confirmed")


def write_checkpoint_atomic(path: os.PathLike | str, checkpoint: EpochCheckpoint,
                            *, fault_at: Optional[str] = None) -> None:
    """Persist via temp fsync -> replace -> directory fsync.

    fault_at supports deterministic host tests at named boundaries:
    after_temp_write, after_file_fsync, after_replace, before_dir_fsync.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = encode_checkpoint(checkpoint)
    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp",
                                     dir=str(target.parent))
    temp_path = Path(temp_name)
    replaced = False
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            if fault_at == "after_temp_write":
                raise OSError("injected failure after temp write")
            os.fsync(stream.fileno())
            if fault_at == "after_file_fsync":
                raise OSError("injected failure after file fsync")
        os.replace(temp_path, target)
        replaced = True
        if fault_at == "after_replace":
            raise OSError("injected failure after replace")
        if fault_at == "before_dir_fsync":
            raise OSError("injected failure before directory fsync")
        dir_fd = os.open(str(target.parent), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        if not replaced:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass
