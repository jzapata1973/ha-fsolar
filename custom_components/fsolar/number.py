"""Number entities for Fsolar Cloud."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import UnitOfElectricCurrent
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import FsolarConfigEntry
from .api import FsolarCommandError, FsolarInverter
from .const import (
    DOMAIN,
    MAX_GRID_CHARGE_CURRENT_MAX,
    MAX_GRID_CHARGE_CURRENT_MIN,
)
from .coordinator import FsolarCoordinator


async def async_setup_entry(hass, entry: FsolarConfigEntry, async_add_entities):
    """Set up maximum grid charge current entities."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        FsolarMaxGridChargeCurrentNumber(coordinator, inverter)
        for inverter in coordinator.inverters
    )


class FsolarMaxGridChargeCurrentNumber(
    CoordinatorEntity[FsolarCoordinator], NumberEntity
):
    """Control maximum grid charge current for one inverter."""

    _attr_has_entity_name = True
    _attr_translation_key = "max_grid_charge_current"
    _attr_native_min_value = MAX_GRID_CHARGE_CURRENT_MIN
    _attr_native_max_value = MAX_GRID_CHARGE_CURRENT_MAX
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        coordinator: FsolarCoordinator,
        inverter: FsolarInverter,
    ) -> None:
        super().__init__(coordinator)
        self._inverter = inverter
        self._attr_unique_id = f"{inverter.serial}_max_grid_charge_current"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, inverter.serial)},
            name=f"Fsolar Inverter {inverter.serial[-4:]}",
            manufacturer="Felicity Solar",
            model=inverter.model or "Fsolar inverter",
            serial_number=inverter.serial,
        )

    @property
    def native_value(self) -> float | None:
        """Return the current setting in amperes."""
        settings = self.coordinator.data.get(self._inverter.serial)
        return settings.max_grid_charge_current if settings else None

    @property
    def available(self) -> bool:
        """Return whether this specific inverter answered the last poll."""
        return (
            super().available
            and self._inverter.serial not in self.coordinator.failed_serials
        )

    async def async_set_native_value(self, value: float) -> None:
        """Set and verify maximum grid charge current."""
        integer_value = int(value)
        if value != integer_value:
            raise ValueError("Maximum grid charge current must be a whole ampere")
        try:
            async with self.coordinator.command_lock:
                await self.coordinator.api.async_set_max_grid_charge_current(
                    self._inverter.serial, integer_value
                )
        except FsolarCommandError:
            await self.coordinator.async_request_refresh()
            raise
        await self.coordinator.async_request_refresh()
