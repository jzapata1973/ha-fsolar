"""Data coordinator for Fsolar Cloud."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import FsolarApi, FsolarInverter, FsolarSettings
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class FsolarCoordinator(DataUpdateCoordinator[dict[str, FsolarSettings]]):
    """Poll supported settings for all configured inverters."""

    def __init__(
        self,
        hass,
        api: FsolarApi,
        inverters: list[FsolarInverter],
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.api = api
        self.inverters = inverters
        self.failed_serials: set[str] = set()
        self.command_lock = asyncio.Lock()

    async def _async_update_data(self) -> dict[str, FsolarSettings]:
        results = await asyncio.gather(
            *(
                self.api.async_get_settings(inverter.serial)
                for inverter in self.inverters
            ),
            return_exceptions=True,
        )
        data = dict(self.data or {})
        errors: list[str] = []
        successful = 0
        failed_serials: set[str] = set()
        for inverter, result in zip(self.inverters, results, strict=True):
            if isinstance(result, BaseException):
                errors.append(f"{inverter.serial[-4:]}: {result}")
                failed_serials.add(inverter.serial)
                continue
            data[inverter.serial] = result
            successful += 1
        self.failed_serials = failed_serials
        if not successful:
            raise UpdateFailed("; ".join(errors) or "No inverter responded")
        if errors:
            _LOGGER.warning("Partial Fsolar update: %s", "; ".join(errors))
        return data
