"""Fixed-PWM motor-voltage diagnostic for real-machine 3V control investigation.

This tool intentionally bypasses automatic voltage control. It is not a benchmark
and does not alter STANDARD_3V30S / FULL_PACKAGE behavior.

Run from repository root:
    python tools/pwm_fixed_diagnostic.py --port /dev/ttyACM0

The default test points are PWM 43..50, 10 seconds each. During each point the
PWM is held fixed and the received DATA frames are written unchanged to a
diagnostic raw CSV. A summary CSV reports min/max/mean Motor V and current.
"""
from __future__ import annotations

import argparse
import csv
import os
import statistics
import time
from datetime import datetime

from communication.serial_controller import SerialController


PWM_VALUES = tuple(range(43, 51))
DEFAULT_DURATION_SEC = 10.0
DEFAULT_BAUDRATE = 57600


def parse_data(line: str):
    fields = [x.strip() for x in line.split(",")]
    if len(fields) < 16 or fields[0] != "DATA":
        return None
    try:
        return {
            "elapsed_time": int(float(fields[3])),
            "current_avg": float(fields[14]),
            "motor_voltage": float(fields[10]),
            "pwm": int(float(fields[11])),
        }
    except (ValueError, IndexError):
        return None


def run(args):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = args.output or os.path.join("data", "diagnostics")
    os.makedirs(out_dir, exist_ok=True)

    raw_path = os.path.join(out_dir, f"PWM_FIXED_{timestamp}.csv")
    summary_path = os.path.join(out_dir, f"PWM_FIXED_{timestamp}_summary.csv")

    serial = SerialController(serial_port=args.port, baudrate=args.baudrate)
    if not serial.connect():
        raise RuntimeError(f"Serial connection failed: {args.port}")

    rows = []
    summary = []

    try:
        serial.forward()
        time.sleep(0.5)

        with open(raw_path, "w", newline="", encoding="utf-8") as raw_file:
            raw_writer = csv.writer(raw_file)
            raw_writer.writerow(["test_pwm", "received_at", "raw_data"])

            for pwm in PWM_VALUES:
                print(f"\\n=== FIXED PWM {pwm} / {args.duration:.1f}s ===")
                serial.set_pwm(pwm)
                started = time.monotonic()
                values = []
                currents = []

                while time.monotonic() - started < args.duration:
                    while serial.serial and serial.serial.in_waiting:
                        raw = serial.serial.readline().decode(
                            "utf-8", errors="replace"
                        ).strip()
                        if not raw:
                            continue

                        received_at = datetime.now().isoformat(timespec="milliseconds")
                        raw_writer.writerow([pwm, received_at, raw])
                        raw_file.flush()

                        measurement = parse_data(raw)
                        if measurement is None:
                            continue

                        values.append(measurement["motor_voltage"])
                        currents.append(measurement["current_avg"])
                        rows.append({
                            "test_pwm": pwm,
                            "received_at": received_at,
                            **measurement,
                        })

                    time.sleep(0.01)

                if values:
                    summary.append({
                        "test_pwm": pwm,
                        "samples": len(values),
                        "motor_voltage_mean": round(statistics.mean(values), 4),
                        "motor_voltage_min": round(min(values), 4),
                        "motor_voltage_max": round(max(values), 4),
                        "motor_voltage_range": round(max(values) - min(values), 4),
                        "current_mean": round(statistics.mean(currents), 4),
                        "current_min": round(min(currents), 4),
                        "current_max": round(max(currents), 4),
                    })
                    print(
                        f"PWM={pwm}: V mean={summary[-1]['motor_voltage_mean']:.4f}, "
                        f"min={summary[-1]['motor_voltage_min']:.4f}, "
                        f"max={summary[-1]['motor_voltage_max']:.4f}, "
                        f"range={summary[-1]['motor_voltage_range']:.4f}"
                    )
                else:
                    summary.append({
                        "test_pwm": pwm,
                        "samples": 0,
                        "motor_voltage_mean": "",
                        "motor_voltage_min": "",
                        "motor_voltage_max": "",
                        "motor_voltage_range": "",
                        "current_mean": "",
                        "current_min": "",
                        "current_max": "",
                    })
                    print(f"PWM={pwm}: DATA frame not received")

                serial.set_pwm(0)
                time.sleep(1.0)

    finally:
        serial.stop_breakin()
        serial.disconnect()

    with open(summary_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=summary[0].keys())
        writer.writeheader()
        writer.writerows(summary)

    print(f"\\nRaw diagnostic log: {raw_path}")
    print(f"Summary: {summary_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default="/dev/ttyACM0")
    parser.add_argument("--baudrate", type=int, default=DEFAULT_BAUDRATE)
    parser.add_argument("--duration", type=float, default=DEFAULT_DURATION_SEC)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
