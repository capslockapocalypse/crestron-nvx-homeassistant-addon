"""The Crestron NVX integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .crestron_nvx_api import CrestronNVXAPI, CrestronNVXDevice
from .const import DOMAIN, CONF_DEVICES, CONF_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SELECT, Platform.BUTTON]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Crestron NVX from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    api = CrestronNVXAPI()
    
    # Add all configured devices
    devices_config = entry.data.get(CONF_DEVICES, [])
    for device_config in devices_config:
        await api.add_device(
            host=device_config["host"],
            device_type=device_config["device_type"],
            name=device_config["name"],
            username=device_config.get("username"),
            password=device_config.get("password"),
        )
    
    # Create coordinators for each device
    coordinators = {}
    scan_interval = entry.data.get(CONF_SCAN_INTERVAL, 30)
    
    for device_name, device in api.devices.items():
        coordinator = CrestronNVXDataUpdateCoordinator(
            hass,
            device=device,
            update_interval=timedelta(seconds=scan_interval),
        )
        await coordinator.async_config_entry_first_refresh()
        coordinators[device_name] = coordinator
    
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinators": coordinators,
    }
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        data = hass.data[DOMAIN].pop(entry.entry_id)
        await data["api"].close()
    
    return unload_ok


class CrestronNVXDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Crestron NVX data."""

    def __init__(
        self,
        hass: HomeAssistant,
        device: CrestronNVXDevice,
        update_interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        self.device = device
        super().__init__(
            hass,
            _LOGGER,
            name=f"Crestron NVX {device.name}",
            update_interval=update_interval,
        )

    async def _async_update_data(self):
        """Fetch data from the device."""
        try:
            data = await self.device.update_all_status()
            
            # Process and structure the data
            processed_data = {
                "resolution": None,
                "signal_detected": False,
                "hdcp_active": False,
                "audio_present": False,
                "network_connected": False,
                "subscriptions": [],
            }
            
            if data.get("video_status"):
                processed_data["resolution"] = data["video_status"].get("Resolution", "Unknown")
                processed_data["signal_detected"] = data["video_status"].get("SignalDetected", False)
            
            if data.get("hdcp_status"):
                processed_data["hdcp_active"] = data["hdcp_status"].get("Active", False)
            
            if data.get("audio_status"):
                processed_data["audio_present"] = data["audio_status"].get("AudioDetected", False)
            
            if data.get("network_status"):
                processed_data["network_connected"] = data["network_status"].get("Connected", False)
            
            if data.get("subscriptions"):
                processed_data["subscriptions"] = data["subscriptions"]
            
            return processed_data
            
        except Exception as err:
            raise UpdateFailed(f"Error communicating with device: {err}")
