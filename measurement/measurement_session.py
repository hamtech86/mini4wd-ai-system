"""
=====================================================
 MINI4WD AI SYSTEM
 MOTOR_BREAKIN_V3
 measurement_session.py
=====================================================

Measurement Session

Measurementを管理するセッション情報。
Measurement原本とは独立して管理する。
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid


class MeasurementType(Enum):
    """
    測定種別
    """

    BREAKIN = "BREAKIN"
    EVALUATION = "EVALUATION"
    MANUAL = "MANUAL"


class SessionStatus(Enum):
    """
    セッション状態
    """

    READY = "READY"
    RUNNING = "RUNNING"
    FINISHED = "FINISHED"
    CANCELLED = "CANCELLED"
    ERROR = "ERROR"


@dataclass(slots=True)
class MeasurementSession:
    """
    Measurement Session
    """

    session_id: str = field(
        default_factory=lambda: str(uuid.uuid4())
    )

    measurement_type: MeasurementType = MeasurementType.BREAKIN

    status: SessionStatus = SessionStatus.READY

    start_time: datetime | None = None

    end_time: datetime | None = None

    measurement_count: int = 0

    operator: str = "SYSTEM"

    notes: str = ""

    schema_version: str = "1.0"

    firmware_version: str = "MOTOR_BREAKIN_V3"

    def start(self):
        """
        セッション開始
        """

        self.start_time = datetime.now()
        self.status = SessionStatus.RUNNING

    def finish(self):
        """
        セッション終了
        """

        self.end_time = datetime.now()
        self.status = SessionStatus.FINISHED

    def cancel(self):
        """
        セッションキャンセル
        """

        self.end_time = datetime.now()
        self.status = SessionStatus.CANCELLED

    def error(self):
        """
        エラー終了
        """

        self.end_time = datetime.now()
        self.status = SessionStatus.ERROR

    def add_measurement(self):
        """
        Measurement件数加算
        """

        self.measurement_count += 1

    @property
    def elapsed_seconds(self) -> float:
        """
        経過時間
        """

        if self.start_time is None:
            return 0.0

        end = self.end_time or datetime.now()

        return (end - self.start_time).total_seconds()

    @property
    def is_running(self) -> bool:
        """
        実行中判定
        """

        return self.status == SessionStatus.RUNNING

