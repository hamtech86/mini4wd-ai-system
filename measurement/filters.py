"""
=====================================================
 MINI4WD AI SYSTEM
 MOTOR_BREAKIN_V3
 filters.py
=====================================================

Measurement Filters

Measurement層で使用するフィルタ群

・EMA（指数移動平均）
・SMA（単純移動平均）

Analysis用ではなく、
Measurement表示・記録補助用。
"""

from __future__ import annotations

from collections import deque


class EMAFilter:
    """
    Exponential Moving Average
    """

    def __init__(self, alpha: float = 0.20):

        if not 0.0 < alpha <= 1.0:
            raise ValueError("alpha must be 0 < alpha <= 1")

        self.alpha = alpha
        self._value = None

    def reset(self):

        self._value = None

    @property
    def value(self):

        return self._value

    def update(self, sample: float) -> float:

        if self._value is None:

            self._value = sample

        else:

            self._value = (
                self.alpha * sample
                + (1.0 - self.alpha) * self._value
            )

        return self._value


class SMAFilter:
    """
    Simple Moving Average
    """

    def __init__(self, window_size: int = 10):

        if window_size <= 0:
            raise ValueError("window_size must be > 0")

        self.samples = deque(maxlen=window_size)

    def reset(self):

        self.samples.clear()

    @property
    def value(self):

        if not self.samples:
            return 0.0

        return sum(self.samples) / len(self.samples)

    def update(self, sample: float) -> float:

        self.samples.append(sample)

        return self.value


class FilterGroup:
    """
    Measurementで使用するフィルタセット

    current
    voltage
    power

    をまとめて管理する。
    """

    def __init__(self):

        self.current = EMAFilter(0.20)

        self.voltage = EMAFilter(0.20)

        self.power = EMAFilter(0.20)

    def reset(self):

        self.current.reset()
        self.voltage.reset()
        self.power.reset()

