"""
=====================================================
 MINI4WD AI SYSTEM
 MOTOR_BREAKIN_V3
 config.py
=====================================================
システム共通設定
"""

from pathlib import Path

# =====================================================
# アプリケーション情報
# =====================================================

APP_NAME = "MINI4WD AI SYSTEM"
APP_VERSION = "3.0.0-beta1"

SCHEMA_VERSION = "1.0"
FIRMWARE_VERSION = "MOTOR_BREAKIN_V3"
ANALYSIS_VERSION = "1.0"

# =====================================================
# ディレクトリ
# =====================================================

ROOT_DIR = Path(__file__).parent

DATA_DIR = ROOT_DIR / "data"
LOG_DIR = ROOT_DIR / "logs"
DB_DIR = ROOT_DIR / "database"

DATABASE_FILE = DB_DIR / "mini4wd.db"

# 必要なディレクトリを生成
DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)
DB_DIR.mkdir(exist_ok=True)

# =====================================================
# シリアル通信
# =====================================================

DEFAULT_PORT = "/dev/ttyACM0"
DEFAULT_BAUDRATE = 57600
SERIAL_TIMEOUT = 0.1

# =====================================================
# Arduino コマンド
# =====================================================

CMD_START = "START"
CMD_STOP = "STOP"

CMD_FORWARD = "DIR FWD"
CMD_REVERSE = "DIR REV"

CMD_PWM = "PWM"

# =====================================================
# グラフ設定
# =====================================================

GRAPH_MAX_POINTS = 1000
GRAPH_UPDATE_MS = 100

# =====================================================
# ログ
# =====================================================

LOG_FILENAME_FORMAT = "motor_log_%Y%m%d_%H%M%S.csv"

# =====================================================
# CSV
# =====================================================

CSV_HEADER = [
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

# =====================================================
# UI更新
# =====================================================

UI_REFRESH_MS = 100

# =====================================================
# Measurement
# =====================================================

MEASUREMENT_SAVE_INTERVAL = 1

# =====================================================
# Analysis
# =====================================================

ENABLE_ANALYSIS = False

# β1ではMeasurementのみ実装

