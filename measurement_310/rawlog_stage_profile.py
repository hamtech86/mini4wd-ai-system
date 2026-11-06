"""Measure RawLog v2 append and evidence-journal costs with synthetic records.

Software-only microbenchmark: uses real RawLogV2Session.append and
TransportEvidenceJournal.append implementations. It does not qualify ADC
cadence, Protocol v2 acceptance, SequenceController stages, or T18 end-to-end.
"""
from __future__ import annotations

import base64
import csv
import hashlib
import json
import math
import os
import platform
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from measurement_310.protocol_v1_session import TransportEvidenceJournal
from raw_log_v2 import RawLogV2Writer
from raw_log_v2.validator import CHANNELS


MIN_SAMPLES = 10_000
BATCH_SAMPLES = 12
CHANNEL_CODE_ORDER = (0, 1, 4, 5, 2, 3) * 2


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def percentile(values: list[int], fraction: float) -> int:
    if not values:
        raise ValueError("percentile requires at least one value")
    ordered = sorted(values)
    return ordered[math.ceil(fraction * len(ordered)) - 1]


def summarize(values: list[int]) -> dict:
    if not values:
        return {"count": 0}
    return {
        "count": len(values),
        "mean_ns": round(sum(values) / len(values)),
        "p50_ns": percentile(values, 0.50),
        "p95_ns": percentile(values, 0.95),
        "p99_ns": percentile(values, 0.99),
        "p999_ns": percentile(values, 0.999),
        "max_ns": max(values),
    }


def fsync_file(path: Path, payload: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def write_csv(path: Path, header: tuple[str, ...], rows) -> None:
    with path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(rows)
        stream.flush()
        os.fsync(stream.fileno())


def run_profile(output_dir: str | os.PathLike, samples: int = 10_008) -> dict:
    if isinstance(samples, bool) or not isinstance(samples, int) or samples < MIN_SAMPLES:
        raise ValueError("RawLog append microbenchmark requires at least 10,000 sample commits")
    if samples % BATCH_SAMPLES:
        raise ValueError(f"samples must be a multiple of {BATCH_SAMPLES} to preserve whole ADC_BATCH groups")

    requested = Path(output_dir)
    if requested.is_symlink() or not requested.is_dir():
        raise ValueError("output directory must pre-exist and must not be a symlink")
    root = requested.resolve()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    log_id = "T18-RAWLOG-" + run_id
    session_id = str(uuid.uuid4())
    device_epoch_id = "0000000000000001"
    channel_names = list(CHANNELS)
    sample_latencies: list[int] = []
    evidence_latencies: list[int] = []
    batch_latencies: list[int] = []
    sample_rows = []
    batch_rows = []
    sample_sequence = 0
    record_sequence = 0
    batch_count = samples // BATCH_SAMPLES
    stage_index = -1
    stage_context_id = ""

    print(
        f"T18 RawLog append microbenchmark: {samples} ADC_SAMPLE commits, "
        f"{batch_count} synthetic 12-slot groups",
        flush=True,
    )

    with tempfile.TemporaryDirectory(prefix=".310-rawlog-stage-profile-", dir=root) as temp:
        rawlog_root = Path(temp) / "rawlog"
        writer = RawLogV2Writer(rawlog_root)
        session = writer.begin({
            "log_id": log_id,
            "measurement_session_id": session_id,
            "started_at_utc": utc_now(),
        })
        evidence = TransportEvidenceJournal.for_session(rawlog_root, session_id)

        for batch_index in range(batch_count):
            next_stage = 0
            if next_stage != stage_index:
                stage_index = next_stage
                stage_context_id = f"t18-context-{stage_index:03d}"
                started = time.perf_counter_ns()
                evidence.append(
                    "STAGE_CONTEXT_MAP",
                    {"stage_index": stage_index, "stage_context_id": stage_context_id},
                    measurement_session_id=session_id,
                    device_epoch_id=device_epoch_id,
                    direction="host_internal",
                )
                evidence_latencies.append(time.perf_counter_ns() - started)

            batch_started = time.perf_counter_ns()
            first_sequence = sample_sequence
            wire_samples = []
            rawlog_records = []

            for slot in range(BATCH_SAMPLES):
                channel_code = CHANNEL_CODE_ORDER[slot]
                channel = channel_names[channel_code]
                sensor, role = CHANNELS[channel]
                sample_sequence += 1
                device_elapsed_us = sample_sequence * 25_000
                timestamp_us = device_elapsed_us & 0xFFFFFFFF
                wire_samples.append({
                    "channel_code": channel_code,
                    "adc_raw": 512,
                    "timestamp_us_u32": timestamp_us,
                    "device_elapsed_us": device_elapsed_us,
                    "sample_sequence64": sample_sequence,
                    "acquisition_status": 0,
                    "stage_context_token": stage_index + 1,
                })
                rawlog_records.append({
                    "schema_version": "2.0.0",
                    "record_type": "ADC_SAMPLE",
                    "record_id": f"t18-record-{sample_sequence:08d}",
                    "record_seq": record_sequence + slot + 1,
                    "log_id": log_id,
                    "measurement_session_id": session_id,
                    "recorded_at_utc": utc_now(),
                    "sample_id": f"t18-sample-{sample_sequence:08d}",
                    "channel": channel,
                    "sensor": sensor,
                    "signal_role": role,
                    "adc_raw": 512,
                    "adc_resolution_bits": 10,
                    "raw_unit": "count",
                    "device_timestamp_us_u32": timestamp_us,
                    "device_timestamp_point": "conversion_midpoint",
                    "device_epoch_id": device_epoch_id,
                    "device_elapsed_us": device_elapsed_us,
                    "device_sample_sequence": sample_sequence,
                    "host_received_at_utc": utc_now(),
                    "host_received_monotonic_ns": time.monotonic_ns(),
                    "stage_context_id": stage_context_id,
                    "stage_id": f"PWM-{stage_index:02d}",
                    "stage_assignment": "confirmed",
                    "calibration_id": None,
                    "validity": "valid",
                    "invalid_reason": None,
                })

            message = {
                "kind": "ADC_BATCH",
                "measurement_session_id": session_id,
                "device_epoch_tag": 1,
                "samples": wire_samples,
            }
            raw_frame = json.dumps(message, separators=(",", ":"), sort_keys=True).encode("utf-8")
            raw_b64 = base64.b64encode(raw_frame).decode("ascii")

            for event, payload in (
                ("RX_BYTES", {"raw_b64": raw_b64, "byte_count": len(raw_frame)}),
                ("FRAME_RX_DECODED", {"message": message}),
                ("ADC_BATCH_ACCEPTED", {
                    "first_sample_sequence64": first_sequence + 1,
                    "next_sample_sequence64": sample_sequence + 1,
                    "sample_count": BATCH_SAMPLES,
                    "device_elapsed_us": wire_samples[-1]["device_elapsed_us"],
                    "raw_frame_base64": raw_b64,
                }),
            ):
                started = time.perf_counter_ns()
                evidence.append(
                    event, payload,
                    measurement_session_id=session_id,
                    device_epoch_id=device_epoch_id,
                    direction="device_to_host",
                )
                evidence_latencies.append(time.perf_counter_ns() - started)

            for slot, record in enumerate(rawlog_records):
                started = time.perf_counter_ns()
                session.append(record)
                elapsed = time.perf_counter_ns() - started
                sample_latencies.append(elapsed)
                sample_rows.append((
                    record["record_seq"], stage_index, batch_index,
                    record["channel"], elapsed,
                ))
            record_sequence += BATCH_SAMPLES

            if (batch_index + 1) % 10 == 0:
                started = time.perf_counter_ns()
                evidence.append(
                    "ADC_LOSS_WINDOW_SUMMARY",
                    {"window_index": (batch_index + 1) // 10 - 1,
                     "expected_per_channel": 20, "channel_count": 6},
                    measurement_session_id=session_id,
                    device_epoch_id=device_epoch_id,
                    direction="host_internal",
                )
                evidence_latencies.append(time.perf_counter_ns() - started)

            batch_elapsed = time.perf_counter_ns() - batch_started
            batch_latencies.append(batch_elapsed)
            batch_rows.append((batch_index + 1, stage_index, first_sequence + 1,
                               sample_sequence, batch_elapsed))

            if (batch_index + 1) % 10 == 0:
                print(
                    f"progress: {sample_sequence}/{samples} samples; "
                    f"batch {batch_index + 1}/{batch_count}; "
                    f"last batch {batch_elapsed / 1_000_000:.1f} ms",
                    flush=True,
                )



    report = {
        "profile": "310-5-T18-rawlog-append-microbenchmark-v2",
        "run_id": run_id,
        "host": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": sys.version,
            "target_path": str(root),
            "st_dev": root.stat().st_dev,
        },
        "parameters": {
            "rawlog_sample_commits": samples,
            "batch_samples": BATCH_SAMPLES,
            "channel_code_order": list(CHANNEL_CODE_ORDER),
            "timestamp_model": "synthetic monotonic sequence counter; not a device-time or cadence claim",
        },
        "workload": {
            "rawlog_append_count": len(sample_latencies),
            "evidence_append_count": len(evidence_latencies),
            "adc_batch_count": len(batch_latencies),
            "full_10s_stage_groups": None,
            "partial_final_stage_samples": None,
        },
        "latency": {
            "rawlog_append": summarize(sample_latencies),
            "evidence_append": summarize(evidence_latencies),
            "adc_batch_total": summarize(batch_latencies),
            "full_stage_group_ns": None,
            "full_stage_group_max_ns": None,
        },
        "budget": {
            "rawlog_append_profile_completed": len(sample_latencies) == samples,
            "stage_budget_assessed": False,
            "t18_end_to_end_pass": False,
        },
        "limitations": [
            "Uses the production RawLogV2Session.append and TransportEvidenceJournal.append code paths with synthetic ADC_BATCH contents.",
            "Does not open serial ports, firmware, MCU, driver, motor, or hardware.",
            "Does not execute the 310-second sequence or measure physical ADC arrival timing.",
            "Does not include final package publication, crash recovery, or backup/restore timing.",
            "Synthetic batch groups use protocol-v2 channel code order only; no device cadence is asserted.",
            "No stage-budget or T18 end-to-end pass is produced by this microbenchmark.",
        ],
    }

    sample_csv = root / f"310-rawlog-samples-{run_id}.csv"
    batch_csv = root / f"310-rawlog-batches-{run_id}.csv"
    report_json = root / f"310-rawlog-report-{run_id}.json"
    report_sha = root / f"310-rawlog-report-{run_id}.sha256"

    write_csv(sample_csv, ("record_seq", "stage_index", "batch_index", "channel", "append_ns"), sample_rows)
    write_csv(batch_csv, ("batch_index", "stage_index", "first_sequence64", "next_sequence64", "batch_total_ns"), batch_rows)

    encoded = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
    fsync_file(report_json, encoded)
    digest = hashlib.sha256(encoded).hexdigest()
    fsync_file(report_sha, f"{digest}  {report_json.name}\n".encode("ascii"))
    dir_fd = os.open(str(root), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)

    print(json.dumps(report, indent=2, sort_keys=True), flush=True)
    print(f"ARTIFACTS: {sample_csv.name}, {batch_csv.name}, {report_json.name}, {report_sha.name}", flush=True)
    return report


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--samples", type=int, default=10_008)
    args = parser.parse_args(argv)
    report = run_profile(args.output_dir, args.samples)
    return 0 if report["budget"]["rawlog_append_profile_completed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
