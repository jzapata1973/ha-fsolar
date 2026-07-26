"""SolarAssistant-style battery reserve controller."""

from __future__ import annotations

import asyncio
import logging
import math
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.util import dt as dt_util

from .const import (
    CONF_RESERVE_ENABLED,
    CONF_RESERVE_POINT_A_HIGH,
    CONF_RESERVE_POINT_A_LOW,
    CONF_RESERVE_POINT_A_TIME,
    CONF_RESERVE_POINT_B_HIGH,
    CONF_RESERVE_POINT_B_LOW,
    CONF_RESERVE_POINT_B_TIME,
    CONF_RESERVE_SOC_ENTITIES,
    DEFAULT_RESERVE_ENABLED,
    DEFAULT_RESERVE_POINT_A_HIGH,
    DEFAULT_RESERVE_POINT_A_LOW,
    DEFAULT_RESERVE_POINT_A_TIME,
    DEFAULT_RESERVE_POINT_B_HIGH,
    DEFAULT_RESERVE_POINT_B_LOW,
    DEFAULT_RESERVE_POINT_B_TIME,
    OUTPUT_SOURCE_PRIORITY_BY_VALUE,
    OUTPUT_SOURCE_PRIORITY_VALUES,
    RESERVE_EVALUATION_INTERVAL,
    RESERVE_RETRY_INTERVAL,
)
from .coordinator import FsolarCoordinator
from .reserve_logic import (
    ReserveOutputMode,
    ReservePoint,
    desired_output_mode,
    interpolate_thresholds,
    time_to_minute,
)

_LOGGER = logging.getLogger(__name__)


class ReserveStatus(StrEnum):
    """Runtime states exposed by the reserve status sensor."""

    DISABLED = "disabled"
    WAITING_FOR_SOC = "waiting_for_soc"
    STANDBY = "standby"
    APPLYING = "applying"
    UTILITY_FIRST = "utility_first"
    BATTERY_FIRST = "battery_first"
    ERROR = "error"


class ReserveActiveMode(StrEnum):
    """Consensus output priority across configured inverters."""

    UTI = "UTI"
    SUB = "SUB"
    SBU = "SBU"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class BatteryReserveController:
    """Maintain a configurable battery reserve through output source priority."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        coordinator: FsolarCoordinator,
        *,
        soc_entities: tuple[str, ...] | None = None,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.coordinator = coordinator
        self.enabled = bool(
            entry.options.get(CONF_RESERVE_ENABLED, DEFAULT_RESERVE_ENABLED)
        )
        self.soc_entities = soc_entities or tuple(
            entry.options.get(CONF_RESERVE_SOC_ENTITIES, [])
        )
        self.minimum_soc: float | None = None
        self.low_threshold: float | None = None
        self.high_threshold: float | None = None
        self.status = (
            ReserveStatus.WAITING_FOR_SOC if self.enabled else ReserveStatus.DISABLED
        )
        self.active_mode = ReserveActiveMode.UNKNOWN
        self.last_commanded_mode: ReserveOutputMode | None = None
        self.last_change: datetime | None = None
        self.last_attempt: datetime | None = None
        self.last_attempt_mode: ReserveOutputMode | None = None
        self.last_error: str | None = None
        self.invalid_soc_entities: tuple[str, ...] = ()
        self.failed_inverters: tuple[str, ...] = ()
        self.last_trigger: str | None = None
        self._listeners: set[Callable[[], None]] = set()
        self._unsubscribers: list[Callable[[], None]] = []
        self._evaluation_lock = asyncio.Lock()
        self._stopped = False

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Subscribe an entity to runtime state changes."""
        self._listeners.add(listener)

        @callback
        def remove_listener() -> None:
            self._listeners.discard(listener)

        return remove_listener

    @callback
    def _async_notify_listeners(self) -> None:
        for listener in tuple(self._listeners):
            listener()

    async def async_start(self) -> None:
        """Start state/time listeners and perform the first evaluation."""
        self._stopped = False
        self._async_update_thresholds()
        self._unsubscribers.append(
            self.coordinator.async_add_listener(self._async_coordinator_updated)
        )
        self._unsubscribers.append(
            async_track_time_interval(
                self.hass,
                self._async_interval_elapsed,
                timedelta(seconds=RESERVE_EVALUATION_INTERVAL),
                name="Fsolar battery reserve",
                cancel_on_shutdown=True,
            )
        )
        if not self.enabled:
            self._async_update_active_mode()
            self._async_notify_listeners()
            return

        self._unsubscribers.append(
            async_track_state_change_event(
                self.hass,
                self.soc_entities,
                self._async_soc_changed,
            )
        )
        await self.async_evaluate("startup")

    async def async_stop(self) -> None:
        """Stop all callbacks and prevent further commands."""
        self._stopped = True
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._unsubscribers.clear()
        async with self._evaluation_lock:
            pass

    async def _async_soc_changed(self, _event: Event[EventStateChangedData]) -> None:
        await self.async_evaluate("soc_change")

    async def _async_interval_elapsed(self, _now: datetime) -> None:
        if not self.enabled:
            if self._stopped:
                return
            self._async_update_thresholds()
            self._async_update_active_mode()
            self._async_notify_listeners()
            return
        await self.async_evaluate("interval")

    @callback
    def _async_coordinator_updated(self) -> None:
        self._async_update_active_mode()
        self._async_notify_listeners()

    async def async_evaluate(self, trigger: str) -> None:
        """Evaluate the reserve curve and apply a priority when required."""
        async with self._evaluation_lock:
            if self._stopped or not self.enabled:
                return

            self.last_trigger = trigger
            self._async_update_thresholds()
            self._async_update_active_mode()
            soc_values, invalid_entities = self._read_soc_values()
            self.invalid_soc_entities = tuple(invalid_entities)

            if invalid_entities or not soc_values:
                self.minimum_soc = None
                self.status = ReserveStatus.WAITING_FOR_SOC
                self.last_error = "Unavailable or invalid SOC entities: " + ", ".join(
                    invalid_entities or self.soc_entities
                )
                self._async_notify_listeners()
                return

            self.minimum_soc = min(soc_values)
            self.last_error = None
            desired_mode = desired_output_mode(
                self.minimum_soc,
                self.low_threshold,
                self.high_threshold,
            )
            if desired_mode is None:
                self.status = ReserveStatus.STANDBY
                self.failed_inverters = ()
                self._async_notify_listeners()
                return

            desired_value = OUTPUT_SOURCE_PRIORITY_VALUES[desired_mode.value]
            targets = [
                inverter
                for inverter in self.coordinator.inverters
                if inverter.serial in self.coordinator.failed_serials
                or (settings := self.coordinator.data.get(inverter.serial)) is None
                or settings.output_source_priority != desired_value
            ]
            if not targets:
                self.status = self._status_for_mode(desired_mode)
                self.last_commanded_mode = desired_mode
                self.failed_inverters = ()
                self._async_notify_listeners()
                return

            now = datetime.now(UTC)
            if (
                self.last_attempt_mode == desired_mode
                and self.last_attempt is not None
                and (now - self.last_attempt).total_seconds() < RESERVE_RETRY_INTERVAL
            ):
                self._async_notify_listeners()
                return

            self.status = ReserveStatus.APPLYING
            self.last_attempt = now
            self.last_attempt_mode = desired_mode
            self._async_notify_listeners()

            async with self.coordinator.command_lock:
                results = await asyncio.gather(
                    *(
                        self.coordinator.api.async_set_output_source_priority(
                            inverter.serial, desired_value
                        )
                        for inverter in targets
                    ),
                    return_exceptions=True,
                )

            failures = [
                (inverter, result)
                for inverter, result in zip(targets, results, strict=True)
                if isinstance(result, BaseException)
            ]
            successes = len(targets) - len(failures)
            if successes:
                self.last_change = datetime.now(UTC)
                self.last_commanded_mode = desired_mode

            await self.coordinator.async_refresh()
            self._async_update_active_mode()

            if failures:
                self.failed_inverters = tuple(
                    inverter.serial[-4:] for inverter, _result in failures
                )
                self.last_error = "; ".join(
                    f"{inverter.serial[-4:]}: {result}" for inverter, result in failures
                )
                self.status = ReserveStatus.ERROR
                _LOGGER.error(
                    "Battery reserve could not apply %s to all inverters: %s",
                    desired_mode,
                    self.last_error,
                )
            else:
                self.failed_inverters = ()
                self.last_error = None
                self.status = self._status_for_mode(desired_mode)
            self._async_notify_listeners()

    def _read_soc_values(self) -> tuple[list[float], list[str]]:
        values: list[float] = []
        invalid: list[str] = []
        for entity_id in self.soc_entities:
            state = self.hass.states.get(entity_id)
            if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                invalid.append(entity_id)
                continue
            try:
                value = float(state.state)
            except (TypeError, ValueError):
                invalid.append(entity_id)
                continue
            if not math.isfinite(value) or not 0 <= value <= 100:
                invalid.append(entity_id)
                continue
            values.append(value)
        return values, invalid

    def _async_update_thresholds(self) -> None:
        now = dt_util.now()
        minute = now.hour * 60 + now.minute + now.second / 60
        point_a = ReservePoint(
            time_to_minute(
                self.entry.options.get(
                    CONF_RESERVE_POINT_A_TIME,
                    DEFAULT_RESERVE_POINT_A_TIME,
                )
            ),
            float(
                self.entry.options.get(
                    CONF_RESERVE_POINT_A_LOW,
                    DEFAULT_RESERVE_POINT_A_LOW,
                )
            ),
            float(
                self.entry.options.get(
                    CONF_RESERVE_POINT_A_HIGH,
                    DEFAULT_RESERVE_POINT_A_HIGH,
                )
            ),
        )
        point_b = ReservePoint(
            time_to_minute(
                self.entry.options.get(
                    CONF_RESERVE_POINT_B_TIME,
                    DEFAULT_RESERVE_POINT_B_TIME,
                )
            ),
            float(
                self.entry.options.get(
                    CONF_RESERVE_POINT_B_LOW,
                    DEFAULT_RESERVE_POINT_B_LOW,
                )
            ),
            float(
                self.entry.options.get(
                    CONF_RESERVE_POINT_B_HIGH,
                    DEFAULT_RESERVE_POINT_B_HIGH,
                )
            ),
        )
        self.low_threshold, self.high_threshold = interpolate_thresholds(
            minute, point_a, point_b
        )

    @callback
    def _async_update_active_mode(self) -> None:
        if self.coordinator.failed_serials:
            self.active_mode = ReserveActiveMode.UNKNOWN
            return
        values = [
            settings.output_source_priority
            for inverter in self.coordinator.inverters
            if (settings := self.coordinator.data.get(inverter.serial)) is not None
        ]
        if len(values) != len(self.coordinator.inverters):
            self.active_mode = ReserveActiveMode.UNKNOWN
            return
        if len(set(values)) != 1:
            self.active_mode = ReserveActiveMode.MIXED
            return
        mode = OUTPUT_SOURCE_PRIORITY_BY_VALUE.get(values[0])
        self.active_mode = (
            ReserveActiveMode(mode) if mode is not None else ReserveActiveMode.UNKNOWN
        )

    @staticmethod
    def _status_for_mode(mode: ReserveOutputMode) -> ReserveStatus:
        return (
            ReserveStatus.UTILITY_FIRST
            if mode == ReserveOutputMode.UTI
            else ReserveStatus.BATTERY_FIRST
        )

    @property
    def diagnostic_attributes(self) -> dict[str, Any]:
        """Return useful non-sensitive details for the status sensor."""
        return {
            "soc_entities": list(self.soc_entities),
            "invalid_soc_entities": list(self.invalid_soc_entities),
            "failed_inverters": list(self.failed_inverters),
            "last_commanded_mode": self.last_commanded_mode,
            "last_trigger": self.last_trigger,
            "last_error": self.last_error,
        }
