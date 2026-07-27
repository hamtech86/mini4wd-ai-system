"""
=====================================================
 MINI4WD AI SYSTEM
 MOTOR_BREAKIN_V3
 csv_parser.py
=====================================================

Arduinoから受信したCSV文字列を
Pythonで扱いやすい辞書へ変換する。

Communication層は通信のみを担当し、
Measurementオブジェクトの生成は行わない。
"""

from typing import Dict, Any

from loguru import logger

from communication.protocol import (
    CSV_FIELDS,
    CSV_FIELD_COUNT,
)


class CSVParser:
    """CSV解析クラス"""

    def parse(self, line: str) -> Dict[str, Any]:
        """
        CSV文字列を辞書へ変換

        Parameters
        ----------
        line : str
            Arduinoから受信したCSV文字列

        Returns
        -------
        Dict[str, Any]
        """

        line = line.strip()

        if not line:
            raise ValueError("Empty CSV line")

        values = line.split(",")

        if not self.validate(values):
            logger.error(
                f"CSV項目数エラー ({len(values)}/{CSV_FIELD_COUNT})"
            )
            raise ValueError("Invalid CSV length")

        data: Dict[str, Any] = {}

        for key, value in zip(CSV_FIELDS, values):
            data[key] = self.parse_number(value)

        return data

    def validate(self, values: list) -> bool:
        """
        CSV項目数チェック
        """

        return len(values) == CSV_FIELD_COUNT

    def parse_number(self, value: str):
        """
        数値変換

        int → int
        float → float
        その他 → str
        空文字 → None
        """

        value = value.strip()

        if value == "":
            return None

        try:
            if "." in value:
                return float(value)

            return int(value)

        except ValueError:
            return value

    @staticmethod
    def is_data_record(data: Dict[str, Any]) -> bool:
        """DATAレコード判定"""

        return data.get("record_type") == "DATA"

    @staticmethod
    def is_info_record(data: Dict[str, Any]) -> bool:
        """INFOレコード判定"""

        return data.get("record_type") == "INFO"

    @staticmethod
    def is_error_record(data: Dict[str, Any]) -> bool:
        """ERRORレコード判定"""

        return data.get("record_type") == "ERROR"

