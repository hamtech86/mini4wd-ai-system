"""
Mini4WD Database Test Runner
"""

import traceback

from test_connection import run as connection_test
from test_schema import run as schema_test
from test_motor_repository import run as motor_test
from test_instance_repository import run as instance_test
from test_session_repository import run as session_test
from test_breakin_repository import run as breakin_test
from test_database_manager import run as manager_test


TESTS = [
    ("Connection", connection_test),
    ("Schema", schema_test),
    ("MotorRepository", motor_test),
    ("MotorInstanceRepository", instance_test),
    ("MeasurementSessionRepository", session_test),
    ("BreakinLogRepository", breakin_test),
    ("DatabaseManager", manager_test),
]


def main():

    print("=" * 60)
    print("Mini4WD Database Self Test")
    print("=" * 60)

    passed = 0

    for name, func in TESTS:

        print(f"\n[{name}]")

        try:

            func()

            print("PASS")

            passed += 1

        except Exception:

            print("FAIL")

            traceback.print_exc()

    print("\n" + "=" * 60)

    print(f"{passed}/{len(TESTS)} tests passed.")

    print("=" * 60)


if __name__ == "__main__":
    main()

