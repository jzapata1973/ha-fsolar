"""Fsolar Cloud integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import FsolarApi, FsolarInverter
from .const import CONF_INVERTERS, CONF_RESERVE_SOC_ENTITIES, PLATFORMS
from .coordinator import FsolarCoordinator
from .reserve import BatteryReserveController


@dataclass(slots=True)
class FsolarRuntimeData:
    """Runtime objects shared by Fsolar platforms."""

    coordinator: FsolarCoordinator
    reserve: BatteryReserveController


type FsolarConfigEntry = ConfigEntry[FsolarRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: FsolarConfigEntry) -> bool:
    """Set up Fsolar Cloud from a config entry."""
    api = FsolarApi(
        async_get_clientsession(hass),
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
    )
    inverters = [
        FsolarInverter(
            serial=item["serial"],
            name=item["name"],
            model=item.get("model"),
        )
        for item in entry.data[CONF_INVERTERS]
    ]
    coordinator = FsolarCoordinator(hass, api, inverters)
    await coordinator.async_config_entry_first_refresh()
    entity_registry = er.async_get(hass)
    soc_entities = tuple(
        er.async_resolve_entity_id(entity_registry, entity_id_or_uuid)
        or entity_id_or_uuid
        for entity_id_or_uuid in entry.options.get(CONF_RESERVE_SOC_ENTITIES, [])
    )
    reserve = BatteryReserveController(
        hass,
        entry,
        coordinator,
        soc_entities=soc_entities,
    )
    entry.runtime_data = FsolarRuntimeData(coordinator, reserve)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await reserve.async_start()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: FsolarConfigEntry) -> bool:
    """Unload a config entry."""
    await entry.runtime_data.reserve.async_stop()
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.coordinator.api.async_close_session()
    else:
        await entry.runtime_data.reserve.async_start()
    return unloaded
