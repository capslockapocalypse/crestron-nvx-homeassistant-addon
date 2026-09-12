"""Camera platform for Crestron NVX - live preview snapshot.

Opt-in, off by default: enable it per-entry via the integration's Options
(the gear icon on its entry in Settings > Devices & Services). Fetching this
polls the device's own JPEG preview generator (Device/Preview), a separate,
heavier feature from the small JSON status endpoints everything else here
uses, so it isn't created unconditionally for everyone.
"""
from __future__ import annotations

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_ENABLE_PREVIEW_CAMERA, DOMAIN
from .entity import crestron_device_info


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Crestron NVX preview camera, if enabled in this entry's options."""
    if not entry.options.get(CONF_ENABLE_PREVIEW_CAMERA, False):
        return

    data = hass.data[DOMAIN][entry.entry_id]
    api = data["api"]

    entities = [
        CrestronNVXPreviewCamera(api.get_device(device_name))
        for device_name in data["coordinators"]
        if api.get_device(device_name).preview_supported
    ]
    async_add_entities(entities)


class CrestronNVXPreviewCamera(Camera):
    """Snapshot of what this device's input/output currently shows.

    Not tied to the polling coordinator - the image is fetched fresh
    on-demand each time Home Assistant asks for it (dashboard render,
    automation snapshot, etc.), same as any other still-image camera.
    """

    def __init__(self, device) -> None:
        """Initialize the camera."""
        super().__init__()
        self.device = device
        self._attr_name = f"{device.name} Preview"
        self._attr_unique_id = f"{device.host}_preview"
        self._attr_device_info = crestron_device_info(device)

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Fetch the current preview JPEG."""
        return await self.device.get_preview_image()
