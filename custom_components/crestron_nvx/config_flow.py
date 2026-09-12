"""Config flow for Crestron NVX integration."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_ENABLE_PREVIEW_CAMERA, CONF_SCAN_INTERVAL, CONF_VERIFY_SSL, DOMAIN
from .crestron_nvx_api import CrestronNVXAuthError, CrestronNVXConnectionError, CrestronNVXDevice

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): str,
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_VERIFY_SSL, default=False): bool,
        vol.Optional(CONF_SCAN_INTERVAL, default=30): vol.All(
            vol.Coerce(int), vol.Range(min=10, max=300)
        ),
    }
)


class CrestronNVXConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Crestron NVX."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> CrestronNVXOptionsFlow:
        """Get the options flow for this handler."""
        return CrestronNVXOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            session = aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True))
            try:
                device = CrestronNVXDevice(
                    host=user_input[CONF_HOST],
                    username=user_input[CONF_USERNAME],
                    password=user_input[CONF_PASSWORD],
                    session=session,
                    verify_ssl=user_input[CONF_VERIFY_SSL],
                )
                try:
                    await device.login()
                except CrestronNVXAuthError:
                    errors["base"] = "invalid_auth"
                except CrestronNVXConnectionError:
                    errors["base"] = "cannot_connect"
                else:
                    if device.device_mode is None:
                        errors["base"] = "cannot_connect"
                    else:
                        await device.logout()
                        await self.async_set_unique_id(
                            f"{user_input[CONF_HOST]}_{user_input[CONF_NAME]}"
                        )
                        self._abort_if_unique_id_configured()

                        return self.async_create_entry(
                            title=user_input[CONF_NAME],
                            data={
                                "devices": [
                                    {**user_input, "device_mode": device.device_mode}
                                ],
                                CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
                            },
                        )
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception validating Crestron NVX device")
                errors["base"] = "unknown"
            finally:
                await session.close()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


class CrestronNVXOptionsFlow(config_entries.OptionsFlow):
    """Options for an existing entry - currently just the preview camera opt-in.

    Off by default: fetching a preview image hits the device's JPEG snapshot
    generator (see crestron_nvx_api.py's get_preview_image), a separate,
    heavier feature from the JSON status endpoints everything else here
    uses, so it isn't enabled unconditionally for everyone.
    """

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_ENABLE_PREVIEW_CAMERA,
                        default=self.config_entry.options.get(
                            CONF_ENABLE_PREVIEW_CAMERA, False
                        ),
                    ): bool,
                }
            ),
        )
