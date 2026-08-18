"""Parser for the verified Battery 5A Standalone DATA frame.

Firmware contract (2ch5Abattery.ino):
DATA,BATTERY_DISCHARGER_V1,<CH1|CH2>,elapsed_ms,current,voltage,0,pwm,0,<state>

This module only maps the verified raw frame into the common Measurement model.
It does not change the Arduino firmware and does not estimate internal resistance.
"""

from __future__ import annotations

from measurement.measurement import Measurement


class BatteryMeasurementParseError(ValueError):
    pass


def parse_battery_data_frame(raw: str | bytes) -> Measurement:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="strict")

    fields = [x.strip() for x in str(raw).strip().split(",")]
    if len(fields) != 10 or fields[0] != "DATA":
        raise BatteryMeasurementParseError("invalid Battery DATA frame")
    if fields[1] != "BATTERY_DISCHARGER_V1":
        raise BatteryMeasurementParseError("unsupported Battery device model")
    if fields[2] not in {"CH1", "CH2"}:
        raise BatteryMeasurementParseError("invalid Battery channel")

    try:
        elapsed_ms = int(fields[3])
        current = float(fields[4])
        voltage = float(fields[5])
        pwm = int(fields[7])
    except ValueError as exc:
        raise BatteryMeasurementParseError("invalid numeric Battery DATA field") from exc

    channel = fields[2]
    current1 = current if channel == "CH1" else 0.0
    current2 = current if channel == "CH2" else 0.0
    voltage1 = voltage if channel == "CH1" else 0.0
    voltage2 = voltage if channel == "CH2" else 0.0
    power = voltage * current

    return Measurement(
        record_type="DATA",
        device_model="BATTERY_DISCHARGER_V1",
        instance_id=channel,
        elapsed_time=elapsed_ms,
        raw_acs1=0,
        raw_acs2=0,
        current1=current1,
        current2=current2,
        voltage1=voltage1,
        voltage2=voltage2,
        motor_voltage=voltage,
        pwm=pwm,
        direction="DISCHARGE",
        state=fields[9],
        current_avg=current,
        power=power,
        current_ripple=0.0,
        voltage_ripple=0.0,
        peak_power=power,
        peak_current=current,
        peak_voltage=voltage,
        peak_pwm=pwm,
        brush_peak_current=0.0,
        raw_magnetic=0,
        magnetic_level=0.0,
        motor_temperature=0.0,
        firmware_version="BATTERY_DISCHARGER_V1",
    )
