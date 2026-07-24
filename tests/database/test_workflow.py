# ============================================================
# test_workflow.py
# Motor Database System
# Revision 1
# Database Workflow Test
# ============================================================

from database.manager.database_manager import DatabaseManager
from datetime import datetime


DB_PATH = "database/mini4wd.db"


def main():

    print("=" * 60)
    print("Database Workflow Test")
    print("=" * 60)


    db = DatabaseManager(DB_PATH)


    try:

        # ----------------------------------------------------
        # 1. Motor Instance create
        # ----------------------------------------------------

        instance_id = db.motor_instance.create(
            {
                "motor_model_id": 1,
                "serial_number": "FLOW-TEST-001",
                "nickname": "Workflow Test Motor",
                "status": "NEW"
            }
        )

        print(
            "[OK] Instance Created :",
            instance_id
        )


        # ----------------------------------------------------
        # 2. Start Work
        # ----------------------------------------------------

        work_id = db.start_work(
            instance_id,
            "BREAKIN",
            datetime.now().isoformat()
        )

        print(
            "[OK] Work Started :",
            work_id
        )


        # ----------------------------------------------------
        # 3. Start Session
        # ----------------------------------------------------

        session_id = db.start_session(
            instance_id,
            "BREAKIN",
            "MOTOR_BREAKIN_V3",
            "Rev1",
            "Analysis_Rev1",
            datetime.now().isoformat()
        )


        print(
            "[OK] Session Started :",
            session_id
        )


        # ----------------------------------------------------
        # 4. Insert Log
        # ----------------------------------------------------

        log_id = db.insert_log(
            {
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
                "elapsed_sec": 1,
                "voltage_v": 2.4,
                "current_ma": 500,
                "temperature_c": 25,
                "pwm": 120,
                "direction": "FWD",
                "quality_status": "GOOD",
                "anomaly_type": "NONE"
            }
        )


        print(
            "[OK] Log Inserted :",
            log_id
        )


        # ----------------------------------------------------
        # 5. Finish Session
        # ----------------------------------------------------

        db.finish_session(
            session_id,
            datetime.now().isoformat(),
            "COMPLETE"
        )


        print(
            "[OK] Session Finished"
        )


        # ----------------------------------------------------
        # 6. Finish Work
        # ----------------------------------------------------

        db.finish_work(
            work_id,
            datetime.now().isoformat(),
            1
        )


        print(
            "[OK] Work Finished"
        )


        print("=" * 60)
        print("DATABASE WORKFLOW TEST COMPLETE")
        print("=" * 60)


    finally:

        db.close()



if __name__ == "__main__":
    main()

