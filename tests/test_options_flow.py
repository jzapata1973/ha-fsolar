"""Tests for the guided battery reserve options flow."""

from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace

try:
    from custom_components.fsolar.config_flow import FsolarOptionsFlow
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
    """Verify both reserve configuration steps and validation."""

    def test_valid_flow_creates_complete_options(self) -> None:
        async def run_flow() -> None:
            flow = _flow()
            first_form = await flow.async_step_init()
            self.assertEqual(first_form["step_id"], "init")

            schedule_form = await flow.async_step_init(
                {
                    CONF_RESERVE_ENABLED: True,
                    CONF_RESERVE_SOC_ENTITIES: [
                        "sensor.battery_one",
                        "sensor.battery_two",
                    ],
                }
            )
            self.assertEqual(schedule_form["step_id"], "schedule")

            result = await flow.async_step_schedule(_schedule())
            self.assertTrue(result["data"][CONF_RESERVE_ENABLED])
            self.assertEqual(
                result["data"][CONF_RESERVE_POINT_A_LOW],
                50,
            )

        asyncio.run(run_flow())

    def test_enabled_control_requires_soc_sensor(self) -> None:
        async def run_flow() -> None:
            flow = _flow()
            result = await flow.async_step_init(
                {
                    CONF_RESERVE_ENABLED: True,
                    CONF_RESERVE_SOC_ENTITIES: [],
                }
            )
            self.assertEqual(result["step_id"], "init")
            self.assertEqual(
                result["errors"][CONF_RESERVE_SOC_ENTITIES],
                "soc_entities_required",
            )

        asyncio.run(run_flow())

    def test_schedule_rejects_equal_times_and_invalid_hysteresis(self) -> None:
        async def run_flow() -> None:
            flow = _flow()
            await flow.async_step_init(
                {
                    CONF_RESERVE_ENABLED: False,
                    CONF_RESERVE_SOC_ENTITIES: [],
                }
            )
            invalid = _schedule()
            invalid[CONF_RESERVE_POINT_B_TIME] = invalid[CONF_RESERVE_POINT_A_TIME]
            invalid[CONF_RESERVE_POINT_A_HIGH] = invalid[CONF_RESERVE_POINT_A_LOW]

            result = await flow.async_step_schedule(invalid)
            self.assertEqual(
                result["errors"]["base"],
                "reserve_times_must_differ",
            )
            self.assertEqual(
                result["errors"][CONF_RESERVE_POINT_A_HIGH],
                "high_must_exceed_low",
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


def _schedule() -> dict:
    return {
        CONF_RESERVE_POINT_A_TIME: "08:00:00",
        CONF_RESERVE_POINT_A_LOW: 50,
        CONF_RESERVE_POINT_A_HIGH: 55,
        CONF_RESERVE_POINT_B_TIME: "18:00:00",
        CONF_RESERVE_POINT_B_LOW: 50,
        CONF_RESERVE_POINT_B_HIGH: 55,
    }
