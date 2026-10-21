"""
MINI4WD AI SYSTEM - DATA and INFO protocol parser.
DATA remains the fixed 26-field contract; INFO is parsed separately.
"""
from typing import Dict, Any
from loguru import logger
from communication.protocol import CSV_FIELDS, CSV_FIELD_COUNT

INFO_FIELDS = ("TYPE", "MODEL", "FW", "BUILD", "ID")


class CSVParser:
    """Strict line-oriented parser for DATA and INFO records."""

    def parse(self, line: str) -> Dict[str, Any]:
        line = line.strip()
        if not line:
            raise ValueError("Empty CSV line")
        if line == "INFO" or line.startswith("INFO,"):
            return self.parse_info(line)
        values = line.split(",")
        if not self.validate(values):
            logger.error(f"CSV項目数エラー ({len(values)}/{CSV_FIELD_COUNT})")
            raise ValueError("Invalid CSV length")
        return {key: self.parse_number(value) for key, value in zip(CSV_FIELDS, values)}

    def parse_info(self, line: str) -> Dict[str, Any]:
        tokens = line.strip().split(",")
        if not tokens or tokens[0] != "INFO":
            raise ValueError("Invalid INFO record type")
        info: Dict[str, Any] = {"record_type": "INFO"}
        for token in tokens[1:]:
            if "=" not in token:
                raise ValueError("Malformed INFO field")
            key, value = token.split("=", 1)
            key, value = key.strip(), value.strip()
            if key not in INFO_FIELDS:
                raise ValueError(f"Unknown INFO field: {key}")
            if key in info:
                raise ValueError(f"Duplicate INFO field: {key}")
            if not value:
                raise ValueError(f"Empty INFO field: {key}")
            info[key] = value
        missing = [key for key in INFO_FIELDS if key not in info]
        if missing:
            raise ValueError("Missing INFO fields: " + ",".join(missing))
        return info

    def validate(self, values: list) -> bool:
        return len(values) == CSV_FIELD_COUNT

    def parse_number(self, value: str):
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
        return data.get("record_type") == "DATA"

    @staticmethod
    def is_info_record(data: Dict[str, Any]) -> bool:
        return data.get("record_type") == "INFO"

    @staticmethod
    def is_error_record(data: Dict[str, Any]) -> bool:
        return data.get("record_type") == "ERROR"
