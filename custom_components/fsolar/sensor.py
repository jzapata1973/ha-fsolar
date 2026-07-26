"""Sensor entities for Fsolar Cloud."""

from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE
from homeassistant.helpers.entity import EntityCategory

from . import FsolarConfigEntry
from .reserve import ReserveActiveMode, ReserveStatus
from .reserve_entity import FsolarReserveEntity, async_add_reserve_entities


async def async_setup_entry(hass, entry: FsolarConfigEntry, async_add_entities):
    """Set up battery reserve diagnostic sensors."""
    async_add_reserve_entities(
        async_add_entities,
        [
            FsolarReserveMinimumSocSensor(entry),
            FsolarReserveLowThresholdSensor(entry),
            FsolarReserveHighThresholdSensor(entry),
            FsolarReserveOutputModeSensor(entry),
            FsolarReserveStatusSensor(entry),
            FsolarReserveLastChangeSensor(entry),
        ],
    )


class FsolarReservePercentageSensor(FsolarReserveEntity, SensorEntity):
    """Base percentage sensor for reserve state."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_suggested_display_precision = 1


class FsolarReserveMinimumSocSensor(FsolarReservePercentageSensor):
    """Expose the lowest configured battery SOC."""

    _attr_translation_key = "battery_reserve_minimum_soc"
    _attr_device_class = SensorDeviceClass.BATTERY

    def __init__(self, entry: FsolarConfigEntry) -> None:
        super().__init__(entry, "minimum_soc")

    @property
    def native_value(self) -> float | None:
        """Return the minimum valid SOC."""
        return self.controller.minimum_soc


class FsolarReserveLowThresholdSensor(FsolarReservePercentageSensor):
    """Expose the currently interpolated low reserve threshold."""

    _attr_translation_key = "battery_reserve_low_threshold"

    def __init__(self, entry: FsolarConfigEntry) -> None:
        super().__init__(entry, "low_threshold")

    @property
    def native_value(self) -> float | None:
        """Return the current lower threshold."""
        return self.controller.low_threshold


class FsolarReserveHighThresholdSensor(FsolarReservePercentageSensor):
    """Expose the currently interpolated high reserve threshold."""

    _attr_translation_key = "battery_reserve_high_threshold"

    def __init__(self, entry: FsolarConfigEntry) -> None:
        super().__init__(entry, "high_threshold")

    @property
    def native_value(self) -> float | None:
        """Return the current upper threshold."""
        return self.controller.high_threshold


class FsolarReserveOutputModeSensor(FsolarReserveEntity, SensorEntity):
    """Expose consensus output priority across all managed inverters."""

    _attr_translation_key = "battery_reserve_output_mode"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_options: ClassVar[list[str]] = [mode.value for mode in ReserveActiveMode]

    def __init__(self, entry: FsolarConfigEntry) -> None:
        super().__init__(entry, "output_mode")

    @property
    def native_value(self) -> str:
        """Return consensus priority or a mixed/unknown diagnostic state."""
        return self.controller.active_mode.value


class FsolarReserveStatusSensor(FsolarReserveEntity, SensorEntity):
    """Expose the reserve controller state and troubleshooting details."""

    _attr_translation_key = "battery_reserve_status"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_options: ClassVar[list[str]] = [status.value for status in ReserveStatus]

    def __init__(self, entry: FsolarConfigEntry) -> None:
        super().__init__(entry, "status")

    @property
    def native_value(self) -> str:
        """Return controller status."""
        return self.controller.status.value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return concise controller diagnostics."""
        return self.controller.diagnostic_attributes


class FsolarReserveLastChangeSensor(FsolarReserveEntity, SensorEntity):
    """Expose when the controller last changed at least one inverter."""

    _attr_translation_key = "battery_reserve_last_change"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry: FsolarConfigEntry) -> None:
        super().__init__(entry, "last_change")

    @property
    def native_value(self) -> datetime | None:
        """Return the last controller-initiated change time."""
        return self.controller.last_change
