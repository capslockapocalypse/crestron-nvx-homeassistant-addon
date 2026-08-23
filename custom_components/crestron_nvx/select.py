"""Select platforms for Crestron NVX: network source, audio source, and HDMI input switching."""
from __future__ import annotations

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .entity import crestron_device_info

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
            entities.append(CrestronNVXAudioSourceSelect(coordinator, device))
            if device.hdmi_inputs > 0:
                entities.append(CrestronNVXLocalSourceSelect(coordinator, device))
        elif device.is_transmitter and device.hdmi_inputs > 1:
            entities.append(CrestronNVXTransmitterInputSelect(coordinator, device))

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
        self._attr_device_info = crestron_device_info(device)

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
            success = await self.device.set_route_off()
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


class CrestronNVXAudioSourceSelect(CoordinatorEntity, SelectEntity):
    """Independent audio source select, for anyone not running audio-follows-video.

    Only meaningful - and only shown as available - when the "Audio Follows
    Video" switch (switch.py) is off. Writes AudioSource alone via
    AvRouting, verified live not to disturb VideoSource/UsbSource.
    """

    def __init__(self, coordinator, device):
        """Initialize the select entity."""
        super().__init__(coordinator)
        self.device = device
        self._attr_name = f"{device.name} Audio Source"
        self._attr_unique_id = f"{device.host}_audio_source"
        self._attr_icon = "mdi:volume-high"
        self._attr_device_info = crestron_device_info(device)

    def _streams(self) -> dict[str, dict]:
        return (self.coordinator.data or {}).get("discovered_streams") or {}

    @property
    def available(self) -> bool:
        """Greyed out while Audio Follows Video is on - it owns AudioSource then."""
        if not super().available:
            return False
        route_control = (self.coordinator.data or {}).get("route_control") or {}
        return not route_control.get("IsSecondaryAudioFollowsVideoEnabled", True)

    @property
    def options(self) -> list[str]:
        """Return available source names."""
        names = [info.get("SessionName") for info in self._streams().values() if info.get("SessionName")]
        return names or ["No sources available"]

    @property
    def current_option(self) -> str | None:
        """Return the currently routed audio source name."""
        route = (self.coordinator.data or {}).get("route")
        if not route:
            return None
        current_uid = route.get("AudioSource")
        if not current_uid:
            return None
        stream = self._streams().get(current_uid)
        return stream.get("SessionName") if stream else f"Unknown ({current_uid})"

    async def async_select_option(self, option: str) -> None:
        """Switch audio to the selected source, independent of video."""
        target_uid = next(
            (uid for uid, info in self._streams().items() if info.get("SessionName") == option),
            None,
        )
        if target_uid is None:
            _LOGGER.error("Could not find source UID for option: %s", option)
            return

        success = await self.device.set_audio_source(target_uid)
        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to switch %s audio to source: %s", self.device.host, option)


class CrestronNVXLocalSourceSelect(CoordinatorEntity, SelectEntity):
    """Local HDMI input vs. network Stream select, for receivers with a local HDMI input.

    Only created when the device reports at least one local HDMI input
    (DeviceCapabilities.PortConfig.NumberOfHdmiInputs > 0) - most receivers
    in this fleet don't have one at all. Backed by DeviceSpecific.VideoSource,
    confirmed live to accept "Stream" and "InputN" and to correctly resume
    the existing AvRouting route when switched back to "Stream".
    """

    def __init__(self, coordinator, device):
        """Initialize the select entity."""
        super().__init__(coordinator)
        self.device = device
        self._attr_name = f"{device.name} Video Input"
        self._attr_unique_id = f"{device.host}_video_input"
        self._attr_icon = "mdi:swap-horizontal"
        self._attr_options = ["Stream"] + [f"Local Input {i + 1}" for i in range(device.hdmi_inputs)]
        self._attr_device_info = crestron_device_info(device)

    @property
    def current_option(self) -> str | None:
        """Return "Stream" or "Local Input N", from DeviceSpecific.VideoSource."""
        value = ((self.coordinator.data or {}).get("device_specific") or {}).get("VideoSource")
        if value == "Stream":
            return "Stream"
        if value and value.startswith("Input"):
            return f"Local Input {value[len('Input'):]}"
        return None

    async def async_select_option(self, option: str) -> None:
        """Switch between the network stream and a local HDMI input."""
        if option == "Stream":
            value = "Stream"
        else:
            index = option.removeprefix("Local Input ").strip()
            value = f"Input{index}"

        success = await self.device.set_video_source(value)
        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to set %s video input to: %s", self.device.host, option)


class CrestronNVXTransmitterInputSelect(CoordinatorEntity, SelectEntity):
    """HDMI input select, for transmitters with more than one HDMI input.

    Only created when NumberOfHdmiInputs > 1 (e.g. a DM-NVX-352) - a
    single-input transmitter like a DM-NVX-E30 has nothing to switch
    between. Same DeviceSpecific.VideoSource field as the receiver-side
    local/stream select, just without the "Stream" option.
    """

    def __init__(self, coordinator, device):
        """Initialize the select entity."""
        super().__init__(coordinator)
        self.device = device
        self._attr_name = f"{device.name} HDMI Input"
        self._attr_unique_id = f"{device.host}_hdmi_input"
        self._attr_icon = "mdi:video-input-hdmi"
        self._attr_options = [f"Input {i + 1}" for i in range(device.hdmi_inputs)]
        self._attr_device_info = crestron_device_info(device)

    @property
    def current_option(self) -> str | None:
        """Return "Input N", from DeviceSpecific.VideoSource."""
        value = ((self.coordinator.data or {}).get("device_specific") or {}).get("VideoSource")
        if value and value.startswith("Input"):
            return f"Input {value[len('Input'):]}"
        return None

    async def async_select_option(self, option: str) -> None:
        """Switch the active HDMI input."""
        index = option.removeprefix("Input ").strip()
        success = await self.device.set_video_source(f"Input{index}")
        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("Failed to set %s HDMI input to: %s", self.device.host, option)
