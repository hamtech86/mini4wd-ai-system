"""
=====================================================
 MINI4WD AI SYSTEM
 MOTOR_BREAKIN_V3
 protocol.py
=====================================================

Arduino ⇔ Python 通信仕様

CSV Protocol Version : 1.0
"""

from enum import Enum

# =====================================================
# Protocol Version
# =====================================================

PROTOCOL_VERSION = "1.0"

# =====================================================
# CSV Record Type
# =====================================================

class RecordType(Enum):
    DATA = "DATA"
    INFO = "INFO"
    ERROR = "ERROR"


# =====================================================
# CSV Header
# Arduino送信順と完全一致
# =====================================================

CSV_FIELDS = [

    "record_type",

    "device_model",

    "instance_id",

    "elapsed_time",

    "raw_acs1",

    "raw_acs2",

    "current1",

    "current2",

    "voltage1",

    "voltage2",

    "motor_voltage",

    "pwm",

    "direction",

    "state",

    "current_avg",

    "power",

    "current_ripple",

    "voltage_ripple",

    "peak_power",

    "peak_current",

    "peak_voltage",

    "peak_pwm",

    "brush_peak_current",

    "raw_magnetic",

    "magnetic_level",

    "motor_temperature",

]

CSV_FIELD_COUNT = len(CSV_FIELDS)


# =====================================================
# Utility
# =====================================================

def validate_csv_length(data: list) -> bool:
    """
    CSV項目数チェック
    """

    return len(data) == CSV_FIELD_COUNT


def get_field_index(name: str) -> int:
    """
    フィールド番号取得
    """

    return CSV_FIELDS.index(name)

