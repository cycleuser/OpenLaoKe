"""Adaptive retry temperature.

Cycles temperature on retry attempts to avoid producing the same broken output
repeatedly. Attempt 1: lower, Attempt 2: higher, Attempt 3: back to base.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AdaptiveTemperature:
    base_temp: float = 0.7
    delta: float = 0.15
    min_temp: float = 0.0
    max_temp: float = 1.0
    _enabled: bool = True

    def get_temperature(self, attempt: int, base: float | None = None) -> float:
        if not self._enabled:
            return base or self.base_temp
        bt = base if base is not None else self.base_temp
        cycle_pos = (attempt - 1) % 3
        if cycle_pos == 0:
            temp = bt - self.delta
        elif cycle_pos == 1:
            temp = bt + self.delta
        else:
            temp = bt
        return max(self.min_temp, min(self.max_temp, temp))

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value
