"""Per-channel, device-clock, half-open 1-second ADC loss windows for protocol v2."""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Optional

CHANNEL_ORDER = (0, 1, 4, 5, 2, 3)
CHANNEL_NAMES = {0: "A0", 1: "A1", 2: "A2", 3: "A3", 4: "A4", 5: "A5"}
WINDOW_US = 1_000_000
EXPECTED_PER_CHANNEL = 20
UINT32_MASK = 0xFFFFFFFF
UINT32_HALF = 0x80000000


class DeviceLossAccountingError(ValueError):
    pass


@dataclass(frozen=True)
class ChannelWindow:
    channel: str
    expected: Optional[int]
    attempted: int
    valid: int
    invalid: int
    missing: Optional[int]
    not_acquired: int
    unattributable_slots: int
    status: str


@dataclass(frozen=True)
class DeviceLossWindow:
    boot_id64: int
    stage_context_token: Optional[int]
    window_index: int
    start_elapsed_us: int
    end_elapsed_us: int
    channels: tuple[ChannelWindow, ...]
    status: str


@dataclass(frozen=True)
class DeviceClockCheckpoint:
    sample_sequence64: int
    timestamp_us_u32: int
    elapsed_us: int


def load_latest_device_clock_checkpoint(
    rawlog_root, boot_id64: int
) -> Optional[DeviceClockCheckpoint]:
    """Find the latest durable valid ADC_SAMPLE clock point for this boot epoch.

    Only RawLog v2 records are considered. Historical v1 data is never parsed
    or migrated. Duplicate copies from recovery/original packages are allowed
    only when sequence, raw timestamp and elapsed coordinate are identical.
    """
    if isinstance(boot_id64, bool) or not isinstance(boot_id64, int) or not 0 < boot_id64 <= 0xFFFFFFFFFFFFFFFF:
        raise DeviceLossAccountingError("boot_id64 must be a nonzero uint64")
    if rawlog_root is None:
        return None
    root = os.fspath(rawlog_root)
    if not os.path.exists(root):
        return None
    if os.path.islink(root) or not os.path.isdir(root):
        raise DeviceLossAccountingError("RawLog clock-checkpoint root must be a real directory")
    epoch_id = f"{boot_id64:016X}"
    points: dict[int, tuple[int, int]] = {}
    for directory, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        dirnames[:] = [
            name for name in dirnames
            if not os.path.islink(os.path.join(directory, name))
        ]
        if "records.jsonl" not in filenames:
            continue
        path = os.path.join(directory, "records.jsonl")
        if os.path.islink(path) or not os.path.isfile(path):
            raise DeviceLossAccountingError("RawLog records.jsonl checkpoint source is not a regular file")
        try:
            with open(path, "r", encoding="utf-8") as stream:
                for line_number, line in enumerate(stream, 1):
                    if not line.endswith("\n"):
                        raise DeviceLossAccountingError(
                            f"truncated RawLog v2 records.jsonl at {path}:{line_number}"
                        )
                    try:
                        record = json.loads(line)
                    except (TypeError, ValueError) as exc:
                        raise DeviceLossAccountingError(
                            f"invalid RawLog v2 JSON at {path}:{line_number}"
                        ) from exc
                    if (not isinstance(record, dict)
                            or record.get("record_type") != "ADC_SAMPLE"
                            or record.get("device_epoch_id") != epoch_id
                            or record.get("validity") != "valid"):
                        continue
                    sequence = record.get("device_sample_sequence")
                    timestamp = record.get("device_timestamp_us_u32")
                    elapsed = record.get("device_elapsed_us")
                    if (isinstance(sequence, bool) or not isinstance(sequence, int)
                            or not 0 <= sequence <= 0xFFFFFFFFFFFFFFFF
                            or isinstance(timestamp, bool) or not isinstance(timestamp, int)
                            or not 0 <= timestamp <= UINT32_MASK
                            or isinstance(elapsed, bool) or not isinstance(elapsed, int)
                            or elapsed < 0):
                        raise DeviceLossAccountingError(
                            f"invalid valid ADC_SAMPLE clock fields at {path}:{line_number}"
                        )
                    point = (timestamp, elapsed)
                    previous = points.get(sequence)
                    if previous is not None and previous != point:
                        raise DeviceLossAccountingError(
                            "conflicting duplicate RawLog v2 clock checkpoint sequence"
                        )
                    points[sequence] = point
        except OSError as exc:
            raise DeviceLossAccountingError(f"cannot read RawLog v2 clock checkpoint source: {path}") from exc

    if not points:
        return None
    ordered = sorted(points.items())
    previous_sequence = None
    previous_timestamp = None
    previous_elapsed = None
    for sequence, (timestamp, elapsed) in ordered:
        if previous_sequence is not None:
            if sequence <= previous_sequence:
                raise DeviceLossAccountingError("RawLog v2 device sample sequence is not increasing")
            delta = (timestamp - previous_timestamp) & UINT32_MASK
            if delta >= UINT32_HALF:
                raise DeviceLossAccountingError("RawLog v2 clock checkpoint crosses an ambiguous micros() gap")
            if elapsed != previous_elapsed + delta:
                raise DeviceLossAccountingError("RawLog v2 device_elapsed_us is discontinuous within one device epoch")
        previous_sequence, previous_timestamp, previous_elapsed = sequence, timestamp, elapsed
    return DeviceClockCheckpoint(
        sample_sequence64=previous_sequence,
        timestamp_us_u32=previous_timestamp,
        elapsed_us=previous_elapsed,
    )


class DeviceEpochClockUnwrapper:
    """Track actual device time and map scheduled-but-unacquired slot times.

    Actual conversion/attempt timestamps advance the clock. NOT_ACQUIRED
    timestamps identify scheduled slot starts and may precede the previous
    conversion midpoint; they are mapped into the existing epoch coordinate
    without moving the actual-clock cursor backwards.
    """

    def __init__(
        self, boot_id64: int, *,
        checkpoint_timestamp_us_u32: Optional[int] = None,
        checkpoint_elapsed_us: Optional[int] = None,
    ):
        if isinstance(boot_id64, bool) or not isinstance(boot_id64, int) or not 0 <= boot_id64 <= 0xFFFFFFFFFFFFFFFF:
            raise ValueError("boot_id64 must be uint64")
        if (checkpoint_timestamp_us_u32 is None) != (checkpoint_elapsed_us is None):
            raise ValueError("device clock checkpoint requires both timestamp and elapsed values")
        if checkpoint_timestamp_us_u32 is not None:
            if (isinstance(checkpoint_timestamp_us_u32, bool)
                    or not isinstance(checkpoint_timestamp_us_u32, int)
                    or not 0 <= checkpoint_timestamp_us_u32 <= UINT32_MASK
                    or isinstance(checkpoint_elapsed_us, bool)
                    or not isinstance(checkpoint_elapsed_us, int)
                    or checkpoint_elapsed_us < 0):
                raise ValueError("invalid device clock checkpoint")
        self.boot_id64 = boot_id64
        self._origin_timestamp: Optional[int] = checkpoint_timestamp_us_u32
        self._last: Optional[int] = checkpoint_timestamp_us_u32
        self._elapsed: Optional[int] = checkpoint_elapsed_us
        self._high_water_elapsed: Optional[int] = checkpoint_elapsed_us

    @property
    def elapsed_us(self) -> Optional[int]:
        """Highest unwrapped device time observed, including scheduled slots."""
        return self._high_water_elapsed

    def add_actual(self, timestamp_us_u32: int) -> int:
        if isinstance(timestamp_us_u32, bool) or not isinstance(timestamp_us_u32, int) or not 0 <= timestamp_us_u32 <= UINT32_MASK:
            raise DeviceLossAccountingError("timestamp_us_u32 must be uint32")
        if self._last is None:
            if self._origin_timestamp is None:
                self._origin_timestamp = timestamp_us_u32
                elapsed = 0
            else:
                delta = (timestamp_us_u32 - self._origin_timestamp) & UINT32_MASK
                if delta >= UINT32_HALF:
                    raise DeviceLossAccountingError("actual device timestamp is ambiguous relative to epoch origin")
                elapsed = delta
        else:
            delta = (timestamp_us_u32 - self._last) & UINT32_MASK
            if delta >= UINT32_HALF:
                raise DeviceLossAccountingError(
                    "actual device timestamp ordering is ambiguous within this boot epoch"
                )
            elapsed = int(self._elapsed) + delta
        self._last = timestamp_us_u32
        self._elapsed = elapsed
        self._high_water_elapsed = (
            elapsed if self._high_water_elapsed is None
            else max(self._high_water_elapsed, elapsed)
        )
        return elapsed

    def map_scheduled(self, timestamp_us_u32: int) -> tuple[int, bool]:
        """Map a NOT_ACQUIRED scheduled slot start without rewinding actual time.

        Returns (elapsed_us, unattributable_before_origin). A schedule timestamp
        slightly before the first observed actual sample is clamped to the
        origin and marks that first window UNATTRIBUTABLE.
        """
        if isinstance(timestamp_us_u32, bool) or not isinstance(timestamp_us_u32, int) or not 0 <= timestamp_us_u32 <= UINT32_MASK:
            raise DeviceLossAccountingError("scheduled timestamp_us_u32 must be uint32")
        if self._last is None:
            if self._origin_timestamp is None:
                self._origin_timestamp = timestamp_us_u32
                elapsed = 0
                self._high_water_elapsed = 0
                return elapsed, False
            delta = (timestamp_us_u32 - self._origin_timestamp) & UINT32_MASK
            if delta < UINT32_HALF:
                elapsed = delta
                self._high_water_elapsed = max(self._high_water_elapsed or 0, elapsed)
                return elapsed, False
            age = (self._origin_timestamp - timestamp_us_u32) & UINT32_MASK
            if age < UINT32_HALF:
                return 0, True
            raise DeviceLossAccountingError("scheduled timestamp is ambiguous relative to epoch origin")

        delta = (timestamp_us_u32 - self._last) & UINT32_MASK
        if delta < UINT32_HALF:
            elapsed = int(self._elapsed) + delta
            self._high_water_elapsed = max(self._high_water_elapsed or 0, elapsed)
            return elapsed, False
        age = (self._last - timestamp_us_u32) & UINT32_MASK
        if age < UINT32_HALF:
            if age <= int(self._elapsed):
                return int(self._elapsed) - age, False
            return 0, True
        raise DeviceLossAccountingError("scheduled timestamp is ambiguous within this boot epoch")

    # Backward-compatible name for callers/tests that provide actual timestamps.
    def add(self, timestamp_us_u32: int) -> int:
        return self.add_actual(timestamp_us_u32)


class DeviceLossWindowAccumulator:
    """Accumulate per-channel [n*1s,(n+1)*1s) windows for one device epoch.

    One accumulator is retained across all ARM/stage contexts in the same
    verified boot epoch. Its elapsed coordinate starts at the first scheduled
    slot observed by this host session and is never reset at a stage boundary.
    A sequence gap or incomplete terminal window is UNATTRIBUTABLE; it is
    never spread across channels by guesswork.
    """

    def __init__(
        self, boot_id64: int, stage_context_token: Optional[int] = None, *,
        checkpoint_timestamp_us_u32: Optional[int] = None,
        checkpoint_elapsed_us: Optional[int] = None,
    ):
        if isinstance(boot_id64, bool) or not isinstance(boot_id64, int) or not 0 <= boot_id64 <= 0xFFFFFFFFFFFFFFFF:
            raise ValueError("boot_id64 must be uint64")
        if stage_context_token is not None and (
            isinstance(stage_context_token, bool) or not isinstance(stage_context_token, int)
            or not 0 <= stage_context_token <= 0xFFFF
        ):
            raise ValueError("stage_context_token must be uint16 or None")
        self.boot_id64 = boot_id64
        self.stage_context_token = stage_context_token
        if (checkpoint_timestamp_us_u32 is None) != (checkpoint_elapsed_us is None):
            raise ValueError("loss-window checkpoint requires both timestamp and elapsed values")
        if checkpoint_timestamp_us_u32 is not None:
            if (isinstance(checkpoint_timestamp_us_u32, bool)
                    or not isinstance(checkpoint_timestamp_us_u32, int)
                    or not 0 <= checkpoint_timestamp_us_u32 <= UINT32_MASK
                    or isinstance(checkpoint_elapsed_us, bool)
                    or not isinstance(checkpoint_elapsed_us, int)
                    or checkpoint_elapsed_us < 0):
                raise ValueError("invalid loss-window checkpoint")
        self._origin: Optional[int] = checkpoint_timestamp_us_u32
        self._last: Optional[int] = checkpoint_timestamp_us_u32
        self._elapsed = int(checkpoint_elapsed_us or 0)
        self._window_index = self._elapsed // WINDOW_US
        self._counts = self._empty_counts()
        self._unattributable = checkpoint_timestamp_us_u32 is not None
        self._unattributable_slots = 0
        self._unattributable_windows: set[int] = (
            {self._window_index} if checkpoint_timestamp_us_u32 is not None else set()
        )
        self._gap_slots_by_window: dict[int, int] = {}
        self._fallback_clock = DeviceEpochClockUnwrapper(
            boot_id64,
            checkpoint_timestamp_us_u32=checkpoint_timestamp_us_u32,
            checkpoint_elapsed_us=checkpoint_elapsed_us,
        )
        self._closed = False

    @staticmethod
    def _empty_counts():
        return {
            name: {"slots": 0, "attempted": 0, "valid": 0, "invalid": 0, "not_acquired": 0}
            for name in ("A0", "A1", "A2", "A3", "A4", "A5")
        }

    @property
    def window_elapsed_us(self) -> Optional[int]:
        """Device-epoch elapsed coordinate used for 1-second loss-window boundaries."""
        return self._elapsed if self._origin is not None else None

    def add_batch(self, samples: list[dict], *, gap_slots: int = 0) -> list[DeviceLossWindow]:
        if self._closed:
            raise DeviceLossAccountingError("accounting epoch is closed")
        if not isinstance(samples, list) or len(samples) != 12:
            raise DeviceLossAccountingError("each ADC_BATCH must contain 12 sample slots")
        if isinstance(gap_slots, bool) or not isinstance(gap_slots, int) or gap_slots < 0:
            raise DeviceLossAccountingError("gap_slots must be a nonnegative integer")

        entries = []
        for i, sample in enumerate(samples):
            if not isinstance(sample, dict) or sample.get("channel_code") != CHANNEL_ORDER[i % 6]:
                raise DeviceLossAccountingError("ADC_BATCH channel order is not A0,A1,A4,A5,A2,A3 twice")
            status = sample.get("acquisition_status")
            if isinstance(status, bool) or not isinstance(status, int) or status not in (0, 1, 2, 3):
                raise DeviceLossAccountingError("invalid acquisition status")
            timestamp = sample.get("timestamp_us_u32")
            if isinstance(timestamp, bool) or not isinstance(timestamp, int) or not 0 <= timestamp <= UINT32_MASK:
                raise DeviceLossAccountingError("timestamp_us_u32 must be uint32")

            if "_loss_window_elapsed_us" in sample:
                elapsed = sample["_loss_window_elapsed_us"]
                before_origin = bool(sample.get("_loss_window_unattributable", False))
            elif status == 3:
                elapsed, before_origin = self._fallback_clock.map_scheduled(timestamp)
            else:
                elapsed = self._fallback_clock.add_actual(timestamp)
                before_origin = False
            if isinstance(elapsed, bool) or not isinstance(elapsed, int) or elapsed < 0:
                raise DeviceLossAccountingError("loss-window elapsed coordinate must be nonnegative integer")
            entries.append((elapsed, sample, before_origin))

        if not entries:
            return []
        previous_elapsed = self._elapsed if self._origin is not None else None
        minimum_elapsed = min(item[0] for item in entries)
        maximum_elapsed = max(item[0] for item in entries)
        if self._origin is None:
            self._origin = 0
            self._elapsed = minimum_elapsed
            self._window_index = minimum_elapsed // WINDOW_US

        if gap_slots:
            first_window = (
                previous_elapsed if previous_elapsed is not None else minimum_elapsed
            ) // WINDOW_US
            last_window = maximum_elapsed // WINDOW_US
            for index in range(first_window, last_window + 1):
                self._unattributable_windows.add(index)
            self._gap_slots_by_window[first_window] = (
                self._gap_slots_by_window.get(first_window, 0) + gap_slots
            )

        completed: list[DeviceLossWindow] = []
        # NOT_ACQUIRED slots carry scheduled-slot timestamps. They may be
        # slightly earlier than a conversion midpoint in the same ADC batch,
        # so bucket the complete batch by window before finalizing any window.
        for elapsed, sample, before_origin in sorted(entries, key=lambda item: (item[0] // WINDOW_US, item[0])):
            target_window = elapsed // WINDOW_US
            if target_window < self._window_index:
                raise DeviceLossAccountingError(
                    "late scheduled ADC slot arrived after its device-epoch window was finalized"
                )
            while self._window_index < target_window:
                self._unattributable = self._window_index in self._unattributable_windows
                self._unattributable_slots = self._gap_slots_by_window.get(self._window_index, 0)
                completed.append(self._finish_current())
                self._window_index += 1
                self._counts = self._empty_counts()
            if before_origin:
                self._unattributable_windows.add(target_window)
            self._unattributable = self._window_index in self._unattributable_windows
            self._unattributable_slots = self._gap_slots_by_window.get(self._window_index, 0)

            name = CHANNEL_NAMES[sample["channel_code"]]
            counts = self._counts[name]
            counts["slots"] += 1
            status = sample["acquisition_status"]
            if status == 0:
                counts["attempted"] += 1
                counts["valid"] += 1
            elif status in (1, 2):
                counts["attempted"] += 1
                counts["invalid"] += 1
            else:
                counts["not_acquired"] += 1

        self._elapsed = max(self._elapsed, maximum_elapsed)
        return completed

    def _finish_current(self, *, terminal: bool = False) -> DeviceLossWindow:
        channels = []
        window_status = "PASS"
        for name in ("A0", "A1", "A2", "A3", "A4", "A5"):
            item = self._counts[name]
            complete_slots = item["slots"] == EXPECTED_PER_CHANNEL
            attributable = not self._unattributable and complete_slots
            if attributable:
                expected: Optional[int] = EXPECTED_PER_CHANNEL
                missing: Optional[int] = expected - item["attempted"]
                status = "PASS" if missing == item["not_acquired"] else "FAIL"
                if status == "FAIL":
                    window_status = "FAIL"
            else:
                expected = EXPECTED_PER_CHANNEL if not terminal else None
                missing = None
                status = "UNATTRIBUTABLE"
                window_status = "UNATTRIBUTABLE"
            channels.append(ChannelWindow(
                channel=name, expected=expected, attempted=item["attempted"],
                valid=item["valid"], invalid=item["invalid"], missing=missing,
                not_acquired=item["not_acquired"],
                unattributable_slots=self._unattributable_slots,
                status=status,
            ))
        return DeviceLossWindow(
            boot_id64=self.boot_id64, stage_context_token=self.stage_context_token,
            window_index=self._window_index, start_elapsed_us=self._window_index * WINDOW_US,
            end_elapsed_us=(self._window_index + 1) * WINDOW_US,
            channels=tuple(channels), status=window_status,
        )

    def finalize(self) -> Optional[DeviceLossWindow]:
        if self._closed:
            return None
        self._closed = True
        if self._origin is None:
            return None
        if not any(item["slots"] for item in self._counts.values()):
            return None
        return self._finish_current(terminal=True)
