"""Behavior tests for the Home Assistant battery reserve controller."""

from __future__ import annotations

import asyncio
import unittest
from types import SimpleNamespace

try:
    from custom_components.fsolar.api import FsolarInverter, FsolarSettings
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
    from custom_components.fsolar.reserve import (
        BatteryReserveController,
        ReserveStatus,
    )
except ModuleNotFoundError:
    HOME_ASSISTANT_AVAILABLE = False
else:
    HOME_ASSISTANT_AVAILABLE = True


@unittest.skipUnless(
    HOME_ASSISTANT_AVAILABLE,
    "Home Assistant runtime is required",
)
class ReserveControllerTests(unittest.TestCase):
    """Verify safe SOC handling and per-inverter output commands."""

    def test_lowest_soc_changes_every_inverter_to_utility_first(self) -> None:
        controller, api = self._controller(
            soc_values={"sensor.one": "60", "sensor.two": "49", "sensor.three": "70"},
            output_priorities=(2, 2, 2),
        )

        asyncio.run(controller.async_evaluate("test"))

        self.assertEqual(sorted(api.commands), [("one", 0), ("three", 0), ("two", 0)])
        self.assertEqual(controller.minimum_soc, 49)
        self.assertEqual(controller.status, ReserveStatus.UTILITY_FIRST)

    def test_unavailable_soc_blocks_all_commands(self) -> None:
        controller, api = self._controller(
            soc_values={
                "sensor.one": "60",
                "sensor.two": "unavailable",
                "sensor.three": "70",
            },
            output_priorities=(2, 2, 2),
        )

        asyncio.run(controller.async_evaluate("test"))

        self.assertEqual(api.commands, [])
        self.assertIsNone(controller.minimum_soc)
        self.assertEqual(controller.status, ReserveStatus.WAITING_FOR_SOC)

    def test_high_soc_changes_every_inverter_to_battery_first(self) -> None:
        controller, api = self._controller(
            soc_values={"sensor.one": "55", "sensor.two": "80", "sensor.three": "70"},
            output_priorities=(0, 0, 0),
        )

        asyncio.run(controller.async_evaluate("test"))

        self.assertEqual(sorted(api.commands), [("one", 2), ("three", 2), ("two", 2)])
        self.assertEqual(controller.status, ReserveStatus.BATTERY_FIRST)

    def test_only_mismatched_inverter_receives_a_command(self) -> None:
        controller, api = self._controller(
            soc_values={"sensor.one": "40", "sensor.two": "45", "sensor.three": "49"},
            output_priorities=(0, 2, 0),
        )

        asyncio.run(controller.async_evaluate("test"))

        self.assertEqual(api.commands, [("two", 0)])

    def _controller(
        self,
        *,
        soc_values: dict[str, str],
        output_priorities: tuple[int, int, int],
    ):
        inverters = [
            FsolarInverter("one", "One"),
            FsolarInverter("two", "Two"),
            FsolarInverter("three", "Three"),
        ]
        coordinator = _FakeCoordinator(inverters, output_priorities)
        hass = SimpleNamespace(states=_FakeStates(soc_values))
        entry = SimpleNamespace(
            options={
                CONF_RESERVE_ENABLED: True,
                CONF_RESERVE_SOC_ENTITIES: list(soc_values),
                CONF_RESERVE_POINT_A_TIME: "08:00:00",
                CONF_RESERVE_POINT_A_LOW: 50,
                CONF_RESERVE_POINT_A_HIGH: 55,
                CONF_RESERVE_POINT_B_TIME: "18:00:00",
                CONF_RESERVE_POINT_B_LOW: 50,
                CONF_RESERVE_POINT_B_HIGH: 55,
            }
        )
        controller = BatteryReserveController(hass, entry, coordinator)
        return controller, coordinator.api


class _FakeStates:
    def __init__(self, values: dict[str, str]) -> None:
        self._values = values

    def get(self, entity_id: str):
        value = self._values.get(entity_id)
        return None if value is None else SimpleNamespace(state=value)


class _FakeApi:
    def __init__(self, coordinator) -> None:
        self.coordinator = coordinator
        self.commands: list[tuple[str, int]] = []

    async def async_set_output_source_priority(self, serial: str, value: int) -> None:
        self.commands.append((serial, value))
        previous = self.coordinator.data[serial]
        self.coordinator.data[serial] = FsolarSettings(
            previous.source_priority,
            value,
            previous.max_grid_charge_current,
        )


class _FakeCoordinator:
    def __init__(
        self,
        inverters,
        output_priorities: tuple[int, int, int],
    ) -> None:
        self.inverters = inverters
        self.data = {
            inverter.serial: FsolarSettings(1, priority, 20)
            for inverter, priority in zip(
                inverters,
                output_priorities,
                strict=True,
            )
        }
        self.failed_serials: set[str] = set()
        self.command_lock = asyncio.Lock()
        self.api = _FakeApi(self)

    async def async_refresh(self) -> None:
        return
