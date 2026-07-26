"""Binary sensor entities for Fsolar Cloud."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.entity import EntityCategory

from . import FsolarConfigEntry
from .reserve_entity import FsolarReserveEntity, async_add_reserve_entities


async def async_setup_entry(hass, entry: FsolarConfigEntry, async_add_entities):
    """Set up battery reserve binary sensors."""
    async_add_reserve_entities(
        async_add_entities,
        [FsolarReserveEnabledBinarySensor(entry)],
    )


class FsolarReserveEnabledBinarySensor(
    FsolarReserveEntity,
    BinarySensorEntity,
):
    """Report whether automatic reserve control is enabled."""

    _attr_translation_key = "battery_reserve_enabled"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry: FsolarConfigEntry) -> None:
        super().__init__(entry, "enabled")

    @property
    def is_on(self) -> bool:
        """Return whether reserve control is enabled."""
        return self.controller.enabled
