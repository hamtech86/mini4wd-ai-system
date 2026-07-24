# ============================================================
# motor_work_repository.py
# Motor Database System
# Revision 1
# Motor Work Repository
# ============================================================

from .base_repository import BaseRepository



class MotorWorkRepository(BaseRepository):


    TABLE = "motor_work"



    def create(
        self,
        work_data
    ):

        return self.insert(
            self.TABLE,
            work_data
        )



    def get_by_id(
        self,
        work_id
    ):

        return self.fetch_one(
            """
            SELECT *

            FROM motor_work

            WHERE
                work_id=?

            """,
            (
                work_id,
            )
        )



    def get_by_instance(
        self,
        instance_id
    ):

        return self.fetch_all(
            """
            SELECT *

            FROM motor_work

            WHERE
                instance_id=?

            ORDER BY
                start_datetime DESC

            """,
            (
                instance_id,
            )
        )



    def get_by_type(
        self,
        work_type
    ):

        return self.fetch_all(
            """
            SELECT *

            FROM motor_work

            WHERE
                work_type=?

            ORDER BY
                start_datetime DESC

            """,
            (
                work_type,
            )
        )



    def finish_work(
        self,
        work_id,
        end_datetime,
        duration_sec,
        memo=None
    ):

        data = {

            "end_datetime": end_datetime,

            "duration_sec": duration_sec

        }


        if memo is not None:

            data["memo"] = memo



        return self.update(
            self.TABLE,
            data,
            "work_id=?",
            (
                work_id,
            )
        )



    def delete(
        self,
        work_id
    ):

        query = """

        DELETE FROM motor_work

        WHERE
            work_id=?

        """


        cursor = self.execute(
            query,
            (
                work_id,
            )
        )


        self.database.commit()


        return cursor.rowcount



# ============================================================
# END OF motor_work_repository.py
# ============================================================

