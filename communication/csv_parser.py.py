"""
=====================================================
 MINI4WD AI SYSTEM
 MOTOR_BREAKIN_V3
 csv_parser.py
=====================================================

Arduinoから受信したCSV文字列を
Measurementで利用できる形式へ変換する。
"""

from typing import Dict, Any

from loguru import logger

from communication.protocol import (
    CSV_FIELDS,
    validate_csv_length,
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

        if not validate_csv_length(values):
            logger.error(
                f"CSV項目数エラー "
                f"({len(values)}/{len(CSV_FIELDS)})"
            )
            raise ValueError("Invalid CSV length")

        data = {}

        for key, value in zip(CSV_FIELDS, values):

            value = value.strip()

            if value == "":
                data[key] = None
                continue

            # 数値変換
            try:

                if "." in value:
                    data[key] = float(value)

                else:
                    data[key] = int(value)

                continue

            except ValueError:
                pass

            # 文字列
            data[key] = value

        return data

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

