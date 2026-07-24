"""Config flow for Fsolar Cloud."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    FsolarApi,
    FsolarAuthenticationError,
    FsolarError,
)
from .const import CONF_INVERTERS, DOMAIN


class FsolarConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle an Fsolar Cloud config flow."""

    VERSION = 1

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
            except FsolarAuthenticationError:
                errors["base"] = "invalid_auth"
            except FsolarError:
                errors["base"] = "cannot_connect"
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
