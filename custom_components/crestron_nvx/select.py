"""Select platform for Crestron NVX receivers."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ATTR_SUBSCRIPTIONS, DEVICE_TYPE_RECEIVER

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Crestron NVX select entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinators = data["coordinators"]
    api = data["api"]

    entities = []
    for device_name, coordinator in coordinators.items():
        device = api.get_device(device_name)
        
        # Only add select entity for receivers
        if device.device_type == DEVICE_TYPE_RECEIVER:
            entities.append(CrestronNVXStreamSelect(coordinator, device))

    async_add_entities(entities)


class CrestronNVXStreamSelect(CoordinatorEntity, SelectEntity):
    """Select entity for choosing stream subscription on NVX receiver."""

    def __init__(self, coordinator, device):
        """Initialize the select entity."""
        super().__init__(coordinator)
        self.device = device
        self._attr_name = f"{device.name} Stream Source"
        self._attr_unique_id = f"{device.name}_stream_source"
        self._attr_icon = "mdi:video-input-hdmi"
        
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device.name)},
            "name": device.name,
            "manufacturer": "Crestron",
            "model": f"NVX {device.device_type.capitalize()}",
        }

    @property
    def options(self) -> list[str]:
        """Return available stream options."""
        subscriptions = self.coordinator.data.get(ATTR_SUBSCRIPTIONS, [])
        
        if not subscriptions:
            return ["No streams available"]
        
        # Extract stream names/IDs from subscriptions
        options = []
        for sub in subscriptions:
            # Adjust based on actual API response structure
            stream_name = sub.get("Name") or sub.get("StreamId") or sub.get("Id")
            if stream_name:
                options.append(stream_name)
        
        return options if options else ["No streams available"]

    @property
    def current_option(self) -> str | None:
        """Return currently selected stream."""
        subscriptions = self.coordinator.data.get(ATTR_SUBSCRIPTIONS, [])
        
        if not subscriptions:
            return "No streams available"
        
        # Find active subscription
        for sub in subscriptions:
            if sub.get("Active") or sub.get("IsActive"):
                stream_name = sub.get("Name") or sub.get("StreamId") or sub.get("Id")
                return stream_name
        
        # If no active stream found, return first option
        if subscriptions:
            return self.options[0] if self.options else None
        
        return "No streams available"

    async def async_select_option(self, option: str) -> None:
        """Change the selected stream."""
        if option == "No streams available":
            _LOGGER.warning("Cannot switch to 'No streams available'")
            return
        
        subscriptions = self.coordinator.data.get(ATTR_SUBSCRIPTIONS, [])
        
        # Find the stream ID for the selected option
        stream_id = None
        for sub in subscriptions:
            stream_name = sub.get("Name") or sub.get("StreamId") or sub.get("Id")
            if stream_name == option:
                stream_id = sub.get("StreamId") or sub.get("Id")
                break
        
        if stream_id:
            _LOGGER.info(f"Switching {self.device.name} to stream: {option} (ID: {stream_id})")
            success = await self.device.subscribe_to_stream(stream_id)
            
            if success:
                # Request immediate coordinator update
                await self.coordinator.async_request_refresh()
            else:
                _LOGGER.error(f"Failed to switch stream for {self.device.name}")
        else:
            _LOGGER.error(f"Could not find stream ID for option: {option}")

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.last_update_success and len(self.options) > 0
