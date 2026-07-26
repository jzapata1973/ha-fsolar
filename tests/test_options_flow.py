"""Tests for the guided battery reserve options flow."""

from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace

try:
    from custom_components.fsolar.config_flow import (
        SECTION_POINT_A,
        SECTION_POINT_B,
        FsolarOptionsFlow,
    )
    from custom_components.fsolar.const import (
        CONF_RESERVE_ENABLED,
        CONF_RESERVE_POINT_A_HIGH,
        CONF_RESERVE_POINT_A_LOW,
        CONF_RESERVE_POINT_A_TIME,
        CONF_RESERVE_POINT_B_HIGH,
        CONF_RESERVE_POINT_B_LOW,
        CONF_RESERVE_POINT_B_TIME,
        CONF_RESERVE_SOC_ENTITIES,
    )
except ModuleNotFoundError:
    HOME_ASSISTANT_AVAILABLE = False
else:
    HOME_ASSISTANT_AVAILABLE = True


@unittest.skipUnless(
    HOME_ASSISTANT_AVAILABLE,
    "Home Assistant runtime is required",
)
class OptionsFlowTests(unittest.TestCase):
    """Verify the single-screen reserve configuration and validation."""

    def test_form_exposes_both_reserve_points(self) -> None:
        async def run_flow() -> None:
            flow = _flow()
            form = await flow.async_step_init()
            self.assertEqual(form["step_id"], "init")
            self.assertIn(SECTION_POINT_A, form["data_schema"].schema)
            self.assertIn(SECTION_POINT_B, form["data_schema"].schema)

        asyncio.run(run_flow())

    def test_valid_flow_creates_complete_flat_options(self) -> None:
        async def run_flow() -> None:
            flow = _flow()
            result = await flow.async_step_init(_options_input(enabled=True))
            self.assertTrue(result["data"][CONF_RESERVE_ENABLED])
            self.assertNotIn(SECTION_POINT_A, result["data"])
            self.assertNotIn(SECTION_POINT_B, result["data"])
            self.assertEqual(
                result["data"][CONF_RESERVE_POINT_A_LOW],
                50,
            )

        asyncio.run(run_flow())

    def test_enabled_control_requires_soc_sensor(self) -> None:
        async def run_flow() -> None:
            flow = _flow()
            user_input = _options_input(enabled=True)
            user_input[CONF_RESERVE_SOC_ENTITIES] = []
            result = await flow.async_step_init(user_input)
            self.assertEqual(result["step_id"], "init")
            self.assertEqual(
                result["errors"][CONF_RESERVE_SOC_ENTITIES],
                "soc_entities_required",
            )

        asyncio.run(run_flow())

    def test_form_rejects_equal_times(self) -> None:
        async def run_flow() -> None:
            flow = _flow()
            invalid = _options_input()
            invalid[SECTION_POINT_B][CONF_RESERVE_POINT_B_TIME] = invalid[
                SECTION_POINT_A
            ][CONF_RESERVE_POINT_A_TIME]

            result = await flow.async_step_init(invalid)
            self.assertEqual(
                result["errors"]["base"],
                "reserve_times_must_differ",
            )

        asyncio.run(run_flow())

    def test_form_identifies_invalid_point_a_hysteresis(self) -> None:
        async def run_flow() -> None:
            flow = _flow()
            invalid = _options_input()
            invalid[SECTION_POINT_A][CONF_RESERVE_POINT_A_HIGH] = invalid[
                SECTION_POINT_A
            ][CONF_RESERVE_POINT_A_LOW]

            result = await flow.async_step_init(invalid)
            self.assertEqual(
                result["errors"]["base"],
                "point_a_high_must_exceed_low",
            )

        asyncio.run(run_flow())


def _flow():
    entry = SimpleNamespace(options={})
    hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_get_known_entry=lambda _entry_id: entry)
    )
    flow = FsolarOptionsFlow()
    flow.hass = hass
    flow.handler = "test-entry"
    return flow


def _options_input(*, enabled: bool = False) -> dict:
    return {
        CONF_RESERVE_ENABLED: enabled,
        CONF_RESERVE_SOC_ENTITIES: [
            "sensor.battery_one",
            "sensor.battery_two",
        ],
        SECTION_POINT_A: {
            CONF_RESERVE_POINT_A_TIME: "08:00:00",
            CONF_RESERVE_POINT_A_LOW: 50,
            CONF_RESERVE_POINT_A_HIGH: 55,
        },
        SECTION_POINT_B: {
            CONF_RESERVE_POINT_B_TIME: "18:00:00",
            CONF_RESERVE_POINT_B_LOW: 50,
            CONF_RESERVE_POINT_B_HIGH: 55,
        },
    }
