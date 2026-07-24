# ============================================================
# breakin_log_repository.py
# Motor Database System
# Revision 1
# Break-in Measurement Log Repository
# ============================================================

from .base_repository import BaseRepository



class BreakinLogRepository(BaseRepository):


    TABLE = "breakin_log"



    def create(
        self,
        log_data
    ):

        return self.insert(
            self.TABLE,
            log_data
        )



    def create_bulk(
        self,
        logs
    ):

        query = """

        INSERT INTO breakin_log
        (
            session_id,
            timestamp,
            elapsed_sec,
            voltage_v,
            current_ma,
            temperature_c,
            pwm,
            direction,
            measured_rpm,
            smartphone_rpm,
            quality_status,
            anomaly_type,
            memo
        )

        VALUES
        (
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?
        )

        """


        self.database.execute_many(
            query,
            logs
        )


        self.database.commit()



    def get_by_id(
        self,
        log_id
    ):

        return self.fetch_one(
            """
            SELECT *

            FROM breakin_log

            WHERE
                log_id=?

            """,
            (
                log_id,
            )
        )



    def get_by_session(
        self,
        session_id
    ):

        return self.fetch_all(
            """
            SELECT *

            FROM breakin_log

            WHERE
                session_id=?

            ORDER BY
                elapsed_sec ASC

            """,
            (
                session_id,
            )
        )



    def get_latest(
        self,
        session_id
    ):

        return self.fetch_one(
            """
            SELECT *

            FROM breakin_log

            WHERE
                session_id=?

            ORDER BY
                elapsed_sec DESC

            LIMIT 1

            """,
            (
                session_id,
            )
        )



    def get_peak_candidate(
        self,
        session_id
    ):

        return self.fetch_one(
            """
            SELECT *

            FROM breakin_log

            WHERE
                session_id=?

            AND
                quality_status='GOOD'

            ORDER BY
                measured_rpm DESC

            LIMIT 1

            """,
            (
                session_id,
            )
        )



    def count_anomaly(
        self,
        session_id
    ):

        result = self.fetch_one(
            """
            SELECT

                COUNT(*) AS count


            FROM breakin_log


            WHERE
                session_id=?

            AND
                anomaly_type!='NONE'

            """,
            (
                session_id,
            )
        )


        return result["count"]



# ============================================================
# END OF breakin_log_repository.py
# ============================================================

