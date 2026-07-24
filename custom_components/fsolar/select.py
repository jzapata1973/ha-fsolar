"""Select entities for Fsolar Cloud."""

from __future__ import annotations

from typing import ClassVar

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import FsolarConfigEntry
from .api import FsolarCommandError, FsolarInverter
from .const import (
    DOMAIN,
    SOURCE_PRIORITY_BY_VALUE,
    SOURCE_PRIORITY_VALUES,
)
from .coordinator import FsolarCoordinator


async def async_setup_entry(hass, entry: FsolarConfigEntry, async_add_entities):
    """Set up Source Priority Charge entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        FsolarSourcePrioritySelect(coordinator, inverter)
        for inverter in coordinator.inverters
    )


class FsolarSourcePrioritySelect(CoordinatorEntity[FsolarCoordinator], SelectEntity):
    """Control Source Priority Charge for one inverter."""

    _attr_has_entity_name = True
    _attr_translation_key = "source_priority_charge"
    _attr_options: ClassVar[list[str]] = list(SOURCE_PRIORITY_VALUES)

    def __init__(
        self,
        coordinator: FsolarCoordinator,
        inverter: FsolarInverter,
    ) -> None:
        super().__init__(coordinator)
        self._inverter = inverter
        self._attr_unique_id = f"{inverter.serial}_source_priority_charge"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, inverter.serial)},
            name=f"Fsolar Inverter {inverter.serial[-4:]}",
            manufacturer="Felicity Solar",
            model=inverter.model or "Fsolar inverter",
            serial_number=inverter.serial,
        )

    @property
    def current_option(self) -> str | None:
        """Return the current human-readable option."""
        value = self.coordinator.data.get(self._inverter.serial)
        return SOURCE_PRIORITY_BY_VALUE.get(value)

    @property
    def available(self) -> bool:
        """Return whether this specific inverter answered the last poll."""
        return (
            super().available
            and self._inverter.serial not in self.coordinator.failed_serials
        )

    async def async_select_option(self, option: str) -> None:
        """Set and verify Source Priority Charge."""
        value = SOURCE_PRIORITY_VALUES[option]
        try:
            await self.coordinator.api.async_set_source_priority(
                self._inverter.serial, value
            )
        except FsolarCommandError:
            await self.coordinator.async_request_refresh()
            raise
        await self.coordinator.async_request_refresh()
