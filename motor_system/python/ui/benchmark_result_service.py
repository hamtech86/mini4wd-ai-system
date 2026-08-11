"""Application boundary for confirmed benchmark RPM results."""

from database.repository.benchmark_result_repository import BenchmarkResultRepository
from motor_system.python.ui.benchmark_result_model import BenchmarkResult


def save_benchmark_result(database, instance_id, session_id, benchmark_rpm, notes=None):
    """Persist a confirmed benchmark result without modifying raw measurements."""
    result = BenchmarkResult(
        instance_id=instance_id,
        session_id=session_id,
        benchmark_rpm=benchmark_rpm,
    ).normalized()

    repository = BenchmarkResultRepository(database)
    repository.create_or_update(
        result.instance_id,
        result.session_id,
        result.benchmark_rpm,
        notes=notes,
    )
    return result.as_dict()
