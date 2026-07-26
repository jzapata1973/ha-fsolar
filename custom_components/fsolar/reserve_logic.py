"""Pure battery reserve scheduling and hysteresis logic."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from enum import StrEnum

MINUTES_PER_DAY = 24 * 60


class ReserveOutputMode(StrEnum):
    """Output priorities managed by the battery reserve controller."""

    UTI = "UTI"
    SBU = "SBU"


@dataclass(frozen=True, slots=True)
class ReservePoint:
    """One point on the daily reserve threshold curve."""

    minute: float
    low: float
    high: float


def time_to_minute(value: str | time) -> float:
    """Convert a Home Assistant time selector value to minutes after midnight."""
    parsed = time.fromisoformat(value) if isinstance(value, str) else value
    return parsed.hour * 60 + parsed.minute + parsed.second / 60


def interpolate_thresholds(
    minute: float,
    point_a: ReservePoint,
    point_b: ReservePoint,
) -> tuple[float, float]:
    """Interpolate low/high thresholds across a circular 24-hour curve."""
    span_a_to_b = (point_b.minute - point_a.minute) % MINUTES_PER_DAY
    if span_a_to_b == 0:
        raise ValueError("Reserve points must use different times")

    elapsed_from_a = (minute - point_a.minute) % MINUTES_PER_DAY
    if elapsed_from_a <= span_a_to_b:
        ratio = elapsed_from_a / span_a_to_b
        start, end = point_a, point_b
    else:
        span_b_to_a = MINUTES_PER_DAY - span_a_to_b
        ratio = (elapsed_from_a - span_a_to_b) / span_b_to_a
        start, end = point_b, point_a

    low = start.low + (end.low - start.low) * ratio
    high = start.high + (end.high - start.high) * ratio
    return round(low, 2), round(high, 2)


def desired_output_mode(
    minimum_soc: float,
    low_threshold: float,
    high_threshold: float,
) -> ReserveOutputMode | None:
    """Return the required mode, or None while SOC is inside the hysteresis band."""
    if high_threshold <= low_threshold:
        raise ValueError("High threshold must be greater than low threshold")
    if minimum_soc <= low_threshold:
        return ReserveOutputMode.UTI
    if minimum_soc >= high_threshold:
        return ReserveOutputMode.SBU
    return None
