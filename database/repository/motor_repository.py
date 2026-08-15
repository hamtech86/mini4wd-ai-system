# ============================================================
# motor_repository.py
# Motor Database System
# Motor Model Repository
# ============================================================

from .base_repository import BaseRepository


class MotorRepository(BaseRepository):
    TABLE = "motor_model"

    # Canonical master list. This is database bootstrap/migration data,
    # not UI data. The UI always obtains models through this repository.
    MASTER_MODELS = (
        ("Mach Dash Pro", "MD_PRO", "SPEED"),
        ("Hyper Dash Pro", "HD_PRO", "SPEED"),
        ("Light Dash Pro", "LD_PRO", "SPEED"),
        ("Torque Tune 2 Pro", "TT2_PRO", "TORQUE"),
        ("Atomic Tune 2 Pro", "AT2_PRO", "BALANCE"),
        ("Rev Tune 2 Pro", "RT2_PRO", "HIGH_RPM"),
        ("Normal Double Shaft", "NOR_DBL", "NORMAL"),
        ("Sprint Dash", "SPT", "SPEED"),
        ("Power Dash", "PD", "POWER"),
        ("Hyper Dash 3", "HD3", "SPEED"),
        ("Light Dash", "LD", "SPEED"),
        ("Torque Tune 2", "TT2", "TORQUE"),
        ("Atomic Tune 2", "AT2", "BALANCE"),
        ("Rev Tune 2", "RT2", "HIGH_RPM"),
        ("Normal Single Shaft", "NOR_STD", "NORMAL"),
    )

    def _ensure_master_models(self):
        """Ensure the canonical 15-model master exists in the DB.

        Existing rows are never replaced. The model code is stored in
        ``series`` for the current schema; the UI treats it as model_code.
        """
        rows = self.fetch_all("SELECT motor_model_id, name, series FROM motor_model WHERE is_deleted=0")
        existing = {str(row.get("series")) for row in rows if row.get("series")}
        for name, code, category in self.MASTER_MODELS:
            if code in existing:
                continue
            self.insert(
                self.TABLE,
                {
                    "name": name,
                    "series": code,
                    "shaft_type": "FA130",
                    "motor_category": category,
                    "nominal_voltage": 2.4,
                    "data_confidence": 0.5,
                    "notes": "Canonical Motor Model master entry. Replace reference values with measured data.",
                },
            )

    def create(self, motor_data):
        return self.insert(self.TABLE, motor_data)

    def get_by_id(self, motor_model_id):
        return self.fetch_one(
            "SELECT * FROM motor_model WHERE motor_model_id=? AND is_deleted=0",
            (motor_model_id,),
        )

    def get_by_name(self, name):
        return self.fetch_one(
            "SELECT * FROM motor_model WHERE name=? AND is_deleted=0",
            (name,),
        )

    def get_all(self):
        self._ensure_master_models()
        return self.fetch_all(
            "SELECT * FROM motor_model WHERE is_deleted=0 ORDER BY motor_model_id"
        )

    def update_motor(self, motor_model_id, data):
        return self.update(self.TABLE, data, "motor_model_id=?", (motor_model_id,))

    def delete(self, motor_model_id):
        return self.soft_delete(self.TABLE, "motor_model_id", motor_model_id)


# ============================================================
# END OF motor_repository.py
# ============================================================
