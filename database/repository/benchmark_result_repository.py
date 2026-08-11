"""Repository for confirmed benchmark results."""

from .base_repository import BaseRepository


class BenchmarkResultRepository(BaseRepository):
    TABLE = "benchmark_result"

    def create_or_update(self, instance_id, session_id, benchmark_rpm, notes=None):
        rpm = float(benchmark_rpm)
        if rpm <= 0:
            raise ValueError("benchmark_rpm must be greater than zero")

        existing = self.get_by_session(session_id)
        data = {
            "instance_id": str(instance_id).strip(),
            "session_id": str(session_id).strip(),
            "benchmark_rpm": rpm,
            "source": "USER_CONFIRMED",
            "notes": notes,
        }
        if not data["instance_id"] or not data["session_id"]:
            raise ValueError("instance_id and session_id are required")

        if existing:
            return self.update(
                self.TABLE,
                {
                    "instance_id": data["instance_id"],
                    "benchmark_rpm": data["benchmark_rpm"],
                    "source": data["source"],
                    "notes": data["notes"],
                    "updated_at": "CURRENT_TIMESTAMP",
                },
                "session_id=?",
                (data["session_id"],),
            )

        result = self.insert(self.TABLE, data)
        return result

    def get_by_session(self, session_id):
        return self.fetch_one(
            "SELECT * FROM benchmark_result WHERE session_id=?",
            (session_id,),
        )

    def get_latest_by_instance(self, instance_id):
        return self.fetch_one(
            """
            SELECT *
            FROM benchmark_result
            WHERE instance_id=?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (instance_id,),
        )

    def get_history_by_instance(self, instance_id):
        return self.fetch_all(
            """
            SELECT *
            FROM benchmark_result
            WHERE instance_id=?
            ORDER BY created_at DESC
            """,
            (instance_id,),
        )
