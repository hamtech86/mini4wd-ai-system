"""
=====================================================
 MINI4WD AI SYSTEM
 MOTOR_BREAKIN_V3
 measurement_logger.py
=====================================================

Measurement CSV Logger

Measurement原本をCSVへ保存する。
Loggerは保存のみを担当し、
Measurementの生成や解析は行わない。
"""

from __future__ import annotations

import csv
from dataclasses import fields
from pathlib import Path
from datetime import datetime
from typing import Optional

from measurement.measurement import Measurement


class MeasurementLogger:
    """
    Measurement CSV Logger
    """

    def __init__(self, log_dir: str = "logs"):

        self.log_dir = Path(log_dir)

        self.log_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.file: Optional[object] = None
        self.writer: Optional[csv.writer] = None
        self.filepath: Optional[Path] = None

    @property
    def is_open(self) -> bool:
        """
        ログファイルオープン状態
        """

        return self.file is not None

    def start(self, session_id: str) -> Path:
        """
        ログ開始
        """

        filename = (
            f"measurement_{session_id}_"
            f"{datetime.now():%Y%m%d_%H%M%S}.csv"
        )

        self.filepath = self.log_dir / filename

        self.file = open(
            self.filepath,
            mode="w",
            newline="",
            encoding="utf-8-sig",
        )

        self.writer = csv.writer(self.file)

        self.writer.writerow(
            [field.name for field in fields(Measurement)]
        )

        return self.filepath

    def write(self, measurement: Measurement):
        """
        Measurementを1件保存
        """

        if not self.is_open:
            return

        row = [
            getattr(measurement, field.name)
            for field in fields(Measurement)
        ]

        self.writer.writerow(row)

    def flush(self):
        """
        バッファ書き込み
        """

        if self.file is not None:
            self.file.flush()

    def stop(self):
        """
        ログ終了
        """

        if self.file is None:
            return

        self.file.flush()
        self.file.close()

        self.file = None
        self.writer = None

