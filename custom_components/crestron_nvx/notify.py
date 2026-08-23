"""Notify platform for Crestron NVX - push arbitrary text to a device's OSD.

Not receiver-only: some transmitter models (e.g. DM-NVX-352) have a local
HDMI output with its own OSD too, confirmed live - so this is gated on
device.osd_supported alone, not device role.

For automations that want to show a status message on-screen (e.g. "DSP
Mode: Movie" when switching sources or DSP modes): calling
notify.send_message on this entity sets the OSD text and turns the OSD on,
then automatically turns it off again a few seconds later. Sending another
message before that timer elapses cancels the pending turn-off and starts a
fresh one, so the new text stays on screen instead of flickering.
"""
from __future__ import annotations

import asyncio
import logging

from homeassistant.components.notify import NotifyEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import crestron_device_info

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Crestron NVX notify entities."""
    data = hass.data[DOMAIN][entry.entry_id]
    api = data["api"]

    entities = [
        CrestronNVXOsdNotify(device)
        for device in api.devices.values()
        if device.osd_supported
    ]
    async_add_entities(entities)


class CrestronNVXOsdNotify(NotifyEntity):
    """Sends a message to the device's OSD, auto-clearing it after a delay."""

    def __init__(self, device):
        """Initialize the notify entity."""
        self.device = device
        self._attr_name = f"{device.name} OSD"
        self._attr_unique_id = f"{device.host}_osd_notify"
        self._attr_icon = "mdi:message-text-outline"
        self._attr_device_info = crestron_device_info(device)
        self._clear_task: asyncio.Task | None = None

    async def async_send_message(self, message: str, title: str | None = None) -> None:
        """Show message on the OSD, replacing/extending any message already showing."""
        if self._clear_task:
            self._clear_task.cancel()
            self._clear_task = None

        if not await self.device.set_osd(text=message, enabled=True):
            _LOGGER.error("Failed to set OSD text on %s", self.device.host)
            return

        self._clear_task = self.hass.async_create_background_task(
            self._clear_after_delay(), name=f"crestron_nvx_osd_clear_{self.device.host}"
        )

    async def _clear_after_delay(self) -> None:
        try:
            await asyncio.sleep(self.device.osd_display_seconds)
        except asyncio.CancelledError:
            raise
        else:
            if not await self.device.set_osd(enabled=False):
                _LOGGER.error("Failed to clear OSD on %s", self.device.host)

    async def async_will_remove_from_hass(self) -> None:
        """Cancel any pending clear-OSD task."""
        if self._clear_task:
            self._clear_task.cancel()
