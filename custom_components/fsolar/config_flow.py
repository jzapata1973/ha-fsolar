"""Config flow for Fsolar Cloud."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, PERCENTAGE
from homeassistant.core import callback
from homeassistant.data_entry_flow import SectionConfig, section
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TimeSelector,
)

from .api import (
    FsolarApi,
    FsolarAuthenticationError,
    FsolarError,
)
from .const import (
    CONF_INVERTERS,
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
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

SECTION_POINT_A = "point_a"
SECTION_POINT_B = "point_b"


class FsolarConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an Fsolar Cloud config flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the battery reserve options flow."""
        return FsolarOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Collect and validate Fsolar account credentials."""
        errors: dict[str, str] = {}
        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            await self.async_set_unique_id(username.lower())
            self._abort_if_unique_id_configured()

            api = FsolarApi(
                async_get_clientsession(self.hass),
                username,
                user_input[CONF_PASSWORD],
            )
            try:
                await api.async_login()
                inverters = await api.async_list_inverters()
            except FsolarAuthenticationError as err:
                _LOGGER.warning("Fsolar authentication failed: %s", err)
                errors["base"] = "invalid_auth"
            except FsolarError as err:
                _LOGGER.warning("Unable to connect to Fsolar: %s", err)
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected error while configuring Fsolar")
                errors["base"] = "unknown"
            else:
                if not inverters:
                    errors["base"] = "no_inverters"
                else:
                    return self.async_create_entry(
                        title=f"Fsolar ({username})",
                        data={
                            CONF_USERNAME: username,
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                            CONF_INVERTERS: [
                                {
                                    "serial": inverter.serial,
                                    "name": inverter.name,
                                    "model": inverter.model,
                                }
                                for inverter in inverters
                            ],
                        },
                    )

        schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )


class FsolarOptionsFlow(config_entries.OptionsFlowWithReload):
    """Configure the SolarAssistant-style battery reserve controller."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Configure reserve control, SOC sources, and the daily reserve curve."""
        errors: dict[str, str] = {}
        if user_input is not None:
            point_a = user_input[SECTION_POINT_A]
            point_b = user_input[SECTION_POINT_B]
            options = {
                CONF_RESERVE_ENABLED: user_input[CONF_RESERVE_ENABLED],
                CONF_RESERVE_SOC_ENTITIES: user_input[CONF_RESERVE_SOC_ENTITIES],
                **point_a,
                **point_b,
            }
            if (
                options[CONF_RESERVE_ENABLED]
                and not options[CONF_RESERVE_SOC_ENTITIES]
            ):
                errors[CONF_RESERVE_SOC_ENTITIES] = "soc_entities_required"
            elif (
                options[CONF_RESERVE_POINT_A_TIME]
                == options[CONF_RESERVE_POINT_B_TIME]
            ):
                errors["base"] = "reserve_times_must_differ"
            elif (
                options[CONF_RESERVE_POINT_A_HIGH]
                <= options[CONF_RESERVE_POINT_A_LOW]
            ):
                errors["base"] = "point_a_high_must_exceed_low"
            elif (
                options[CONF_RESERVE_POINT_B_HIGH]
                <= options[CONF_RESERVE_POINT_B_LOW]
            ):
                errors["base"] = "point_b_high_must_exceed_low"
            else:
                return self.async_create_entry(title="", data=options)

        current = _reserve_options(self.config_entry.options)
        percentage_selector = NumberSelector(
            NumberSelectorConfig(
                min=0,
                max=100,
                step=1,
                unit_of_measurement=PERCENTAGE,
                mode=NumberSelectorMode.BOX,
            )
        )
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_RESERVE_ENABLED,
                    default=DEFAULT_RESERVE_ENABLED,
                ): BooleanSelector(),
                vol.Required(
                    CONF_RESERVE_SOC_ENTITIES,
                    default=[],
                ): EntitySelector(
                    EntitySelectorConfig(
                        filter={"domain": "sensor"},
                        multiple=True,
                        reorder=True,
                    )
                ),
                vol.Required(SECTION_POINT_A): section(
                    vol.Schema(
                        {
                            vol.Required(
                                CONF_RESERVE_POINT_A_TIME,
                                default=DEFAULT_RESERVE_POINT_A_TIME,
                            ): TimeSelector(),
                            vol.Required(
                                CONF_RESERVE_POINT_A_LOW,
                                default=DEFAULT_RESERVE_POINT_A_LOW,
                            ): percentage_selector,
                            vol.Required(
                                CONF_RESERVE_POINT_A_HIGH,
                                default=DEFAULT_RESERVE_POINT_A_HIGH,
                            ): percentage_selector,
                        }
                    ),
                    SectionConfig(collapsed=False),
                ),
                vol.Required(SECTION_POINT_B): section(
                    vol.Schema(
                        {
                            vol.Required(
                                CONF_RESERVE_POINT_B_TIME,
                                default=DEFAULT_RESERVE_POINT_B_TIME,
                            ): TimeSelector(),
                            vol.Required(
                                CONF_RESERVE_POINT_B_LOW,
                                default=DEFAULT_RESERVE_POINT_B_LOW,
                            ): percentage_selector,
                            vol.Required(
                                CONF_RESERVE_POINT_B_HIGH,
                                default=DEFAULT_RESERVE_POINT_B_HIGH,
                            ): percentage_selector,
                        }
                    ),
                    SectionConfig(collapsed=False),
                ),
            }
        )
        suggested = {
            CONF_RESERVE_ENABLED: current[CONF_RESERVE_ENABLED],
            CONF_RESERVE_SOC_ENTITIES: current[CONF_RESERVE_SOC_ENTITIES],
            SECTION_POINT_A: {
                CONF_RESERVE_POINT_A_TIME: current[CONF_RESERVE_POINT_A_TIME],
                CONF_RESERVE_POINT_A_LOW: current[CONF_RESERVE_POINT_A_LOW],
                CONF_RESERVE_POINT_A_HIGH: current[CONF_RESERVE_POINT_A_HIGH],
            },
            SECTION_POINT_B: {
                CONF_RESERVE_POINT_B_TIME: current[CONF_RESERVE_POINT_B_TIME],
                CONF_RESERVE_POINT_B_LOW: current[CONF_RESERVE_POINT_B_LOW],
                CONF_RESERVE_POINT_B_HIGH: current[CONF_RESERVE_POINT_B_HIGH],
            },
        }
        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
            errors=errors,
        )


def _reserve_options(options: Mapping[str, Any]) -> dict[str, Any]:
    """Return persisted reserve options merged over safe defaults."""
    return {
        CONF_RESERVE_ENABLED: options.get(
            CONF_RESERVE_ENABLED, DEFAULT_RESERVE_ENABLED
        ),
        CONF_RESERVE_SOC_ENTITIES: options.get(CONF_RESERVE_SOC_ENTITIES, []),
        CONF_RESERVE_POINT_A_TIME: options.get(
            CONF_RESERVE_POINT_A_TIME, DEFAULT_RESERVE_POINT_A_TIME
        ),
        CONF_RESERVE_POINT_A_LOW: options.get(
            CONF_RESERVE_POINT_A_LOW, DEFAULT_RESERVE_POINT_A_LOW
        ),
        CONF_RESERVE_POINT_A_HIGH: options.get(
            CONF_RESERVE_POINT_A_HIGH, DEFAULT_RESERVE_POINT_A_HIGH
        ),
        CONF_RESERVE_POINT_B_TIME: options.get(
            CONF_RESERVE_POINT_B_TIME, DEFAULT_RESERVE_POINT_B_TIME
        ),
        CONF_RESERVE_POINT_B_LOW: options.get(
            CONF_RESERVE_POINT_B_LOW, DEFAULT_RESERVE_POINT_B_LOW
        ),
        CONF_RESERVE_POINT_B_HIGH: options.get(
            CONF_RESERVE_POINT_B_HIGH, DEFAULT_RESERVE_POINT_B_HIGH
        ),
    }
