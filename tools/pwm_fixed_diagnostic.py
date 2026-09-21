"""Fixed-PWM motor-voltage diagnostic for real-machine 3V control investigation.

This temporary diagnostic bypasses automatic voltage control and does not alter
STANDARD_3V30S / FULL_PACKAGE behavior.

It first finds the lowest PWM that produces an electrical response, then
measures fixed PWM points around that region. Only samples that are actually
RUN at the commanded PWM are used for the steady-state summary.
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
STEADY_START_DELAY_SEC = 0.5
FIXED_WINDOW_BELOW = 3
FIXED_WINDOW_ABOVE = 3


def parse_data(line: str):
    fields = [x.strip() for x in line.split(",")]
    if len(fields) < 26 or fields[0] != "DATA":
        return None
    try:
        return {
            "elapsed_time": int(float(fields[3])),
            "current_avg": float(fields[14]),
            "motor_voltage": float(fields[10]),
            "pwm": int(float(fields[11])),
            "state": fields[13],
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
        time.sleep(0.01)
    return measurements


def run_samples(measurements, test_pwm):
    return [
        m for m in measurements
        if m["state"] == "RUN" and m["pwm"] == test_pwm
    ]


def summarize(pwm, measurements, steady_only=False):
    source = measurements
    if steady_only:
        source = run_samples(measurements, pwm)

    if not source:
        return {
            "test_pwm": pwm,
            "samples": 0,
            "motor_voltage_mean": "",
            "motor_voltage_min": "",
            "motor_voltage_max": "",
            "motor_voltage_range": "",
            "motor_voltage_sd": "",
            "current_mean": "",
            "current_min": "",
            "current_max": "",
            "state_values": "",
            "actual_pwm_values": "",
        }

    values = [m["motor_voltage"] for m in source]
    currents = [m["current_avg"] for m in source]
    states = sorted(set(m["state"] for m in source))
    actual_pwms = sorted(set(m["pwm"] for m in source))
    return {
        "test_pwm": pwm,
        "samples": len(source),
        "motor_voltage_mean": round(statistics.mean(values), 4),
        "motor_voltage_min": round(min(values), 4),
        "motor_voltage_max": round(max(values), 4),
        "motor_voltage_range": round(max(values) - min(values), 4),
        "motor_voltage_sd": round(statistics.pstdev(values), 4)
        if len(values) > 1 else 0.0,
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
                result = summarize(pwm, measurements, steady_only=True)
                summary.append(result)

                print(
                    f"PWM={pwm}: RUN samples={result['samples']}, "
                    f"Vmean={result['motor_voltage_mean']}, "
                    f"Imean={result['current_mean']}, "
                    f"Vrange={result['motor_voltage_range']}, "
                    f"state={result['state_values']}, "
                    f"actual_pwm={result['actual_pwm_values']}"
                )

                # Electrical response only; this is not an evaluation threshold.
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
                low = max(0, start_pwm_found - FIXED_WINDOW_BELOW)
                high = min(END_PWM, start_pwm_found + FIXED_WINDOW_ABOVE)
                print(
                    f"\n=== FIXED PWM WINDOW {low}..{high}, "
                    f"{args.duration:.1f}s each ==="
                )

                for pwm in range(low, high + 1):
                    print(f"\n=== FIXED PWM {pwm} / {args.duration:.1f}s ===")
                    serial.stop_breakin()
                    time.sleep(0.5)
                    serial.set_pwm(pwm)
                    serial.send_command("START")
                    time.sleep(STEADY_START_DELAY_SEC)

                    measurements = collect_for(
                        serial, raw_writer, pwm, args.duration
                    )
                    result = summarize(pwm, measurements, steady_only=True)
                    summary.append(result)
                    print(
                        f"PWM={pwm}: RUN samples={result['samples']}, "
                        f"Vmean={result['motor_voltage_mean']}, "
                        f"Vmin={result['motor_voltage_min']}, "
                        f"Vmax={result['motor_voltage_max']}, "
                        f"Vrange={result['motor_voltage_range']}, "
                        f"Vsd={result['motor_voltage_sd']}, "
                        f"Imean={result['current_mean']}, "
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
            "motor_voltage_range", "motor_voltage_sd",
            "current_mean", "current_min", "current_max",
            "state_values", "actual_pwm_values",
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
