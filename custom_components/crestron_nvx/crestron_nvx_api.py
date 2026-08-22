"""Client for the real Crestron DM NVX REST API (CresNext).

Reference: https://sdkcon78221.crestron.com/sdk/DM_NVX_REST_API/
All endpoints and behavior below were verified against live DM-NVX-E30,
DM-NVX-352, DM-NVX-350 and DM-NVX-D30 hardware, not just the docs.
"""
from __future__ import annotations

import base64
import logging
from typing import Any, Optional

import aiohttp

_LOGGER = logging.getLogger(__name__)

LOGIN_PATH = "/userlogin.html"
LOGOUT_PATH = "/logout"
LONGPOLL_PATH = "/Device/Longpoll"

DEVICE_MODE_TRANSMITTER = "Transmitter"
DEVICE_MODE_RECEIVER = "Receiver"

# CEC opcodes/operands relevant to the "listen for Apple TV remote presses"
# use case. Confirmed live: a real Volume Up press decoded to bytes
# 40 44 41 -> header 0x40 (source 4 "Playback Device 1" = the Apple TV,
# dest 0 "TV") + opcode 0x44 (User Control Pressed) + operand 0x41 (Volume Up).
_CEC_OPCODE_IMAGE_VIEW_ON = 0x04
_CEC_OPCODE_STANDBY = 0x36
_CEC_OPCODE_USER_CONTROL_PRESSED = 0x44
_CEC_OPCODE_USER_CONTROL_RELEASED = 0x45  # key-up; intentionally ignored

_CEC_STANDALONE_EVENTS = {
    _CEC_OPCODE_IMAGE_VIEW_ON: "power_on",
    _CEC_OPCODE_STANDBY: "power_off",
}
_CEC_USER_CONTROL_EVENTS = {
    0x41: "volume_up",
    0x42: "volume_down",
    0x43: "mute",
}


class CrestronNVXError(Exception):
    """Base error for this client."""


class CrestronNVXAuthError(CrestronNVXError):
    """Login failed (bad credentials or device rejected the session)."""


class CrestronNVXConnectionError(CrestronNVXError):
    """Device could not be reached."""


def decode_cec_message(b64_message: Optional[str]) -> Optional[str]:
    """Decode a raw base64 CEC frame into an HA event type, or None.

    The frame is base64(header_byte + opcode [+ operand]) with no other
    wrapping - confirmed by decoding real captured ReceiveCecMessage values.
    """
    if not b64_message:
        return None
    try:
        frame = base64.b64decode(b64_message, validate=True)
    except (ValueError, TypeError):
        return None
    if len(frame) < 2:
        return None
    opcode = frame[1]
    if opcode in _CEC_STANDALONE_EVENTS:
        return _CEC_STANDALONE_EVENTS[opcode]
    if opcode == _CEC_OPCODE_USER_CONTROL_PRESSED and len(frame) >= 3:
        return _CEC_USER_CONTROL_EVENTS.get(frame[2])
    return None


class CrestronNVXDevice:
    """A single Crestron NVX transmitter or receiver."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        session: aiohttp.ClientSession,
        verify_ssl: bool = False,
        name: Optional[str] = None,
    ) -> None:
        self.host = host
        self.name = name or host
        self.username = username
        self.password = password
        self.device_mode: Optional[str] = None
        self._session = session
        self._ssl = None if verify_ssl else False
        self._base_url = f"https://{host}"
        self._authenticated = False

    @property
    def is_receiver(self) -> bool:
        return self.device_mode == DEVICE_MODE_RECEIVER

    @property
    def is_transmitter(self) -> bool:
        return self.device_mode == DEVICE_MODE_TRANSMITTER

    async def login(self) -> None:
        """Authenticate and establish the cookie session.

        DM NVX auth: GET /userlogin.html to seed the TRACKID cookie, then
        POST credentials to the same path. On success the device sets 6
        cookies (AuthByPasswd, TRACKID, iv, tag, userid, userstr) which
        aiohttp's cookie jar stores/resends automatically from here on.
        """
        try:
            await self._session.get(
                f"{self._base_url}{LOGIN_PATH}",
                ssl=self._ssl,
                timeout=aiohttp.ClientTimeout(total=10),
            )
            async with self._session.post(
                f"{self._base_url}{LOGIN_PATH}",
                data={"login": self.username, "passwd": self.password},
                headers={
                    "Origin": self._base_url,
                    "Referer": f"{self._base_url}{LOGIN_PATH}",
                },
                ssl=self._ssl,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status != 200:
                    raise CrestronNVXAuthError(
                        f"Login to {self.host} failed with HTTP {response.status}"
                    )
        except TimeoutError as err:
            raise CrestronNVXConnectionError(f"Timeout connecting to {self.host}") from err
        except aiohttp.ClientError as err:
            raise CrestronNVXConnectionError(f"Error connecting to {self.host}: {err}") from err

        self._authenticated = True
        self.device_mode = await self.get_device_mode()

    async def logout(self) -> None:
        """End the session. Best-effort; errors are not fatal."""
        if not self._authenticated:
            return
        try:
            await self._session.get(
                f"{self._base_url}{LOGOUT_PATH}",
                ssl=self._ssl,
                timeout=aiohttp.ClientTimeout(total=10),
            )
        except (TimeoutError, aiohttp.ClientError):
            pass
        self._authenticated = False

    async def _request(
        self,
        path: str,
        method: str = "GET",
        json_body: Optional[dict] = None,
        timeout: int = 10,
        _retry: bool = True,
    ) -> Optional[dict]:
        """Make an authenticated request to /Device/<path>."""
        url = f"{self._base_url}/Device/{path}"
        try:
            async with self._session.request(
                method,
                url,
                json=json_body,
                ssl=self._ssl,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as response:
                if response.status == 403 and _retry:
                    _LOGGER.debug("Session expired for %s, re-authenticating", self.host)
                    await self.login()
                    return await self._request(
                        path, method, json_body, timeout=timeout, _retry=False
                    )
                if response.status != 200:
                    _LOGGER.error("Request to %s failed with HTTP %s", url, response.status)
                    return None
                return await response.json(content_type=None)
        except TimeoutError:
            _LOGGER.error("Timeout requesting %s", url)
            return None
        except aiohttp.ClientError as err:
            _LOGGER.error("Error requesting %s: %s", url, err)
            return None

    async def longpoll(self, timeout: int = 30) -> Optional[dict]:
        """Block until a property changes, or return None on timeout/error.

        The device's own long-poll window is ~19s; callers should loop this
        rather than treat a single call as a persistent connection.
        """
        data = await self._request(LONGPOLL_PATH.removeprefix("/Device/"), timeout=timeout)
        if data is None:
            return None
        if data.get("Device") == "Response Timeout":
            return None
        return data

    async def get_device_info(self) -> Optional[dict]:
        """Model, serial number, firmware version, MAC address."""
        data = await self._request("DeviceInfo")
        try:
            return data["Device"]["DeviceInfo"]
        except (KeyError, TypeError):
            return None

    async def get_device_mode(self) -> Optional[str]:
        """"Transmitter" or "Receiver", read from the device itself."""
        data = await self._request("DeviceSpecific/DeviceMode")
        try:
            return data["Device"]["DeviceSpecific"]["DeviceMode"]
        except (KeyError, TypeError):
            return None

    async def get_video_status(self) -> Optional[dict]:
        """Normalized video/HDCP status for this device's role.

        Transmitters report on their HDMI input (Inputs/0/Ports/0);
        receivers report on their HDMI output (Outputs/0/Ports/0). Only
        port index 0 exists on every model in the verified fleet.
        """
        if self.is_receiver:
            data = await self._request("AudioVideoInputOutput/Outputs/0/Ports/0")
            try:
                port = data["Device"]["AudioVideoInputOutput"]["Outputs"][0]["Ports"][0]
            except (KeyError, TypeError, IndexError):
                return None
            connected = port.get("IsSinkConnected", False)
        else:
            data = await self._request("AudioVideoInputOutput/Inputs/0/Ports/0")
            try:
                port = data["Device"]["AudioVideoInputOutput"]["Inputs"][0]["Ports"][0]
            except (KeyError, TypeError, IndexError):
                return None
            connected = port.get("IsSyncDetected", False)

        hdmi = port.get("Hdmi", {})
        return {
            "connected": connected,
            "horizontal_resolution": port.get("HorizontalResolution"),
            "vertical_resolution": port.get("VerticalResolution"),
            "frames_per_second": port.get("FramesPerSecond"),
            "hdcp_state": hdmi.get("HdcpState"),
        }

    async def get_ethernet_status(self) -> Optional[dict]:
        """Link status, IP address and MAC of the primary network adapter."""
        data = await self._request("Ethernet")
        try:
            adapter = data["Device"]["Ethernet"]["Adapters"][0]
        except (KeyError, TypeError, IndexError):
            return None
        try:
            ip_address = adapter["IPv4"]["Addresses"][0]["Address"]
        except (KeyError, TypeError, IndexError):
            ip_address = None
        return {
            "connected": adapter.get("LinkStatus", False),
            "ip_address": ip_address,
            "mac_address": adapter.get("MacAddress"),
        }

    async def get_discovered_streams(self) -> dict[str, dict]:
        """Network-wide map of {unique_id: stream_info} available to route to."""
        data = await self._request("DiscoveredStreams")
        try:
            return data["Device"]["DiscoveredStreams"]["Streams"]
        except (KeyError, TypeError):
            return {}

    async def get_current_route(self) -> Optional[dict]:
        """Current AvRouting route (VideoSource/AudioSource/UsbSource UIDs)."""
        data = await self._request("AvRouting/Routes/0")
        try:
            return data["Device"]["AvRouting"]["Routes"][0]
        except (KeyError, TypeError, IndexError):
            return None

    async def set_route(self, source_uid: str) -> bool:
        """Switch video, audio and USB together to the given DiscoveredStreams UID.

        This is the verified-working mechanism - confirmed live across three
        real source switches. Writing StreamReceive/MulticastAddress or
        StreamLocation directly either does nothing or leaves audio on the
        old source, because this receiver's audio is a separate breakaway
        subscription that only AvRouting knows how to keep in sync.
        """
        body = {
            "Device": {
                "AvRouting": {
                    "Routes": [
                        {
                            "VideoSource": source_uid,
                            "AudioSource": source_uid,
                            "UsbSource": source_uid,
                        }
                    ]
                }
            }
        }
        result = await self._request("AvRouting/Routes/0", method="POST", json_body=body)
        if result is None:
            return False
        try:
            status_id = result["Actions"][0]["Results"][0]["StatusId"]
        except (KeyError, TypeError, IndexError):
            return False
        return status_id == 0

    async def get_cec_input_message(self) -> Optional[str]:
        """Raw base64 CEC frame most recently received on the HDMI input."""
        data = await self._request("AudioVideoInputOutput/Inputs/0/Ports/0/Hdmi/ReceiveCecMessage")
        try:
            return data["Device"]["AudioVideoInputOutput"]["Inputs"][0]["Ports"][0]["Hdmi"][
                "ReceiveCecMessage"
            ]
        except (KeyError, TypeError, IndexError):
            return None


class CrestronNVXAPI:
    """Owns the shared HTTPS session/cookie jar and the devices on it."""

    def __init__(self, verify_ssl: bool = False) -> None:
        self.devices: dict[str, CrestronNVXDevice] = {}
        self._verify_ssl = verify_ssl
        # unsafe=True is required: aiohttp's default cookie jar refuses to
        # store cookies for bare IP-address hosts (no registrable domain),
        # which is exactly what every NVX device is addressed by.
        self._session = aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True))

    async def add_device(
        self, host: str, name: str, username: str, password: str
    ) -> CrestronNVXDevice:
        """Create, authenticate and register a device."""
        device = CrestronNVXDevice(
            host=host,
            username=username,
            password=password,
            session=self._session,
            verify_ssl=self._verify_ssl,
            name=name,
        )
        await device.login()
        self.devices[name] = device
        _LOGGER.info(
            "Added %s device: %s at %s", device.device_mode or "unknown", name, host
        )
        return device

    def get_device(self, name: str) -> Optional[CrestronNVXDevice]:
        return self.devices.get(name)

    async def close(self) -> None:
        for device in self.devices.values():
            await device.logout()
        await self._session.close()
