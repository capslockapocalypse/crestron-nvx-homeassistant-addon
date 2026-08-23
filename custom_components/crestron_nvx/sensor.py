"""Sensor platform for Crestron NVX."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .entity import crestron_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Crestron NVX sensors."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinators = data["coordinators"]
    api = data["api"]

    entities = []
    for device_name, coordinator in coordinators.items():
        device = api.get_device(device_name)
        entities.extend(
            [
                CrestronNVXResolutionSensor(coordinator, device),
                CrestronNVXVideoConnectionSensor(coordinator, device),
                CrestronNVXHDCPSensor(coordinator, device),
                CrestronNVXNetworkSensor(coordinator, device),
            ]
        )

    async_add_entities(entities)


class CrestronNVXSensorBase(CoordinatorEntity, SensorEntity):
    """Base class for Crestron NVX sensors."""

    def __init__(self, coordinator, device):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.device = device
        self._attr_device_info = crestron_device_info(device)


class CrestronNVXResolutionSensor(CrestronNVXSensorBase):
    """Sensor for video resolution."""

    def __init__(self, coordinator, device):
        """Initialize the resolution sensor."""
        super().__init__(coordinator, device)
        self._attr_name = f"{device.name} Resolution"
        self._attr_unique_id = f"{device.host}_resolution"
        self._attr_icon = "mdi:video"

    @property
    def native_value(self):
        """Return the resolution as e.g. '1920x1080@60'."""
        video = (self.coordinator.data or {}).get("video")
        if not video or not video.get("horizontal_resolution"):
            return "Unknown"
        return (
            f"{video['horizontal_resolution']}x{video['vertical_resolution']}"
            f"@{video['frames_per_second']}"
        )


class CrestronNVXVideoConnectionSensor(CrestronNVXSensorBase):
    """Sensor for HDMI signal/sink connection status.

    Transmitters report whether a source is sending sync on their HDMI
    input; receivers report whether a display is connected on their HDMI
    output. Different question, same shape - one sensor, role-aware label.
    """

    def __init__(self, coordinator, device):
        """Initialize the sensor."""
        super().__init__(coordinator, device)
        label = "Sink Connected" if device.is_receiver else "Signal Detected"
        self._attr_name = f"{device.name} {label}"
        self._attr_unique_id = f"{device.host}_video_connected"
        self._attr_icon = "mdi:video-input-hdmi"

    @property
    def native_value(self):
        """Return connected/disconnected."""
        video = (self.coordinator.data or {}).get("video")
        connected = bool(video and video.get("connected"))
        return "connected" if connected else "disconnected"


class CrestronNVXHDCPSensor(CrestronNVXSensorBase):
    """Sensor for HDCP state.

    The device reports a real string state (e.g. "Authenticated",
    "Non-HDCPSource", "NoHDCPReceiverInDownstream"), not a simple boolean -
    exposed as-is rather than collapsed to active/inactive.
    """

    def __init__(self, coordinator, device):
        """Initialize the HDCP sensor."""
        super().__init__(coordinator, device)
        self._attr_name = f"{device.name} HDCP State"
        self._attr_unique_id = f"{device.host}_hdcp_state"
        self._attr_icon = "mdi:shield-lock"

    @property
    def native_value(self):
        """Return the raw HDCP state string."""
        video = (self.coordinator.data or {}).get("video")
        return (video or {}).get("hdcp_state") or "Unknown"


class CrestronNVXNetworkSensor(CrestronNVXSensorBase):
    """Sensor for network connection status."""

    def __init__(self, coordinator, device):
        """Initialize the network sensor."""
        super().__init__(coordinator, device)
        self._attr_name = f"{device.name} Network Status"
        self._attr_unique_id = f"{device.host}_network_status"
        self._attr_icon = "mdi:ethernet"

    @property
    def native_value(self):
        """Return connected/disconnected."""
        ethernet = (self.coordinator.data or {}).get("ethernet")
        connected = bool(ethernet and ethernet.get("connected"))
        return "connected" if connected else "disconnected"

    @property
    def extra_state_attributes(self):
        """Return the IP address as an attribute."""
        ethernet = (self.coordinator.data or {}).get("ethernet") or {}
        return {"ip_address": ethernet.get("ip_address")}
