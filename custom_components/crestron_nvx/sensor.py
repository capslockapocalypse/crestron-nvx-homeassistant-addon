"""Sensor platform for Crestron NVX."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    ATTR_RESOLUTION,
    ATTR_SIGNAL_DETECTED,
    ATTR_HDCP_ACTIVE,
    ATTR_AUDIO_PRESENT,
    ATTR_NETWORK_CONNECTED,
)


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
        
        # Add sensors for all devices
        entities.extend([
            CrestronNVXResolutionSensor(coordinator, device),
            CrestronNVXSignalSensor(coordinator, device),
            CrestronNVXHDCPSensor(coordinator, device),
            CrestronNVXAudioSensor(coordinator, device),
            CrestronNVXNetworkSensor(coordinator, device),
        ])

    async_add_entities(entities)


class CrestronNVXSensorBase(CoordinatorEntity, SensorEntity):
    """Base class for Crestron NVX sensors."""

    def __init__(self, coordinator, device):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.device = device
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device.name)},
            "name": device.name,
            "manufacturer": "Crestron",
            "model": f"NVX {device.device_type.capitalize()}",
        }


class CrestronNVXResolutionSensor(CrestronNVXSensorBase):
    """Sensor for video resolution."""

    def __init__(self, coordinator, device):
        """Initialize the resolution sensor."""
        super().__init__(coordinator, device)
        self._attr_name = f"{device.name} Resolution"
        self._attr_unique_id = f"{device.name}_resolution"
        self._attr_icon = "mdi:video"

    @property
    def native_value(self):
        """Return the resolution."""
        return self.coordinator.data.get(ATTR_RESOLUTION, "Unknown")

    @property
    def extra_state_attributes(self):
        """Return additional attributes."""
        return {
            "device_type": self.device.device_type,
            "host": self.device.host,
        }


class CrestronNVXSignalSensor(CrestronNVXSensorBase):
    """Sensor for signal detection status."""

    def __init__(self, coordinator, device):
        """Initialize the signal sensor."""
        super().__init__(coordinator, device)
        self._attr_name = f"{device.name} Signal Status"
        self._attr_unique_id = f"{device.name}_signal_status"
        self._attr_icon = "mdi:signal"
        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_options = ["detected", "no_signal"]

    @property
    def native_value(self):
        """Return the signal status."""
        detected = self.coordinator.data.get(ATTR_SIGNAL_DETECTED, False)
        return "detected" if detected else "no_signal"


class CrestronNVXHDCPSensor(CrestronNVXSensorBase):
    """Sensor for HDCP status."""

    def __init__(self, coordinator, device):
        """Initialize the HDCP sensor."""
        super().__init__(coordinator, device)
        self._attr_name = f"{device.name} HDCP Status"
        self._attr_unique_id = f"{device.name}_hdcp_status"
        self._attr_icon = "mdi:shield-lock"
        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_options = ["active", "inactive"]

    @property
    def native_value(self):
        """Return the HDCP status."""
        active = self.coordinator.data.get(ATTR_HDCP_ACTIVE, False)
        return "active" if active else "inactive"


class CrestronNVXAudioSensor(CrestronNVXSensorBase):
    """Sensor for audio presence."""

    def __init__(self, coordinator, device):
        """Initialize the audio sensor."""
        super().__init__(coordinator, device)
        self._attr_name = f"{device.name} Audio Status"
        self._attr_unique_id = f"{device.name}_audio_status"
        self._attr_icon = "mdi:volume-high"
        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_options = ["present", "absent"]

    @property
    def native_value(self):
        """Return the audio status."""
        present = self.coordinator.data.get(ATTR_AUDIO_PRESENT, False)
        return "present" if present else "absent"


class CrestronNVXNetworkSensor(CrestronNVXSensorBase):
    """Sensor for network connection status."""

    def __init__(self, coordinator, device):
        """Initialize the network sensor."""
        super().__init__(coordinator, device)
        self._attr_name = f"{device.name} Network Status"
        self._attr_unique_id = f"{device.name}_network_status"
        self._attr_icon = "mdi:ethernet"
        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_options = ["connected", "disconnected"]

    @property
    def native_value(self):
        """Return the network status."""
        connected = self.coordinator.data.get(ATTR_NETWORK_CONNECTED, False)
        return "connected" if connected else "disconnected"
