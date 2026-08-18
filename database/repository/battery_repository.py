"""Repositories for Battery Model / Instance / Benchmark Result.

Battery 5A Standalone measurement collection remains outside this module.
This repository only persists master/instance metadata and derived results.
"""

from .base_repository import BaseRepository


class BatteryModelRepository(BaseRepository):
    TABLE = "battery_model"

    MASTER_MODELS = (
        ("NEO_STD", "Tamiya Neo Champ", "NiMH"),
        ("NEO_GROWN", "Tamiya Neo Champ (grown)", "NiMH"),
        ("POWER_GOLD", "POWER GOLD", "NiMH"),
    )

    def ensure_schema(self):
        self.execute(
            """CREATE TABLE IF NOT EXISTS battery_model (
                battery_model_id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                chemistry TEXT,
                nominal_voltage REAL,
                capacity_nominal_mah REAL,
                manufacturer TEXT,
                data_confidence REAL,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                is_deleted INTEGER NOT NULL DEFAULT 0
            )"""
        )
        self.database.commit()
        for code, name, chemistry in self.MASTER_MODELS:
            if not self.fetch_one(
                "SELECT 1 FROM battery_model WHERE model_code=?", (code,)
            ):
                self.insert(
                    self.TABLE,
                    {
                        "model_code": code,
                        "name": name,
                        "chemistry": chemistry,
                        "nominal_voltage": 1.2,
                        "data_confidence": 0.5,
                        "notes": "Reference model; measured data takes precedence.",
                    },
                )

    def create(self, data):
        return self.insert(self.TABLE, data)

    def get_by_id(self, battery_model_id):
        return self.fetch_one(
            "SELECT * FROM battery_model WHERE battery_model_id=? AND is_deleted=0",
            (battery_model_id,),
        )

    def get_by_code(self, model_code):
        return self.fetch_one(
            "SELECT * FROM battery_model WHERE model_code=? AND is_deleted=0",
            (model_code,),
        )

    def get_all(self):
        self.ensure_schema()
        return self.fetch_all(
            "SELECT * FROM battery_model WHERE is_deleted=0 ORDER BY battery_model_id"
        )


class BatteryInstanceRepository(BaseRepository):
    TABLE = "battery_instance"

    def ensure_schema(self):
        self.execute(
            """CREATE TABLE IF NOT EXISTS battery_instance (
                instance_id TEXT PRIMARY KEY,
                battery_model_id INTEGER NOT NULL,
                serial_number TEXT,
                nickname TEXT,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                is_deleted INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (battery_model_id) REFERENCES battery_model(battery_model_id)
            )"""
        )
        self.database.commit()

    def create(self, data):
        return self.insert(self.TABLE, data)

    def get_by_id(self, instance_id):
        return self.fetch_one(
            "SELECT * FROM battery_instance WHERE instance_id=? AND is_deleted=0",
            (instance_id,),
        )

    def get_all(self):
        return self.fetch_all(
            "SELECT * FROM battery_instance WHERE is_deleted=0 ORDER BY created_at"
        )


class BatteryBenchmarkResultRepository(BaseRepository):
    TABLE = "battery_benchmark_result"

    def ensure_schema(self):
        self.execute(
            """CREATE TABLE IF NOT EXISTS battery_benchmark_result (
                result_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                instance_id TEXT,
                analysis_version TEXT NOT NULL,
                measurement_count INTEGER NOT NULL DEFAULT 0,
                avg_voltage REAL, avg_current REAL, avg_power REAL,
                max_current REAL, max_power REAL, discharge_time_s REAL,
                voltage_drop REAL, capacity_ah REAL, capacity_mah REAL,
                energy_wh REAL, voltage_stddev REAL, current_stddev REAL,
                power_stddev REAL, voltage_hold_score REAL,
                stability_score REAL, capacity_score REAL, power_score REAL,
                overall_score REAL, internal_resistance_mohm REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(session_id, analysis_version),
                FOREIGN KEY (session_id) REFERENCES measurement_session(session_id),
                FOREIGN KEY (instance_id) REFERENCES battery_instance(instance_id)
            )"""
        )
        self.database.commit()

    def save(self, result):
        """Persist derived analysis without touching measurement rows."""
        columns = ",".join(result.keys())
        placeholders = ",".join("?" for _ in result)
        query = f"INSERT OR REPLACE INTO {self.TABLE} ({columns}) VALUES ({placeholders})"
        cursor = self.execute(query, tuple(result.values()))
        self.database.commit()
        return cursor.lastrowid

    def get_for_session(self, session_id, analysis_version=None):
        if analysis_version is None:
            return self.fetch_all(
                "SELECT * FROM battery_benchmark_result WHERE session_id=? ORDER BY result_id",
                (session_id,),
            )
        return self.fetch_one(
            "SELECT * FROM battery_benchmark_result WHERE session_id=? AND analysis_version=?",
            (session_id, analysis_version),
        )
