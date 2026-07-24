# ============================================================
# motor_repository.py
# Motor Database System
# Revision 1
# Motor Model Repository
# ============================================================

from .base_repository import BaseRepository



class MotorRepository(BaseRepository):


    TABLE = "motor_model"



    def create(
        self,
        motor_data
    ):

        return self.insert(
            self.TABLE,
            motor_data
        )



    def get_by_id(
        self,
        motor_model_id
    ):

        return self.fetch_one(
            """
            SELECT *

            FROM motor_model

            WHERE
                motor_model_id=?

            AND
                is_deleted=0

            """,
            (
                motor_model_id,
            )
        )



    def get_by_name(
        self,
        name
    ):

        return self.fetch_one(
            """
            SELECT *

            FROM motor_model

            WHERE
                name=?

            AND
                is_deleted=0

            """,
            (
                name,
            )
        )



    def get_all(self):

        return self.fetch_all(
            """
            SELECT *

            FROM motor_model

            WHERE
                is_deleted=0

            ORDER BY
                name

            """
        )



    def update_motor(
        self,
        motor_model_id,
        data
    ):

        return self.update(
            self.TABLE,
            data,
            "motor_model_id=?",
            (
                motor_model_id,
            )
        )



    def delete(
        self,
        motor_model_id
    ):

        return self.soft_delete(
            self.TABLE,
            "motor_model_id",
            motor_model_id
        )



# ============================================================
# END OF motor_repository.py
# ============================================================

