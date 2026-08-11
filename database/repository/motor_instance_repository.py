# ============================================================
# motor_instance_repository.py
# Motor Database System
# Revision 2
# Motor Instance Repository
# ============================================================

from .base_repository import BaseRepository


class MotorInstanceRepository(BaseRepository):

    TABLE = "motor_instance"

    def create(self, instance_data):
        return self.insert(self.TABLE, instance_data)

    def get_by_id(self, instance_id):
        return self.fetch_one(
            """
            SELECT *
            FROM motor_instance
            WHERE instance_id=?
              AND is_deleted=0
            """,
            (instance_id,),
        )

    def get_by_model(self, motor_model_id):
        return self.fetch_all(
            """
            SELECT *
            FROM motor_instance
            WHERE motor_model_id=?
              AND is_deleted=0
            ORDER BY created_at DESC
            """,
            (motor_model_id,),
        )

    def get_all_active(self):
        return self.fetch_all(
            """
            SELECT *
            FROM motor_instance
            WHERE is_deleted=0
            ORDER BY created_at DESC
            """
        )

    def get_list_view(self):
        """一覧UI用。モデル名を含む個体情報を返す。"""
        return self.fetch_all(
            """
            SELECT *
            FROM vw_motor_instance
            ORDER BY created_at DESC
            """
        )

    def get_session_history(self, instance_id):
        """個体に紐づくMeasurement Session履歴。"""
        return self.fetch_all(
            """
            SELECT
                session_id,
                instance_id,
                motor_name,
                nickname,
                device_type,
                device_model,
                start_datetime,
                end_datetime,
                result
            FROM vw_latest_session
            WHERE instance_id=?
            ORDER BY start_datetime DESC
            """,
            (instance_id,),
        )

    def get_breakin_summary(self, session_id):
        return self.fetch_one(
            """
            SELECT *
            FROM vw_breakin_summary
            WHERE session_id=?
            """,
            (session_id,),
        )

    def get_latest_log(self, session_id):
        return self.fetch_one(
            """
            SELECT *
            FROM vw_latest_log
            WHERE session_id=?
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            (session_id,),
        )

    def update_instance(self, instance_id, data):
        return self.update(
            self.TABLE,
            data,
            "instance_id=?",
            (instance_id,),
        )

    def update_cache(self, instance_id, cache_data):
        allowed = {
            "latest_session_id",
            "latest_work_id",
            "first_log_id",
            "peak_log_id",
            "latest_log_id",
            "backup_log1",
            "backup_log2",
            "backup_log3",
        }

        update_data = {
            key: value
            for key, value in cache_data.items()
            if key in allowed
        }

        if not update_data:
            return 0

        return self.update(
            self.TABLE,
            update_data,
            "instance_id=?",
            (instance_id,),
        )

    def increment_anomaly(self, instance_id, consecutive=True):
        if consecutive:
            query = """
                UPDATE motor_instance
                SET anomaly_count=anomaly_count+1,
                    consecutive_anomaly_count=consecutive_anomaly_count+1,
                    updated_at=CURRENT_TIMESTAMP
                WHERE instance_id=?
            """
        else:
            query = """
                UPDATE motor_instance
                SET anomaly_count=anomaly_count+1,
                    updated_at=CURRENT_TIMESTAMP
                WHERE instance_id=?
            """

        cursor = self.execute(query, (instance_id,))
        self.database.commit()
        return cursor.rowcount

    def reset_consecutive_anomaly(self, instance_id):
        return self.update(
            self.TABLE,
            {"consecutive_anomaly_count": 0},
            "instance_id=?",
            (instance_id,),
        )

    def delete(self, instance_id):
        return self.soft_delete(self.TABLE, "instance_id", instance_id)


# ============================================================
# END OF motor_instance_repository.py
# ============================================================
