"""Switch platform for Crestron NVX - Audio Follows Video toggle (receivers)."""
from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .entity import crestron_device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Crestron NVX switch entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinators = data["coordinators"]
    api = data["api"]

    entities = [
        CrestronNVXAudioFollowsVideoSwitch(coordinator, api.get_device(device_name))
        for device_name, coordinator in coordinators.items()
        if api.get_device(device_name).is_receiver
    ]
    async_add_entities(entities)


class CrestronNVXAudioFollowsVideoSwitch(CoordinatorEntity, SwitchEntity):
    """Toggle for AvRouting/RouteControl.IsSecondaryAudioFollowsVideoEnabled.

    When on (the device's own default), switching the video source also
    switches audio automatically - the "Audio Source" select entity is
    greyed out (unavailable) while this is on, since the device owns
    AudioSource in that state. When off, "Audio Source" becomes usable to
    route audio independently of video.
    """

    def __init__(self, coordinator, device):
        """Initialize the switch."""
        super().__init__(coordinator)
        self.device = device
        self._attr_name = f"{device.name} Audio Follows Video"
        self._attr_unique_id = f"{device.host}_audio_follows_video"
        self._attr_icon = "mdi:link-variant"
        self._attr_device_info = crestron_device_info(device)

    @property
    def is_on(self) -> bool:
        """Return whether audio currently follows video."""
        route_control = (self.coordinator.data or {}).get("route_control") or {}
        return bool(route_control.get("IsSecondaryAudioFollowsVideoEnabled"))

    async def async_turn_on(self, **kwargs) -> None:
        """Enable audio-follows-video and immediately re-sync audio to the current video source."""
        if await self.device.set_audio_follows_video(True):
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to enable audio-follows-video on %s", self.device.host)

    async def async_turn_off(self, **kwargs) -> None:
        """Disable audio-follows-video, freeing the Audio Source select for independent use."""
        if await self.device.set_audio_follows_video(False):
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to disable audio-follows-video on %s", self.device.host)
