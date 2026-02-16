"""Button platform for Crestron NVX CEC commands."""
from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Crestron NVX button entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinators = data["coordinators"]
    api = data["api"]

    entities = []
    for device_name, coordinator in coordinators.items():
        device = api.get_device(device_name)
        
        # Add CEC control buttons
        entities.extend([
            CrestronNVXCECButton(coordinator, device, "Power On", "ImageOn"),
            CrestronNVXCECButton(coordinator, device, "Power Off", "Standby"),
            CrestronNVXCECButton(coordinator, device, "Volume Up", "VolumeUp"),
            CrestronNVXCECButton(coordinator, device, "Volume Down", "VolumeDown"),
            CrestronNVXCECButton(coordinator, device, "Mute", "Mute"),
        ])

    async_add_entities(entities)


class CrestronNVXCECButton(CoordinatorEntity, ButtonEntity):
    """Button entity for sending CEC commands."""

    def __init__(self, coordinator, device, button_name: str, cec_command: str):
        """Initialize the button."""
        super().__init__(coordinator)
        self.device = device
        self._button_name = button_name
        self._cec_command = cec_command
        
        self._attr_name = f"{device.name} CEC {button_name}"
        self._attr_unique_id = f"{device.name}_cec_{button_name.lower().replace(' ', '_')}"
        
        # Set appropriate icons based on command
        icon_map = {
            "Power On": "mdi:power",
            "Power Off": "mdi:power-off",
            "Volume Up": "mdi:volume-plus",
            "Volume Down": "mdi:volume-minus",
            "Mute": "mdi:volume-mute",
        }
        self._attr_icon = icon_map.get(button_name, "mdi:remote")
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device.name)},
            "name": device.name,
            "manufacturer": "Crestron",
            "model": f"NVX {device.device_type.capitalize()}",
        }

    async def async_press(self) -> None:
        """Handle button press."""
        _LOGGER.info(
            f"Sending CEC command '{self._cec_command}' to {self.device.name}"
        )
        
        success = await self.device.send_cec_command(self._cec_command)
        
        if success:
            _LOGGER.info(f"CEC command sent successfully to {self.device.name}")
        else:
            _LOGGER.error(f"Failed to send CEC command to {self.device.name}")
