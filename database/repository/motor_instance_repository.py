# ============================================================
# motor_instance_repository.py
# Motor Instance Repository
# ============================================================

from .base_repository import BaseRepository


class MotorInstanceRepository(BaseRepository):
    TABLE = "motor_instance"

    def create(self, instance_data):
        return self.insert(self.TABLE, instance_data)

    def get_by_id(self, instance_id):
        return self.fetch_one(
            "SELECT * FROM motor_instance WHERE instance_id=? AND COALESCE(is_deleted,0)=0",
            (instance_id,),
        )

    def get_by_model(self, motor_model_id):
        return self.fetch_all(
            "SELECT * FROM motor_instance WHERE motor_model_id=? AND COALESCE(is_deleted,0)=0 ORDER BY created_at DESC",
            (motor_model_id,),
        )

    def get_all_active(self):
        return self.fetch_all(
            "SELECT * FROM motor_instance WHERE COALESCE(is_deleted,0)=0 ORDER BY instance_id DESC"
        )

    def get_list_view(self):
        return self.fetch_all(
            """
            SELECT mi.*, mm.name AS motor_name, mm.series AS model_code
            FROM motor_instance mi
            LEFT JOIN motor_model mm ON mm.motor_model_id=mi.motor_model_id
            WHERE COALESCE(mi.is_deleted,0)=0
              AND (COALESCE(mm.is_deleted,0)=0 OR mm.motor_model_id IS NULL)
            ORDER BY mi.instance_id DESC
            """
        )

    def update_instance(self, instance_id, data):
        return self.update(self.TABLE, data, "instance_id=?", (instance_id,))

    def update_cache(self, instance_id, cache_data):
        allowed = {"latest_session_id","latest_work_id","first_log_id","peak_log_id",
                   "latest_log_id","backup_log1","backup_log2","backup_log3"}
        data = {k:v for k,v in cache_data.items() if k in allowed}
        return self.update(self.TABLE, data, "instance_id=?", (instance_id,)) if data else 0

    def increment_anomaly(self, instance_id, consecutive=True):
        if consecutive:
            query = ("UPDATE motor_instance SET anomaly_count=anomaly_count+1,"
                     " consecutive_anomaly_count=consecutive_anomaly_count+1,"
                     " updated_at=CURRENT_TIMESTAMP WHERE instance_id=?")
        else:
            query = ("UPDATE motor_instance SET anomaly_count=anomaly_count+1,"
                     " updated_at=CURRENT_TIMESTAMP WHERE instance_id=?")
        cursor = self.execute(query, (instance_id,))
        self.database.commit()
        return cursor.rowcount

    def reset_consecutive_anomaly(self, instance_id):
        return self.update(self.TABLE, {"consecutive_anomaly_count": 0},
                           "instance_id=?", (instance_id,))

    def get_sessions(self, instance_id):
        return self.fetch_all(
            """
            SELECT session_id, device_type, device_model, start_datetime, end_datetime,
                   result, created_at, updated_at
            FROM measurement_session
            WHERE instance_id=?
            ORDER BY COALESCE(end_datetime,start_datetime,created_at) DESC, session_id DESC
            """, (instance_id,)
        )

    def get_session_measurement_count(self, session_id):
        row = self.fetch_one(
            "SELECT COUNT(*) AS n FROM measurement WHERE session_id=?",
            (str(session_id),),
        )
        return int(row["n"]) if row else 0

    def delete(self, instance_id):
        # Retained only for compatibility. Manager visibility never calls it.
        return self.soft_delete(self.TABLE, "instance_id", instance_id)
