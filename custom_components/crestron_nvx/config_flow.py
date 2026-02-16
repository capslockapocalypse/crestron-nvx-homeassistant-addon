"""Config flow for Crestron NVX integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    CONF_DEVICE_TYPE,
    CONF_SCAN_INTERVAL,
    DEVICE_TYPE_RECEIVER,
    DEVICE_TYPE_TRANSMITTER,
)
from .crestron_nvx_api import CrestronNVXDevice

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): str,
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_DEVICE_TYPE): vol.In([DEVICE_TYPE_TRANSMITTER, DEVICE_TYPE_RECEIVER]),
        vol.Optional(CONF_USERNAME): str,
        vol.Optional(CONF_PASSWORD): str,
        vol.Optional(CONF_SCAN_INTERVAL, default=30): vol.All(
            vol.Coerce(int), vol.Range(min=10, max=300)
        ),
    }
)


class CrestronNVXConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Crestron NVX."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate the connection
            device = CrestronNVXDevice(
                host=user_input[CONF_HOST],
                device_type=user_input[CONF_DEVICE_TYPE],
                name=user_input[CONF_NAME],
                username=user_input.get(CONF_USERNAME),
                password=user_input.get(CONF_PASSWORD),
            )

            try:
                # Try to get device info to validate connection
                device_info = await device.get_device_info()
                await device.close()

                if device_info is None:
                    errors["base"] = "cannot_connect"
                else:
                    # Create a unique ID based on host and name
                    await self.async_set_unique_id(
                        f"{user_input[CONF_HOST]}_{user_input[CONF_NAME]}"
                    )
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=user_input[CONF_NAME],
                        data={
                            "devices": [user_input],
                            CONF_SCAN_INTERVAL: user_input.get(CONF_SCAN_INTERVAL, 30),
                        },
                    )

            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
                await device.close()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
