"""Number platform for Crestron NVX - configurable OSD display duration.

Purely a Home Assistant-side setting (the Crestron API has no such concept)
controlling how long notify.py's OSD notify entity leaves text on screen
before auto-clearing it. Persisted across restarts via RestoreNumber.
"""
from __future__ import annotations

from homeassistant.components.number import NumberMode, RestoreNumber
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import crestron_device_info

MIN_SECONDS = 1
MAX_SECONDS = 60


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Crestron NVX number entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    api = data["api"]

    entities = [
        CrestronNVXOsdDurationNumber(device)
        for device in api.devices.values()
        if device.osd_supported
    ]
    async_add_entities(entities)


class CrestronNVXOsdDurationNumber(RestoreNumber):
    """How many seconds notify.py leaves OSD text on screen before clearing it."""

    _attr_native_min_value = MIN_SECONDS
    _attr_native_max_value = MAX_SECONDS
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:timer-outline"

    def __init__(self, device):
        """Initialize the number entity."""
        self.device = device
        self._attr_name = f"{device.name} OSD Display Duration"
        self._attr_unique_id = f"{device.host}_osd_display_duration"
        self._attr_device_info = crestron_device_info(device)

    async def async_added_to_hass(self) -> None:
        """Restore the last configured duration, if any."""
        await super().async_added_to_hass()
        last_data = await self.async_get_last_number_data()
        if last_data is not None and last_data.native_value is not None:
            self.device.osd_display_seconds = last_data.native_value

    @property
    def native_value(self) -> float:
        """Return the currently configured duration."""
        return self.device.osd_display_seconds

    async def async_set_native_value(self, value: float) -> None:
        """Update the configured duration."""
        self.device.osd_display_seconds = value
        self.async_write_ha_state()
