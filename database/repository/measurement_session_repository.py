# ============================================================
# measurement_session_repository.py
# Motor Database System
# Revision 1
# Measurement Session Repository
# ============================================================

from .base_repository import BaseRepository



class MeasurementSessionRepository(BaseRepository):


    TABLE = "measurement_session"



    def create(
        self,
        session_data
    ):

        return self.insert(
            self.TABLE,
            session_data
        )



    def get_by_id(
        self,
        session_id
    ):

        return self.fetch_one(
            """
            SELECT *

            FROM measurement_session

            WHERE
                session_id=?

            """,
            (
                session_id,
            )
        )



    def get_by_instance(
        self,
        instance_id
    ):

        return self.fetch_all(
            """
            SELECT *

            FROM measurement_session

            WHERE
                instance_id=?

            ORDER BY
                start_datetime DESC

            """,
            (
                instance_id,
            )
        )



    def get_by_device_type(
        self,
        device_type
    ):

        return self.fetch_all(
            """
            SELECT *

            FROM measurement_session

            WHERE
                device_type=?

            ORDER BY
                start_datetime DESC

            """,
            (
                device_type,
            )
        )



    def finish_session(
        self,
        session_id,
        end_datetime,
        result
    ):

        return self.update(
            self.TABLE,
            {
                "end_datetime": end_datetime,

                "result": result
            },
            "session_id=?",
            (
                session_id,
            )
        )



    def get_latest(
        self,
        instance_id
    ):

        return self.fetch_one(
            """
            SELECT *

            FROM measurement_session

            WHERE
                instance_id=?

            ORDER BY
                start_datetime DESC

            LIMIT 1

            """,
            (
                instance_id,
            )
        )



# ============================================================
# END OF measurement_session_repository.py
# ============================================================

