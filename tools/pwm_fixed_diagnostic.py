"""Fixed-PWM motor-voltage diagnostic for real-machine 3V control investigation.

This temporary diagnostic bypasses automatic voltage control and does not alter
STANDARD_3V30S / FULL_PACKAGE behavior.

It first finds the lowest PWM that actually produces motor current/rotation
indication, then measures fixed PWM points around the 3V operating region.
"""
from __future__ import annotations

import argparse
import csv
import os
import statistics
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from communication.serial_controller import SerialController

START_PWM = 40
END_PWM = 80
STEP_PWM = 1
START_TEST_SEC = 2.0
MEASURE_DURATION_SEC = 10.0
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
            "state": fields[5],
        }
    except (ValueError, IndexError):
        return None


def read_and_record(serial, raw_writer, test_pwm):
    rows = []
    while serial.serial and serial.serial.in_waiting:
        raw = serial.serial.readline().decode("utf-8", errors="replace").strip()
        if not raw:
            continue
        received_at = datetime.now().isoformat(timespec="milliseconds")
        raw_writer.writerow([test_pwm, received_at, raw])
        measurement = parse_data(raw)
        if measurement is not None:
            rows.append(measurement)
    return rows


def collect_for(serial, raw_writer, test_pwm, duration):
    measurements = []
    started = time.monotonic()
    while time.monotonic() - started < duration:
        measurements.extend(read_and_record(serial, raw_writer, test_pwm))
        raw_writer.writerow([test_pwm, datetime.now().isoformat(timespec="milliseconds"), ""])
        time.sleep(0.01)
    return measurements


def summarize(pwm, measurements):
    if not measurements:
        return {
            "test_pwm": pwm, "samples": 0,
            "motor_voltage_mean": "", "motor_voltage_min": "",
            "motor_voltage_max": "", "motor_voltage_range": "",
            "current_mean": "", "current_min": "", "current_max": "",
            "state_values": "", "actual_pwm_values": "",
        }

    values = [m["motor_voltage"] for m in measurements]
    currents = [m["current_avg"] for m in measurements]
    states = sorted(set(m["state"] for m in measurements))
    actual_pwms = sorted(set(m["pwm"] for m in measurements))
    return {
        "test_pwm": pwm,
        "samples": len(measurements),
        "motor_voltage_mean": round(statistics.mean(values), 4),
        "motor_voltage_min": round(min(values), 4),
        "motor_voltage_max": round(max(values), 4),
        "motor_voltage_range": round(max(values) - min(values), 4),
        "current_mean": round(statistics.mean(currents), 4),
        "current_min": round(min(currents), 4),
        "current_max": round(max(currents), 4),
        "state_values": "|".join(states),
        "actual_pwm_values": "|".join(str(x) for x in actual_pwms),
    }


def run(args):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = args.output or os.path.join("data", "diagnostics")
    os.makedirs(out_dir, exist_ok=True)

    raw_path = os.path.join(out_dir, f"PWM_STARTUP_{timestamp}.csv")
    summary_path = os.path.join(out_dir, f"PWM_STARTUP_{timestamp}_summary.csv")

    serial = SerialController(serial_port=args.port, baudrate=args.baudrate)
    if not serial.connect():
        raise RuntimeError(f"Serial connection failed: {args.port}")

    summary = []
    start_pwm_found = None

    try:
        with open(raw_path, "w", newline="", encoding="utf-8") as raw_file:
            raw_writer = csv.writer(raw_file)
            raw_writer.writerow(["test_pwm", "received_at", "raw_data"])

            print(f"=== STARTUP SEARCH PWM {START_PWM}..{END_PWM} ===")
            for pwm in range(START_PWM, END_PWM + 1, STEP_PWM):
                print(f"\n=== START TEST PWM {pwm} / {START_TEST_SEC:.1f}s ===")
                serial.stop_breakin()
                time.sleep(0.3)
                serial.set_pwm(pwm)
                serial.send_command("START")
                time.sleep(0.2)

                measurements = collect_for(
                    serial, raw_writer, pwm, START_TEST_SEC
                )
                result = summarize(pwm, measurements)
                summary.append(result)

                print(
                    f"PWM={pwm}: samples={result['samples']}, "
                    f"Vmean={result['motor_voltage_mean']}, "
                    f"Imean={result['current_mean']}, "
                    f"Vrange={result['motor_voltage_range']}, "
                    f"state={result['state_values']}, "
                    f"actual_pwm={result['actual_pwm_values']}"
                )

                # A non-zero current is used only as an electrical indication
                # that the motor/driver is responding. This is not an evaluation
                # threshold and does not replace physical observation.
                if (
                    measurements
                    and max(abs(m["current_avg"]) for m in measurements) >= 0.10
                ):
                    start_pwm_found = pwm
                    print(f"START RESPONSE FOUND AT PWM={pwm}")
                    serial.stop_breakin()
                    break

            if start_pwm_found is None:
                print("NO ELECTRICAL START RESPONSE FOUND IN SEARCH RANGE")
            else:
                # Re-test the found point and the next several PWM counts to
                # characterize the low-PWM region before the 3V measurement.
                for pwm in range(
                    start_pwm_found,
                    min(start_pwm_found + 10, END_PWM) + 1
                ):
                    print(f"\n=== FIXED PWM {pwm} / {args.duration:.1f}s ===")
                    serial.stop_breakin()
                    time.sleep(0.5)
                    serial.set_pwm(pwm)
                    serial.send_command("START")
                    time.sleep(0.2)

                    measurements = collect_for(
                        serial, raw_writer, pwm, args.duration
                    )
                    result = summarize(pwm, measurements)
                    summary.append(result)
                    print(
                        f"PWM={pwm}: Vmean={result['motor_voltage_mean']}, "
                        f"Vmin={result['motor_voltage_min']}, "
                        f"Vmax={result['motor_voltage_max']}, "
                        f"Vrange={result['motor_voltage_range']}, "
                        f"Imean={result['current_mean']}, "
                        f"state={result['state_values']}, "
                        f"actual_pwm={result['actual_pwm_values']}"
                    )

                    serial.stop_breakin()
                    time.sleep(0.5)

    finally:
        serial.stop_breakin()
        serial.disconnect()

    with open(summary_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "test_pwm", "samples", "motor_voltage_mean",
            "motor_voltage_min", "motor_voltage_max",
            "motor_voltage_range", "current_mean", "current_min",
            "current_max", "state_values", "actual_pwm_values",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary)

    print(f"\nRaw diagnostic log: {raw_path}")
    print(f"Summary: {summary_path}")
    print(f"Detected start-response PWM: {start_pwm_found}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default="/dev/ttyACM0")
    parser.add_argument("--baudrate", type=int, default=DEFAULT_BAUDRATE)
    parser.add_argument("--duration", type=float, default=MEASURE_DURATION_SEC)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
