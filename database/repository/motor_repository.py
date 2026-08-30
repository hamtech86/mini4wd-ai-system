# ============================================================
# motor_repository.py
# Motor Database System
# Motor Model Repository
# ============================================================

from .base_repository import BaseRepository


class MotorRepository(BaseRepository):
    TABLE = "motor_model"

    # Canonical 15-model master data supplied by the project specification.
    # nominal_voltage is fixed at 2.4 V because the current motor_model schema
    # requires it and the supplied master list omits this field.
    # data_confidence is stored numerically for the current schema:
    # HIGH=1.0, MEDIUM=0.75.
    MASTER_MODELS = (
        ("マッハダッシュPro", "MD_PRO", "PRO", "両軸", "DASH", 25500, 1650, 180, 1.40, "LOW", "HIGH", 1.0, "高回転ピーキー最上位"),
        ("ハイパーダッシュPro", "HD_PRO", "PRO", "両軸", "DASH", 24000, 1600, 190, 1.30, "LOW", "HIGH", 1.0, "バランス高回転型"),
        ("ライトダッシュPro", "LD_PRO", "PRO", "両軸", "TUNED", 18500, 1200, 165, 1.15, "HIGH", "MEDIUM", 1.0, "安定高速型"),
        ("トルクチューン2Pro", "TT2_PRO", "PRO", "両軸", "TUNED", 15000, 1400, 220, 1.00, "HIGH", "LOW", 1.0, "トルク特化型"),
        ("アトミックチューン2Pro", "AT2_PRO", "PRO", "両軸", "TUNED", 16000, 1350, 200, 1.05, "HIGH", "MEDIUM", 1.0, "万能型"),
        ("レブチューン2Pro", "RT2_PRO", "PRO", "両軸", "TUNED", 20000, 1450, 170, 1.20, "MEDIUM", "MEDIUM", 1.0, "高回転安定型"),
        ("ノーマル両軸", "NOR_DBL", "STD", "両軸", "NORMAL", 11000, 900, 140, 1.00, "HIGH", "LOW", 1.0, "基準モーター両軸"),
        ("スプリントダッシュ", "SPT", "STD", "片軸", "DASH", 26500, 1700, 175, 1.35, "LOW", "HIGH", 1.0, "ピーキー高速型"),
        ("パワーダッシュ", "PD", "STD", "片軸", "DASH", 23000, 1750, 230, 1.10, "LOW", "HIGH", 1.0, "トルク特化型"),
        ("ハイパーダッシュ3", "HD3", "STD", "片軸", "DASH", 23500, 1650, 200, 1.20, "LOW", "HIGH", 0.75, "高負荷安定型"),
        ("ライトダッシュ", "LD", "STD", "片軸", "TUNED", 17500, 1150, 160, 1.05, "HIGH", "MEDIUM", 0.75, "安定型"),
        ("トルクチューン2", "TT2", "STD", "片軸", "TUNED", 14500, 1350, 210, 0.95, "HIGH", "LOW", 1.0, "定番トルク型"),
        ("アトミックチューン2", "AT2", "STD", "片軸", "TUNED", 15500, 1300, 195, 1.00, "HIGH", "MEDIUM", 1.0, "万能型"),
        ("レブチューン2", "RT2", "STD", "片軸", "TUNED", 19000, 1400, 165, 1.15, "MEDIUM", "MEDIUM", 1.0, "高回転型"),
        ("ノーマル片軸", "NOR_STD", "STD", "片軸", "NORMAL", 10500, 850, 135, 1.00, "HIGH", "LOW", 1.0, "基準モーター片軸"),
    )

    def _ensure_master_models(self):
        """Synchronize the canonical 15-model master into the current DB.

        The existing schema uses the numeric motor_model_id as the FK and
        the ``series`` column as the human-facing model code. Existing
        canonical rows are updated in place so Motor Instances keep their
        numeric FK; missing canonical rows are inserted. Legacy PD2 naming
        is normalized to the canonical PD code.
        """
        rows = self.fetch_all("SELECT motor_model_id, name, series, is_deleted FROM motor_model")
        by_code = {str(row.get("series")): row for row in rows if row.get("series") is not None}

        for (name, code, product_series, shaft_type, category, rpm, current_ma,
             torque_gcm, efficiency, stability, heat, confidence, notes) in self.MASTER_MODELS:
            values = {
                "name": name,
                "series": code,
                "shaft_type": shaft_type,
                "motor_category": category,
                "nominal_voltage": 2.4,
                "nominal_rpm": rpm,
                "nominal_current_ma": current_ma,
                "nominal_torque_gcm": torque_gcm,
                "efficiency_index": efficiency,
                "stability_tendency": stability,
                "heat_tendency": heat,
                "data_confidence": confidence,
                "notes": notes,
                "is_deleted": 0,
            }
            existing = by_code.get(code)
            if existing is not None:
                self.update(self.TABLE, values, "motor_model_id=?", (existing["motor_model_id"],))
                continue

            # Normalize the old Power Dash 2 seed row to PD when possible,
            # preserving its numeric PK and any Motor Instance FK.
            legacy = self.fetch_one(
                "SELECT motor_model_id FROM motor_model WHERE series='PD2' LIMIT 1"
            ) if code == "PD" else None
            if legacy is not None:
                self.update(self.TABLE, values, "motor_model_id=?", (legacy["motor_model_id"],))
                continue

            self.insert(self.TABLE, values)

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
