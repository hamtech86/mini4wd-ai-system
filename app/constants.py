"""
=====================================================
 MINI4WD AI SYSTEM
 MOTOR_BREAKIN_V3
 constants.py
=====================================================
システム共通定数
"""

from enum import Enum


# =====================================================
# Direction
# =====================================================

class Direction(Enum):
    """モーター回転方向"""

    FORWARD = "FWD"
    REVERSE = "REV"


# =====================================================
# Device State
# =====================================================

class DeviceState(Enum):
    """Arduino状態"""

    READY = "READY"
    RUNNING = "RUNNING"
    STOP = "STOP"
    ERROR = "ERROR"


# =====================================================
# Measurement Session
# =====================================================

class SessionState(Enum):
    """Measurement Session"""

    IDLE = "IDLE"
    STARTED = "STARTED"
    FINISHED = "FINISHED"
    CANCELLED = "CANCELLED"


# =====================================================
# Work State
# =====================================================

class WorkState(Enum):
    """ブレイクイン処理"""

    NONE = "NONE"
    BREAKIN = "BREAKIN"
    EVALUATION = "EVALUATION"


# =====================================================
# CSV Record
# =====================================================

class RecordType(Enum):
    """CSVレコード種別"""

    DATA = "DATA"
    INFO = "INFO"
    ERROR = "ERROR"


# =====================================================
# Arduino Commands
# =====================================================

# Firmware MOTOR_BREAKIN_V3.00 command protocol.
# The firmware accepts bare FWD/REV and PWM=<0..255>.
CMD_START = "START"
CMD_STOP = "STOP"

CMD_FORWARD = "FWD"
CMD_REVERSE = "REV"

CMD_PWM = "PWM="

CMD_STATUS = "STATUS"

CMD_RESET = "RESET"

CMD_VERSION = "VERSION"


# =====================================================
# UI
# =====================================================

WINDOW_TITLE = "MOTOR BREAK-IN V3"

DEFAULT_STATUS = "Disconnected"

CONNECT_TEXT = "Connect"

DISCONNECT_TEXT = "Disconnect"

START_TEXT = "START"

STOP_TEXT = "STOP"


# =====================================================
# Graph
# =====================================================

GRAPH_VOLTAGE = "Motor Voltage"

GRAPH_CURRENT = "Motor Current"

GRAPH_BRUSH = "Brush Current"

GRAPH_POWER = "Power"


# =====================================================
# Measurement
# =====================================================

MEASUREMENT_TYPE_BREAKIN = "BREAKIN"

MEASUREMENT_TYPE_EVALUATION = "EVALUATION"


# =====================================================
# Analysis
# β1では未使用
# =====================================================

ANALYSIS_READY = "READY"

ANALYSIS_RUNNING = "RUNNING"

ANALYSIS_FINISHED = "FINISHED"
