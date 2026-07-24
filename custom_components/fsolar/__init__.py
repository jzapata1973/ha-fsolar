"""Fsolar Cloud integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import FsolarApi, FsolarInverter
from .const import CONF_INVERTERS, PLATFORMS
from .coordinator import FsolarCoordinator

type FsolarConfigEntry = ConfigEntry[FsolarCoordinator]


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
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: FsolarConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.api.async_close_session()
    return unloaded
