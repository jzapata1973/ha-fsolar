"""Base entity for the Fsolar battery reserve controller."""

from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FsolarConfigEntry
from .const import DOMAIN
from .reserve import BatteryReserveController


class FsolarReserveEntity(Entity):
    """Entity backed by in-memory battery reserve controller state."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        entry: FsolarConfigEntry,
        key: str,
    ) -> None:
        self.controller: BatteryReserveController = entry.runtime_data.reserve
        self._attr_unique_id = f"{entry.entry_id}_battery_reserve_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry.entry_id}_battery_reserve")},
            name="Fsolar Battery Reserve",
            manufacturer="Felicity Solar",
            model="Cloud reserve controller",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to controller updates."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.controller.async_add_listener(self._async_controller_updated)
        )

    @callback
    def _async_controller_updated(self) -> None:
        self.async_write_ha_state()


def async_add_reserve_entities(
    async_add_entities: AddConfigEntryEntitiesCallback,
    entities: list[FsolarReserveEntity],
) -> None:
    """Add reserve entities without requesting an extra poll."""
    async_add_entities(entities)
