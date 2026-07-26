"""Tests for battery reserve scheduling and hysteresis."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

COMPONENT_PATH = Path(__file__).parents[1] / "custom_components" / "fsolar"
sys.path.insert(0, str(COMPONENT_PATH))

from reserve_logic import (  # noqa: E402
    ReserveOutputMode,
    ReservePoint,
    desired_output_mode,
    interpolate_thresholds,
    time_to_minute,
)


class ReserveLogicTests(unittest.TestCase):
    """Verify the pure reserve curve logic."""

    def test_time_to_minute_accepts_home_assistant_time(self) -> None:
        self.assertEqual(time_to_minute("08:30:00"), 510)

    def test_flat_curve_remains_constant_all_day(self) -> None:
        point_a = ReservePoint(8 * 60, 50, 55)
        point_b = ReservePoint(18 * 60, 50, 55)

        for minute in (0, 8 * 60, 12 * 60, 18 * 60, 23 * 60 + 59):
            self.assertEqual(
                interpolate_thresholds(minute, point_a, point_b),
                (50, 55),
            )

    def test_curve_interpolates_between_a_and_b(self) -> None:
        point_a = ReservePoint(8 * 60, 40, 50)
        point_b = ReservePoint(18 * 60, 60, 70)

        self.assertEqual(
            interpolate_thresholds(13 * 60, point_a, point_b),
            (50, 60),
        )

    def test_curve_interpolates_across_midnight(self) -> None:
        point_a = ReservePoint(18 * 60, 60, 70)
        point_b = ReservePoint(6 * 60, 40, 50)

        self.assertEqual(
            interpolate_thresholds(0, point_a, point_b),
            (50, 60),
        )
        self.assertEqual(
            interpolate_thresholds(12 * 60, point_a, point_b),
            (50, 60),
        )

    def test_equal_point_times_are_rejected(self) -> None:
        point_a = ReservePoint(8 * 60, 50, 55)
        point_b = ReservePoint(8 * 60, 50, 55)

        with self.assertRaises(ValueError):
            interpolate_thresholds(12 * 60, point_a, point_b)

    def test_hysteresis_selects_expected_mode(self) -> None:
        self.assertEqual(
            desired_output_mode(49, 50, 55),
            ReserveOutputMode.UTI,
        )
        self.assertEqual(
            desired_output_mode(50, 50, 55),
            ReserveOutputMode.UTI,
        )
        self.assertIsNone(desired_output_mode(52, 50, 55))
        self.assertEqual(
            desired_output_mode(55, 50, 55),
            ReserveOutputMode.SBU,
        )
        self.assertEqual(
            desired_output_mode(80, 50, 55),
            ReserveOutputMode.SBU,
        )

    def test_invalid_hysteresis_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            desired_output_mode(50, 55, 55)


if __name__ == "__main__":
    unittest.main()
