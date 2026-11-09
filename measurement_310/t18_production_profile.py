"""Full 310-stage Protocol v2 production-path T18 profile.

This harness uses the production ProtocolV2HostSession, SequenceController,
RawLog v2 writer, loss accounting, command-intent journal and Evidence journal.
Only the serial transport/device and clock are deterministic in-memory adapters;
all persistence writes and fsync calls use the selected host filesystem.

Run:
    python -m measurement_310.t18_production_profile --output-dir ./artifacts/310-t18-production
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import struct
import time
import uuid
from datetime import datetime, timezone

from raw_log_v2 import RawLogV2Writer, parse_complete_jsonl, validate_package
from .device_loss_accounting import CHANNEL_ORDER
from .evidence_bundle import verify_evidence_bundle
from .protocol_v2 import (
    DriveDirection, MessageType, PROTOCOL_V2_MAGIC, PROTOCOL_V2_VERSION,
    ProtocolV2Codec, StopReason, epoch_tag_for_boot_id,
)
from .protocol_v2_session import ProtocolV2HostSession
from .protocol_v1_session import TransportEvidenceJournal


BOOT_ID64 = 0x3105102026110601
SLOTS_PER_BATCH = 12
BATCHES_PER_STAGE = 100
SLOTS_PER_STAGE = SLOTS_PER_BATCH * BATCHES_PER_STAGE
STAGE_BUDGET_NS = 8_000_000_000
CHANNEL_NAME = {0: "A0", 1: "A1", 2: "A2", 3: "A3", 4: "A4", 5: "A5"}


class DeterministicClock:
    def __init__(self):
        self.ns = 1_000_000_000

    def monotonic_ns(self) -> int:
        return self.ns

    def monotonic(self) -> float:
        return self.ns / 1_000_000_000

    def utc_now(self) -> str:
        # UTC is observational wall time; only the monotonic sequence clock is
        # virtualized. This keeps RawLog created_at_utc >= ended_at_utc.
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    def advance_stage(self) -> None:
        self.ns += 10_000_000_000


class InMemoryProtocolV2Transport:
    """Wire-level deterministic peer; every host frame is decoded by the real codec."""

    def __init__(self, codec: ProtocolV2Codec):
        self.codec = codec
        self.connected = False
        self.incoming: list[bytes] = []
        self.sent: list[bytes] = []

    def connect(self) -> None:
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False

    def send(self, payload: bytes) -> None:
        if not self.connected:
            raise RuntimeError("profile transport is disconnected")
        frame = bytes(payload)
        self.sent.append(frame)
        request = self.codec.decode(frame).message
        kind = request["kind"]
        session_id = request["measurement_session_id"]
        epoch = epoch_tag_for_boot_id(BOOT_ID64)
        if kind == "HELLO":
            response = self.codec.encode_message(
                MessageType.HELLO_ACK, session_id=session_id, epoch_tag=epoch,
                payload=struct.pack(
                    "<BQQQ", 0, BOOT_ID64, request["host_nonce64"], 0
                ),
            )
        elif kind == "ARM":
            response = self.codec.encode_message(
                MessageType.ARM_ACK, session_id=session_id, epoch_tag=epoch,
                command_id=request["command_id"],
                payload=struct.pack(
                    "<BBHB", 0, 1, request["stage_context_token"],
                    request["direction_code"],
                ),
            )
        elif kind == "PWM_SET":
            response = self.codec.encode_message(
                MessageType.APPLY_ACK, session_id=session_id, epoch_tag=epoch,
                command_id=request["command_id"],
                payload=struct.pack(
                    "<BBH", 0, request["pwm"], request["stage_context_token"]
                ),
            )
        elif kind == "DISARM":
            response = self.codec.encode_message(
                MessageType.DISARM_ACK, session_id=session_id, epoch_tag=epoch,
                command_id=request["command_id"],
                payload=struct.pack("<BBH", 0, 0, request["stage_context_token"]),
            )
        else:
            raise RuntimeError(f"unexpected host frame in profile: {kind}")
        self.incoming.append(response)

    def receive(self, timeout_s: float):
        if not self.connected:
            raise RuntimeError("profile transport is disconnected")
        return self.incoming.pop(0) if self.incoming else None

    def queue_adc_batch(self, session_id: str, stage_token: int,
                        first_sequence: int) -> None:
        epoch = epoch_tag_for_boot_id(BOOT_ID64)
        payload = bytearray(struct.pack("<QBBB", first_sequence, 0, 12, 0))
        for offset in range(SLOTS_PER_BATCH):
            sequence = first_sequence + offset
            timestamp = ((sequence * 1_000_000) // 120) & 0xFFFFFFFF
            channel = CHANNEL_ORDER[offset % len(CHANNEL_ORDER)]
            payload.extend(struct.pack(
                "<IBHHBH", timestamp, channel, 512, stage_token, 0, 0
            ))
        frame = self.codec.encode_message(
            MessageType.ADC_BATCH, session_id=session_id, epoch_tag=epoch,
            payload=bytes(payload),
        )
        self.incoming.append(frame)


class InMemoryIndependentStopWriter:
    """Captures the independent STOP frame without opening a hardware endpoint."""

    def __init__(self):
        self.frames: list[bytes] = []

    def __call__(self, frame: bytes) -> None:
        self.frames.append(bytes(frame))


def _mount_for(path: Path) -> dict:
    target = str(path.resolve())
    best = {"mountpoint": None, "source": None, "filesystem": None}
    try:
        with open("/proc/mounts", encoding="utf-8") as stream:
            for line in stream:
                fields = line.split()
                if len(fields) < 3:
                    continue
                mountpoint = fields[1].replace("\\040", " ")
                if target == mountpoint or target.startswith(mountpoint.rstrip("/") + "/"):
                    if best["mountpoint"] is None or len(mountpoint) > len(best["mountpoint"]):
                        best = {
                            "mountpoint": mountpoint,
                            "source": fields[0],
                            "filesystem": fields[2],
                        }
    except OSError:
        pass
    return best


def _percentile(values: list[int], percentile: float) -> int:
    ordered = sorted(values)
    if not ordered:
        return 0
    index = max(0, min(len(ordered) - 1,
                       int((percentile / 100.0) * len(ordered) + 0.999999) - 1))
    return ordered[index]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest(root: Path, log_id: str, session_id: str, clock: DeterministicClock) -> dict:
    return {
        "log_id": log_id,
        "measurement_session_id": session_id,
        "started_at_utc": clock.utc_now(),
        "motor_instance_id": None,
        "device": {
            "type": "simulated_protocol_peer", "model": "protocol-v2-profile-peer",
            "firmware_version": "NOT_PHYSICAL", "firmware_build": "T18-PROFILE",
            "firmware_id": f"{BOOT_ID64:016X}", "adc_resolution_bits": 10,
        },
        "measurement_conditions": {
            "direction": "FWD", "voltage_control_mode": "UNKNOWN",
            "sweep_pwm_min": 0, "sweep_pwm_max": 30,
            "stage_duration_ms": 10000, "schedule_owner": "PYTHON",
        },
    }




class PersistenceProfiler:
    """Opt-in, observational timing for production persistence calls.

    It wraps os.fsync and RawLogV2Session.append_many only while the T18
    profile is running, then restores both functions. It never skips, batches,
    reorders, or changes any durability operation.
    """

    FSYNC_BUCKETS = (
        "rawlog_records_file", "rawlog_work_state_file",
        "evidence_file", "command_intent_file", "rawlog_directory",
        "evidence_directory", "command_intent_directory", "other_file",
        "other_directory",
    )

    def __init__(self):
        from collections import defaultdict
        self.current_stage = -1
        self._stats = defaultdict(lambda: defaultdict(
            lambda: {"count": 0, "total_ns": 0, "max_ns": 0}
        ))
        self._original_fsync = None
        self._original_append_many = None
        self._storage_module = None
        self._phase_stats = defaultdict(lambda: defaultdict(
            lambda: {"count": 0, "total_ns": 0, "max_ns": 0}
        ))
        self._phase_patches = []

    def _record_phase(self, stage, key, elapsed_ns):
        row = self._phase_stats[stage][key]
        row["count"] += 1
        row["total_ns"] += elapsed_ns
        row["max_ns"] = max(row["max_ns"], elapsed_ns)

    def _measure_method(self, owner, attribute, key):
        original = getattr(owner, attribute)
        profiler = self

        def measured(*args, **kwargs):
            started = time.perf_counter_ns()
            try:
                return original(*args, **kwargs)
            finally:
                profiler._record_phase(
                    profiler.current_stage, key, time.perf_counter_ns() - started
                )

        setattr(owner, attribute, measured)
        self._phase_patches.append((owner, attribute, original))

    @staticmethod
    def _fd_path(fd):
        try:
            return os.readlink(f"/proc/self/fd/{fd}")
        except OSError:
            return "<unresolved-fd>"

    @classmethod
    def _fsync_bucket(cls, fd):
        path = cls._fd_path(fd)
        try:
            is_directory = os.path.isdir(f"/proc/self/fd/{fd}")
        except OSError:
            is_directory = False
        name = Path(path).name
        if not is_directory:
            if name == "records.jsonl":
                return "rawlog_records_file"
            if name.startswith(".state-"):
                return "rawlog_work_state_file"
            if name == "transport-evidence-v1.jsonl":
                return "evidence_file"
            if name == "command-intents-v1.jsonl":
                return "command_intent_file"
            return "other_file"
        if ".transport-evidence" in path:
            return "evidence_directory"
        if ".command-intents" in path:
            return "command_intent_directory"
        if "/rawlog/" in path or path.endswith("/rawlog"):
            return "rawlog_directory"
        return "other_directory"

    def _record(self, stage, key, elapsed_ns):
        row = self._stats[stage][key]
        row["count"] += 1
        row["total_ns"] += elapsed_ns
        row["max_ns"] = max(row["max_ns"], elapsed_ns)

    def __enter__(self):
        from raw_log_v2 import storage
        self._storage_module = storage
        self._original_fsync = os.fsync
        self._original_append_many = storage.RawLogV2Session.append_many
        profiler = self

        # Attribute the final-stage outlier to production operations without
        # changing ordering, durability, payloads, or failure behavior.
        from .engine import SequenceController
        from .protocol_v2_session import ProtocolV2HostSession
        from . import evidence_bundle
        self._measure_method(SequenceController, "_finish_stage", "sequence_finish_stage")
        self._measure_method(SequenceController, "_complete", "sequence_complete")
        self._measure_method(storage.RawLogV2Session, "finalize", "rawlog_finalize")
        self._measure_method(
            storage.RawLogV2Session, "_persist_work_state_checkpoint",
            "rawlog_checkpoint",
        )
        self._measure_method(
            storage.RawLogV2Writer, "_publish_package", "rawlog_publish_package"
        )
        self._measure_method(storage, "parse_complete_jsonl", "rawlog_parse_jsonl")
        self._measure_method(storage, "validate_package", "rawlog_validate_package")
        self._measure_method(
            ProtocolV2HostSession, "finalize_evidence_bundle",
            "evidence_bundle_finalize",
        )
        self._measure_method(
            evidence_bundle, "write_evidence_bundle_manifest",
            "evidence_manifest_write",
        )
        self._measure_method(storage, "_atomic_replace_json", "rawlog_atomic_state_write")
        self._measure_method(storage, "_publish_new_file", "rawlog_publish_file")
        self._measure_method(storage, "_fsync_dir", "rawlog_directory_fsync")
        self._measure_method(storage, "_sha256", "rawlog_sha256")

        def measured_fsync(fd):
            bucket = profiler._fsync_bucket(fd)
            started = time.perf_counter_ns()
            try:
                return profiler._original_fsync(fd)
            finally:
                profiler._record(profiler.current_stage, "fsync_" + bucket,
                                 time.perf_counter_ns() - started)

        def measured_append_many(session, records):
            started = time.perf_counter_ns()
            try:
                return profiler._original_append_many(session, records)
            finally:
                profiler._record(profiler.current_stage, "rawlog_append_many",
                                 time.perf_counter_ns() - started)

        os.fsync = measured_fsync
        storage.RawLogV2Session.append_many = measured_append_many
        return self

    def __exit__(self, exc_type, exc, traceback):
        for owner, attribute, original in reversed(self._phase_patches):
            setattr(owner, attribute, original)
        self._phase_patches.clear()
        if self._original_fsync is not None:
            os.fsync = self._original_fsync
        if self._storage_module is not None and self._original_append_many is not None:
            self._storage_module.RawLogV2Session.append_many = self._original_append_many
        return False

    def phase_summary(self, stage):
        result = {}
        for key, value in self._phase_stats.get(stage, {}).items():
            result[key + "_count"] = value["count"]
            result[key + "_total_ms"] = value["total_ns"] / 1_000_000
            result[key + "_max_ms"] = value["max_ns"] / 1_000_000
        return result

    def snapshot(self, stage):
        return {
            key: dict(value)
            for key, value in self._stats.get(stage, {}).items()
        }

    @staticmethod
    def delta(before, after):
        result = {}
        keys = set(before) | set(after)
        for key in keys:
            left = before.get(key, {"count": 0, "total_ns": 0, "max_ns": 0})
            right = after.get(key, {"count": 0, "total_ns": 0, "max_ns": 0})
            result[key] = {
                "count": right["count"] - left["count"],
                "total_ns": right["total_ns"] - left["total_ns"],
                "max_ns": right["max_ns"],
            }
        return result

    def stage_summary(self, stage):
        stats = self._stats.get(stage, {})
        result = {}
        keys = ["rawlog_append_many"] + [
            "fsync_" + bucket for bucket in self.FSYNC_BUCKETS
        ]
        for key in keys:
            value = stats.get(key, {"count": 0, "total_ns": 0, "max_ns": 0})
            result[key + "_count"] = value["count"]
            result[key + "_total_ms"] = value["total_ns"] / 1_000_000
            result[key + "_max_ms"] = value["max_ns"] / 1_000_000
        return result

    def overall_summary(self):
        keys = set()
        for stats in self._stats.values():
            keys.update(stats)
        result = {}
        for key in sorted(keys):
            count = sum(self._stats[stage][key]["count"] for stage in self._stats)
            total = sum(self._stats[stage][key]["total_ns"] for stage in self._stats)
            maximum = max(self._stats[stage][key]["max_ns"] for stage in self._stats)
            result[key] = {
                "count": count, "total_ms": total / 1_000_000,
                "max_ms": maximum / 1_000_000,
            }
        return result


def run_profile(output_dir: os.PathLike | str) -> dict:
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    rawlog_root = output / "rawlog"
    rawlog_root.mkdir(parents=True, exist_ok=True)

    session_id = str(uuid.uuid4())
    log_id = "T18-" + session_id.split("-")[0]
    clock = DeterministicClock()
    codec = ProtocolV2Codec(PROTOCOL_V2_MAGIC, PROTOCOL_V2_VERSION)
    transport = InMemoryProtocolV2Transport(codec)
    stop_writer = InMemoryIndependentStopWriter()
    protocol = ProtocolV2HostSession.for_rawlog_session(
        transport, codec, rawlog_root, session_id, stop_writer=stop_writer,
        monotonic=clock.monotonic, utc_now=clock.utc_now,
    )
    writer = RawLogV2Writer(rawlog_root)
    controller = None

    def stop_abort():
        protocol.send_stop_best_effort(
            stop_reason=int(StopReason.INTERNAL_HOST_FAULT)
        )

    def stop_normal():
        protocol.send_stop_best_effort(
            stop_reason=int(StopReason.NORMAL_COMPLETION)
        )

    from .engine import SequenceController
    controller = SequenceController.with_protocol_session(
        writer, _manifest(rawlog_root, log_id, session_id, clock),
        protocol, stop_abort, clock=clock, send_normal_stop=stop_normal,
        stage_direction=lambda _index: int(DriveDirection.FWD),
    )
    stage_rows: list[dict] = []
    total_batches = 0
    total_slots = 0
    profile_start = time.perf_counter_ns()
    stage_zero_start = time.perf_counter_ns()
    profiler = PersistenceProfiler()
    controller.startup_recover()

    with profiler:
        controller.start()
        for stage_index in range(31):
            profiler.current_stage = stage_index
            stage_start = stage_zero_start if stage_index == 0 else time.perf_counter_ns()
            state = controller.poll()  # APPLY_ACK is decoded/correlated by production session.
            if state.value != "running":
                raise RuntimeError(
                    f"stage {stage_index} did not enter RUNNING after APPLY_ACK: {state.value}"
                )
            first_sequence = stage_index * SLOTS_PER_STAGE
            for batch_index in range(BATCHES_PER_STAGE):
                transport.queue_adc_batch(
                    session_id, stage_index + 1,
                    first_sequence + batch_index * SLOTS_PER_BATCH,
                )
                state = controller.poll()
                if state.value != "running":
                    raise RuntimeError(
                        f"stage {stage_index} stopped while processing ADC batch {batch_index}: {state.value}"
                    )
                total_batches += 1
                total_slots += SLOTS_PER_BATCH
            clock.advance_stage()
            state = controller.poll()  # Production stage DISARM, stage record and next ARM.
            elapsed_ns = time.perf_counter_ns() - stage_start
            stage_metrics = profiler.stage_summary(stage_index)
            phase_metrics = profiler.phase_summary(stage_index)
            stage_rows.append({
                "stage_index": stage_index,
                "pwm": stage_index,
                "adc_batches": BATCHES_PER_STAGE,
                "adc_slots": SLOTS_PER_STAGE,
                "elapsed_ns": elapsed_ns,
                "elapsed_ms": elapsed_ns / 1_000_000,
                "budget_ms": STAGE_BUDGET_NS / 1_000_000,
                "within_8s_budget": elapsed_ns <= STAGE_BUDGET_NS,
                **stage_metrics,
                **phase_metrics,
            })
            if stage_index < 30 and state.value != "waiting_ack":
                raise RuntimeError(
                    f"stage {stage_index} did not advance to next ACK gate: {state.value}"
                )
            if stage_index == 30 and state.value != "completed":
                raise RuntimeError(
                    f"31-stage sequence did not complete: {state.value}; "
                    f"controller_fault={controller._last_fault!r}"
                )

    total_elapsed_ns = time.perf_counter_ns() - profile_start
    package_dir = rawlog_root / log_id
    manifest_path = package_dir / "manifest.json"
    records_path = package_dir / "records.jsonl"
    evidence = TransportEvidenceJournal.for_session(rawlog_root, session_id)
    bundle = verify_evidence_bundle(package_dir, evidence, session_id)
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    records, parse_errors = parse_complete_jsonl(records_path.read_bytes())
    validation_errors = list(parse_errors) + validate_package(
        manifest_data, records, raise_on_error=False
    )
    adc_records = [r for r in records if r.get("record_type") == "ADC_SAMPLE"]
    stage_records = [r for r in records if r.get("record_type") == "PWM_STAGE"]
    events, evidence_chain_head = protocol.evidence._read()
    loss_summaries = [
        event for event in events if event.get("event") == "ADC_LOSS_WINDOW_SUMMARY"
    ]
    stop_messages = [
        codec.decode(frame).message for frame in stop_writer.frames
    ]
    if len(stop_messages) != 1 or stop_messages[0].get("kind") != "STOP_REQ":
        raise RuntimeError("normal completion did not emit exactly one independent STOP_REQ")
    if len(adc_records) != 37_200 or len(stage_records) != 31:
        raise RuntimeError(
            f"persisted counts mismatch: ADC_SAMPLE={len(adc_records)}, PWM_STAGE={len(stage_records)}"
        )
    if total_batches != 3_100 or total_slots != 37_200:
        raise RuntimeError("simulated production input count mismatch")
    if len(loss_summaries) != 310:
        raise RuntimeError(f"expected 310 one-second loss summaries, got {len(loss_summaries)}")
    bad_windows = [
        event for event in loss_summaries
        if event.get("payload", {}).get("summary", {}).get("status") != "PASS"
    ]
    if bad_windows:
        raise RuntimeError(f"{len(bad_windows)} ADC loss windows were not PASS")
    if validation_errors:
        raise RuntimeError("RawLog v2 package validation failed: " + "; ".join(validation_errors[:10]))

    stage_times = [row["elapsed_ns"] for row in stage_rows]
    csv_path = output / "t18-production-stage-profile.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        fieldnames = list(stage_rows[0])
        csv_writer = csv.DictWriter(stream, fieldnames=fieldnames)
        csv_writer.writeheader()
        csv_writer.writerows(stage_rows)

    profile_pass = all(row["within_8s_budget"] for row in stage_rows)
    report = {
        "format": "310-t18-production-path-profile-v1",
        "measurement_session_id": session_id,
        "log_id": log_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "PASS" if profile_pass else "FAIL",
        "stage_budget_ms": 8000,
        "persistence_diagnostics": {
            "method": "observational os.fsync and RawLogV2Session.append_many wrappers",
            "durability_operations_changed": False,
            "fsync_by_target": profiler.overall_summary(),
            "finalization_phase_by_stage": {
                str(stage): profiler.phase_summary(stage)
                for stage in range(31) if profiler.phase_summary(stage)
            },
            "scope_note": "Phase timings are observational wrappers around production methods; nested totals overlap and must not be summed. Durability operations are unchanged.",
        },
        "stage_count": len(stage_rows),
        "adc_batches": total_batches,
        "adc_slots": total_slots,
        "adc_sample_records": len(adc_records),
        "pwm_stage_records": len(stage_records),
        "evidence_event_count": len(events),
        "evidence_chain_head": evidence_chain_head,
        "loss_window_summary_count": len(loss_summaries),
        "loss_windows_all_pass": not bad_windows,
        "rawlog_validation_errors": validation_errors,
        "evidence_bundle_verified": bool(bundle),
        "normal_completion_stop_request_count": len(stop_messages),
        "total_profile_elapsed_ms": total_elapsed_ns / 1_000_000,
        "stage_elapsed_ms": {
            "p50": _percentile(stage_times, 50) / 1_000_000,
            "p95": _percentile(stage_times, 95) / 1_000_000,
            "p99": _percentile(stage_times, 99) / 1_000_000,
            "p99_9": _percentile(stage_times, 99.9) / 1_000_000,
            "max": max(stage_times) / 1_000_000,
        },
        "stages": stage_rows,
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "output_path": str(output),
            "storage_mount": _mount_for(output),
            "performance_clock": "time.perf_counter_ns",
            "deterministic_sequence_clock": "injected; advances 10s at each stage boundary",
            "transport": "in-memory protocol-v2 peer; no hardware device opened",
            "persistence": "real RawLog, command-intent and Evidence files with production fsync calls",
            "physical_hardware_used": False,
        },
        "artifact_hashes": {
            "rawlog_manifest_sha256": _sha256(manifest_path),
            "rawlog_records_sha256": _sha256(records_path),
            "evidence_sha256": _sha256(evidence.path),
            "evidence_bundle_manifest_sha256": _sha256(evidence.path.parent / "bundle-manifest.json"),
            "intent_journal_sha256": _sha256(protocol.intent_journal.path),
            "stage_csv_sha256": _sha256(csv_path),
        },
    }
    report_path = output / "t18-production-profile.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    (output / "t18-production-profile.json.sha256").write_text(
        _sha256(report_path) + "  t18-production-profile.json\n",
        encoding="ascii",
    )
    protocol.disconnect()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, help="directory on the filesystem to profile")
    args = parser.parse_args()
    report = run_profile(args.output_dir)
    print(json.dumps({
        "status": report["status"],
        "stage_elapsed_ms": report["stage_elapsed_ms"],
        "stage_count": report["stage_count"],
        "adc_batches": report["adc_batches"],
        "adc_slots": report["adc_slots"],
        "evidence_event_count": report["evidence_event_count"],
        "output_dir": str(Path(args.output_dir).resolve()),
    }, indent=2))
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
