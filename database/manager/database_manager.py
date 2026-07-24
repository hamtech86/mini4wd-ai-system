# ============================================================
# database_manager.py
# Motor Database System
# Revision 1
# Database Facade Manager
# ============================================================

from .connection import DatabaseConnection
from .transaction import TransactionManager

from ..repository.motor_repository import MotorRepository
from ..repository.motor_instance_repository import MotorInstanceRepository
from ..repository.motor_work_repository import MotorWorkRepository
from ..repository.measurement_session_repository import MeasurementSessionRepository
from ..repository.breakin_log_repository import BreakinLogRepository
from ..repository.schema_repository import SchemaRepository



class DatabaseManager:


    def __init__(
        self,
        database_path
    ):


        self.connection = DatabaseConnection(
            database_path
        )


        self.connection.connect()



        self.transaction = TransactionManager(
            self.connection
        )



        self.motor = MotorRepository(
            self.connection
        )


        self.motor_instance = MotorInstanceRepository(
            self.connection
        )


        self.motor_work = MotorWorkRepository(
            self.connection
        )


        self.session = MeasurementSessionRepository(
            self.connection
        )


        self.breakin_log = BreakinLogRepository(
            self.connection
        )


        self.schema = SchemaRepository(
            self.connection
        )



    # ========================================================
    # Motor workflow
    # ========================================================


    def start_work(
        self,
        instance_id,
        work_type,
        start_datetime
    ):

        work_id = self.motor_work.create(
            {
                "instance_id": instance_id,
                "work_type": work_type,
                "start_datetime": start_datetime
            }
        )

        self.motor_instance.update_cache(
            instance_id,
            {
                "latest_work_id": work_id
            }
        )

        return work_id



    def start_session(
        self,
        instance_id,
        device_type,
        device_model,
        firmware_version,
        analysis_version,
        start_datetime
    ):


        session_id = self.session.create(
            {

                "instance_id":
                    instance_id,

                "device_type":
                    device_type,

                "device_model":
                    device_model,

                "firmware_version":
                    firmware_version,

                "analysis_version":
                    analysis_version,

                "start_datetime":
                    start_datetime

            }
        )


        self.motor_instance.update_cache(

            instance_id,

            {

                "latest_session_id":
                    session_id

            }

        )


        return session_id



    def insert_log(
        self,
        log_data
    ):

        log_id = self.breakin_log.create(
            log_data
        )


        return log_id



    def finish_session(
        self,
        session_id,
        end_datetime,
        result
    ):


        return self.session.finish_session(
            session_id,
            end_datetime,
            result
        )



    def finish_work(
        self,
        work_id,
        end_datetime,
        duration_sec
    ):


        return self.motor_work.finish_work(
            work_id,
            end_datetime,
            duration_sec
        )



    # ========================================================
    # Cache management
    # ========================================================


    def update_motor_cache(
        self,
        instance_id,
        cache_data
    ):


        return self.motor_instance.update_cache(
            instance_id,
            cache_data
        )



    # ========================================================
    # Transaction support
    # ========================================================


    def begin_transaction(
        self
    ):

        self.transaction.begin()



    def commit(
        self
    ):

        self.transaction.commit()



    def rollback(
        self
    ):

        self.transaction.rollback()



    # ========================================================
    # Utility
    # ========================================================


    def close(
        self
    ):

        self.connection.close()



    def schema_version(
        self
    ):

        return self.schema.get_version()



# ============================================================
# END OF database_manager.py
# ============================================================

