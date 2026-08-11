"""Benchmark result contract used by Motor Instance Manager.

This module deliberately does not control Main.py or hardware.  It provides a
small validation/normalization boundary for benchmark results supplied by the
break-in application.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class BenchmarkResult:
    instance_id: str
    session_id: str
    benchmark_rpm: Optional[float] = None

    def normalized(self) -> "BenchmarkResult":
        instance_id = str(self.instance_id).strip()
        session_id = str(self.session_id).strip()
        if not instance_id:
            raise ValueError("instance_id is required")
        if not session_id:
            raise ValueError("session_id is required")

        rpm = self.benchmark_rpm
        if rpm is not None:
            try:
                rpm = float(rpm)
            except (TypeError, ValueError) as exc:
                raise ValueError("benchmark_rpm must be numeric") from exc
            if rpm <= 0:
                raise ValueError("benchmark_rpm must be greater than zero")

        return BenchmarkResult(instance_id, session_id, rpm)

    def as_dict(self):
        result = self.normalized()
        return {
            "instance_id": result.instance_id,
            "session_id": result.session_id,
            "benchmark_rpm": result.benchmark_rpm,
        }
