"""The Crestron NVX integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_SCAN_INTERVAL, CONF_VERIFY_SSL, DOMAIN
from .crestron_nvx_api import CrestronNVXAPI, CrestronNVXDevice

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SELECT, Platform.EVENT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Crestron NVX from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    devices_config = entry.data.get("devices", [])
    verify_ssl = devices_config[0].get(CONF_VERIFY_SSL, False) if devices_config else False
    api = CrestronNVXAPI(verify_ssl=verify_ssl)

    for device_config in devices_config:
        await api.add_device(
            host=device_config[CONF_HOST],
            name=device_config["name"],
            username=device_config[CONF_USERNAME],
            password=device_config[CONF_PASSWORD],
        )

    scan_interval = entry.data.get(CONF_SCAN_INTERVAL, 30)
    coordinators: dict[str, CrestronNVXDataUpdateCoordinator] = {}
    for device_name, device in api.devices.items():
        coordinator = CrestronNVXDataUpdateCoordinator(
            hass, device=device, update_interval=timedelta(seconds=scan_interval)
        )
        await coordinator.async_config_entry_first_refresh()
        coordinators[device_name] = coordinator

    hass.data[DOMAIN][entry.entry_id] = {"api": api, "coordinators": coordinators}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        data = hass.data[DOMAIN].pop(entry.entry_id)
        await data["api"].close()

    return unload_ok


class CrestronNVXDataUpdateCoordinator(DataUpdateCoordinator):
    """Fetches video/ethernet/route status for a single NVX device."""

    def __init__(
        self, hass: HomeAssistant, device: CrestronNVXDevice, update_interval: timedelta
    ) -> None:
        """Initialize the coordinator."""
        self.device = device
        super().__init__(
            hass, _LOGGER, name=f"Crestron NVX {device.host}", update_interval=update_interval
        )

    async def _async_update_data(self) -> dict:
        """Fetch status from the device."""
        try:
            data = {
                "video": await self.device.get_video_status(),
                "ethernet": await self.device.get_ethernet_status(),
            }
            if self.device.is_receiver:
                data["discovered_streams"] = await self.device.get_discovered_streams()
                data["route"] = await self.device.get_current_route()
            return data
        except Exception as err:
            raise UpdateFailed(f"Error communicating with {self.device.host}: {err}") from err
