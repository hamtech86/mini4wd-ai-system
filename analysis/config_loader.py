"""
=====================================================
 MINI4WD AI SYSTEM
 MOTOR_BREAKIN_V3
 analysis/config_loader.py
=====================================================

Analysis Config Loader

Analysisで使用する設定ファイルを読み込む。

・設定はキャッシュする
・Analysisは設定のみ参照する
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class ConfigLoader:
    """
    Analysis設定読込クラス
    """

    def __init__(
        self,
        config_directory: str = "config",
    ):

        self.config_directory = Path(
            config_directory
        )

        self._cache: dict[str, Any] = {}

    def load(
        self,
        filename: str,
    ) -> dict[str, Any]:
        """
        YAML読込
        """

        if filename in self._cache:

            return self._cache[filename]

        path = self.config_directory / filename

        if not path.exists():

            raise FileNotFoundError(path)

        with open(
            path,
            "r",
            encoding="utf-8",
        ) as fp:

            data = yaml.safe_load(fp)

        self._cache[filename] = data

        return data

    def clear_cache(self):
        """
        キャッシュ削除
        """

        self._cache.clear()

