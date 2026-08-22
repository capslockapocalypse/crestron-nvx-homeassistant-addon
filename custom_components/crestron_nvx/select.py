"""Select platform for Crestron NVX receivers - source switching via AvRouting."""
from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

OFF_OPTION = "Off"


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
        if device.is_receiver:
            entities.append(CrestronNVXStreamSelect(coordinator, device))

    async_add_entities(entities)


class CrestronNVXStreamSelect(CoordinatorEntity, SelectEntity):
    """Select entity for switching a receiver's source via AvRouting.

    Switches video, audio and USB together (verified live against real
    hardware) - writing StreamReceive's MulticastAddress/StreamLocation
    directly either has no effect or leaves audio on the old source, since
    this fleet's audio is a separate breakaway subscription that only the
    AvRouting object keeps in sync with video.

    Also offers an "Off" option, which clears VideoSource/AudioSource/
    UsbSource to empty strings - confirmed live to blank the output cleanly
    (no video/audio routed) rather than erroring or leaving the last frame.
    """

    def __init__(self, coordinator, device):
        """Initialize the select entity."""
        super().__init__(coordinator)
        self.device = device
        self._attr_name = f"{device.name} Stream Source"
        self._attr_unique_id = f"{device.host}_stream_source"
        self._attr_icon = "mdi:video-input-hdmi"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device.host)},
            "name": device.name,
            "manufacturer": "Crestron",
            "model": f"NVX {device.device_mode}",
        }

    def _streams(self) -> dict[str, dict]:
        return (self.coordinator.data or {}).get("discovered_streams") or {}

    @property
    def options(self) -> list[str]:
        """Return available source names, plus Off."""
        names = [info.get("SessionName") for info in self._streams().values() if info.get("SessionName")]
        return [OFF_OPTION, *names]

    @property
    def current_option(self) -> str | None:
        """Return the currently routed source name, or Off."""
        route = (self.coordinator.data or {}).get("route")
        if not route:
            return None
        current_uid = route.get("VideoSource")
        if not current_uid:
            return OFF_OPTION
        stream = self._streams().get(current_uid)
        if stream:
            return stream.get("SessionName")
        return f"Unknown ({current_uid})"

    async def async_select_option(self, option: str) -> None:
        """Switch to the selected source, or clear routing if Off."""
        if option == OFF_OPTION:
            target_uid = ""
        else:
            target_uid = next(
                (uid for uid, info in self._streams().items() if info.get("SessionName") == option),
                None,
            )
            if target_uid is None:
                _LOGGER.error("Could not find source UID for option: %s", option)
                return

        success = await self.device.set_route(target_uid)
        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to switch %s to source: %s", self.device.host, option)
