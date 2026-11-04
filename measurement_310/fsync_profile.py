"""Measure host-local fsync latency for the 310-5 T18 profile.

Run only on the approved target host/storage. This tool never opens serial ports
or touches hardware. Requires >=10,000 samples and explicit STOP reserve/margin.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import sys
import tempfile
import time
from pathlib import Path


def nearest_rank(values, percentile):
    if not values:
        raise ValueError("values cannot be empty")
    if not 0 < percentile <= 1:
        raise ValueError("percentile must be in (0, 1]")
    ordered = sorted(values)
    return ordered[math.ceil(percentile * len(ordered)) - 1]


def mount_for(path):
    target = str(Path(path).resolve())
    best = None
    try:
        lines = Path("/proc/self/mounts").read_text().splitlines()
    except OSError:
        return None
    for line in lines:
        fields = line.split()
        if len(fields) < 4:
            continue
        mountpoint = fields[1].replace("\\040", " ")
        if target == mountpoint or target.startswith(mountpoint.rstrip("/") + "/"):
            if best is None or len(mountpoint) > len(best["mountpoint"]):
                best = {
                    "source": fields[0],
                    "mountpoint": mountpoint,
                    "filesystem": fields[2],
                    "options": fields[3],
                }
    return best


def percentile_summary(values):
    return {
        "count": len(values),
        "p50_ns": nearest_rank(values, 0.50),
        "p95_ns": nearest_rank(values, 0.95),
        "p99_ns": nearest_rank(values, 0.99),
        "p999_ns": nearest_rank(values, 0.999),
        "max_ns": max(values),
    }


def run_profile(output_dir, samples, stage_ms, stop_reserve_ms, margin_ms):
    if samples < 10000:
        raise ValueError("T18 requires at least 10,000 samples")
    if stage_ms <= 0 or stop_reserve_ms < 0 or margin_ms < 0:
        raise ValueError("invalid timing budget")
    if stop_reserve_ms >= stage_ms:
        raise ValueError("STOP reserve must be less than stage duration")

    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    file_latencies, dir_latencies = [], []
    file_failures, dir_failures = [], []
    with tempfile.TemporaryDirectory(prefix=".310-fsync-profile-", dir=output_dir) as temp:
        root = Path(temp)
        file_path = root / "file-fsync.bin"
        fd = os.open(str(file_path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            for index in range(samples):
                payload = index.to_bytes(8, "big")
                written = os.write(fd, payload)
                if written != len(payload):
                    raise OSError("short write during fsync profile")
                started = time.perf_counter_ns()
                try:
                    os.fsync(fd)
                except OSError as exc:
                    file_failures.append({"sample": index, "error": str(exc)})
                file_latencies.append(time.perf_counter_ns() - started)
        finally:
            os.close(fd)

        dir_fd = os.open(str(root), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            for index in range(samples):
                entry = root / f"entry-{index:05d}"
                entry_fd = os.open(str(entry), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                os.close(entry_fd)
                started = time.perf_counter_ns()
                try:
                    os.fsync(dir_fd)
                except OSError as exc:
                    dir_failures.append({"sample": index, "phase": "create", "error": str(exc)})
                dir_latencies.append(time.perf_counter_ns() - started)
                entry.unlink()
                try:
                    os.fsync(dir_fd)  # cleanup durability; not included in measured create latency
                except OSError as exc:
                    dir_failures.append({"sample": index, "phase": "cleanup", "error": str(exc)})
        finally:
            os.close(dir_fd)

    combined = [a + b for a, b in zip(file_latencies, dir_latencies)]
    budget_ns = (stage_ms - stop_reserve_ms) * 1_000_000
    margin_ns = margin_ms * 1_000_000
    p999_total_ns = nearest_rank(combined, 0.999) + margin_ns
    max_total_ns = max(combined) + margin_ns
    result = {
        "profile": "310-5-T18-fsync-v1",
        "host": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": sys.version,
            "target_path": str(output_dir),
            "st_dev": output_dir.stat().st_dev,
            "mount": mount_for(output_dir),
        },
        "parameters": {
            "samples": samples,
            "stage_ms": stage_ms,
            "stop_reserve_ms": stop_reserve_ms,
            "margin_ms": margin_ms,
        },
        "file_fsync": {**percentile_summary(file_latencies), "failure_count": len(file_failures)},
        "directory_fsync": {**percentile_summary(dir_latencies), "failure_count": len(dir_failures)},
        "fsync_failures": {"file": file_failures, "directory": dir_failures},
        "paired_file_plus_directory_fsync": percentile_summary(combined),
        "budget": {
            "available_ns": budget_ns,
            "p999_plus_margin_ns": p999_total_ns,
            "max_plus_margin_ns": max_total_ns,
            "p999_within_budget": p999_total_ns < budget_ns,
            "max_within_budget": max_total_ns < budget_ns,
            "profile_within_budget": (
                not file_failures and not dir_failures
                and p999_total_ns < budget_ns and max_total_ns < budget_ns
            ),
        },
        "limitations": [
            "Host filesystem synthetic benchmark only; not a power-loss certification.",
            "The paired sum is a profile estimate, not a guarantee for a different journal workload.",
            "No serial, firmware, MCU, driver, motor, or physical STOP behavior is tested.",
        ],
    }

    sample_path = output_dir / "310-fsync-samples.csv"
    with sample_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(("sample", "file_fsync_ns", "directory_fsync_ns", "paired_sum_ns"))
        writer.writerows(
            (i, file_latencies[i], dir_latencies[i], combined[i])
            for i in range(samples)
        )
        stream.flush()
        os.fsync(stream.fileno())
    sample_sha = hashlib.sha256(sample_path.read_bytes()).hexdigest()
    result["samples_file"] = sample_path.name
    result["samples_sha256"] = sample_sha

    report_path = output_dir / "310-fsync-report.json"
    report_bytes = (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
    with report_path.open("wb") as stream:
        stream.write(report_bytes)
        stream.flush()
        os.fsync(stream.fileno())
    report_sha = hashlib.sha256(report_bytes).hexdigest()
    checksum_path = output_dir / "310-fsync-report.sha256"
    with checksum_path.open("w", encoding="ascii", newline="") as stream:
        stream.write(f"{report_sha}  {report_path.name}\n")
        stream.flush()
        os.fsync(stream.fileno())
    dir_fd = os.open(str(output_dir), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True,
                        help="directory on the approved target storage")
    parser.add_argument("--samples", type=int, default=10000)
    parser.add_argument("--stage-ms", type=int, default=10000)
    parser.add_argument("--stop-reserve-ms", type=int, required=True)
    parser.add_argument("--margin-ms", type=int, required=True)
    args = parser.parse_args(argv)
    result = run_profile(
        args.output_dir, args.samples, args.stage_ms,
        args.stop_reserve_ms, args.margin_ms,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["budget"]["profile_within_budget"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
