"""Verify Battery Benchmark v2 against raw Measurement data.

Checks one or more Benchmark Result rows and confirms that start_voltage,
end_voltage and voltage_drop match the first/last valid raw Measurement sample.
No data is modified.
"""
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("database/mini4wd.db")


def main():
    with sqlite3.connect(DB_PATH) as db:
        rows = db.execute(
            """SELECT result_id, session_id, start_voltage, end_voltage, voltage_drop
               FROM battery_benchmark_result
               ORDER BY result_id DESC"""
        ).fetchall()
        if not rows:
            print("NO_BENCHMARK_RESULT")
            return 2

        checked = 0
        for result_id, session_id, stored_start, stored_end, stored_drop in rows:
            first = db.execute(
                """SELECT voltage1 FROM measurement
                   WHERE session_id=? AND voltage1 IS NOT NULL
                   ORDER BY elapsed_time ASC LIMIT 1""",
                (session_id,),
            ).fetchone()
            last = db.execute(
                """SELECT voltage1 FROM measurement
                   WHERE session_id=? AND voltage1 IS NOT NULL
                   ORDER BY elapsed_time DESC LIMIT 1""",
                (session_id,),
            ).fetchone()
            if first is None or last is None:
                print(f"result_id={result_id} session_id={session_id}: NO_RAW_MEASUREMENT")
                continue

            expected_start = float(first[0])
            expected_end = float(last[0])
            expected_drop = expected_start - expected_end
            ok = (
                stored_start is not None
                and stored_end is not None
                and stored_drop is not None
                and abs(float(stored_start) - expected_start) < 1e-9
                and abs(float(stored_end) - expected_end) < 1e-9
                and abs(float(stored_drop) - expected_drop) < 1e-9
            )
            print(
                f"result_id={result_id} session_id={session_id} "
                f"start={stored_start} expected={expected_start} "
                f"end={stored_end} expected={expected_end} "
                f"drop={stored_drop} expected={expected_drop} "
                f"=> {'PASS' if ok else 'FAIL'}"
            )
            checked += 1
            if not ok:
                return 1

        if checked == 0:
            print("NO_RESULT_WITH_RAW_MEASUREMENT")
            return 2
        print(f"BATTERY_BENCHMARK_V2_E2E_PASS checked={checked}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
