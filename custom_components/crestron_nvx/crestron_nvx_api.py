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

# A stale/expired session doesn't get a clean 403 like the docs say - confirmed
# live by logging out server-side and reusing the old cookies: the device
# returns "301 Moved Permanently" / "Location: /userlogin.html" instead. If
# that redirect is auto-followed (aiohttp's default), the response looks like
# a normal 200 containing the login page's HTML rather than JSON, the session
# never gets renewed, and every request fails the same way forever - this is
# why the integration previously wouldn't recover after a disconnect.
# Redirects must be disabled per-request (see _request) and treated the same
# as 403 here.
_REAUTH_STATUSES = frozenset({301, 302, 303, 307, 308, 403})


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
        self.hdmi_inputs = 0
        self.hdmi_outputs = 0
        self.osd_supported = False
        self.test_patterns: list[str] = []
        self.preview_supported = False
        self.model: Optional[str] = None
        self.serial_number: Optional[str] = None
        self.firmware_version: Optional[str] = None
        # Not a device-side setting - purely how long this integration
        # leaves OSD text on screen before auto-clearing it. Mutated
        # directly by number.py's OSD Display Duration entity.
        self.osd_display_seconds = 5
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
        await self._load_port_config()
        self.osd_supported = (await self.get_osd()) is not None
        await self._load_test_patterns()
        await self._load_preview_supported()
        await self._load_device_info()

    async def _load_device_info(self) -> None:
        """Cache Model/SerialNumber/DeviceVersion - static for the device's lifetime."""
        info = await self.get_device_info()
        if not info:
            return
        self.model = info.get("Model")
        self.serial_number = info.get("SerialNumber")
        self.firmware_version = info.get("DeviceVersion")

    async def _load_port_config(self) -> None:
        """Cache HDMI input/output counts - static for the device's lifetime.

        Port count varies a lot across models even within one role (e.g. a
        DM-NVX-352 transmitter has 2 HDMI inputs, a DM-NVX-E30 has 1), so
        this is read once here rather than assumed, and used by entity
        setup to decide whether input-switching entities make sense at all.
        """
        data = await self._request("DeviceCapabilities/PortConfig")
        try:
            port_config = data["Device"]["DeviceCapabilities"]["PortConfig"]
        except (KeyError, TypeError):
            return
        self.hdmi_inputs = port_config.get("NumberOfHdmiInputs", 0)
        self.hdmi_outputs = port_config.get("NumberOfHdmiOutputs", 0)

    async def _load_test_patterns(self) -> None:
        """Cache supported test pattern names - a transmitter-only feature.

        Receivers return an empty {"Device": {}} for this path - confirmed
        live - so an empty list here just means the device doesn't have it,
        same as the missing-object convention used elsewhere in this API.
        """
        data = await self._request("TestPatternConfig")
        try:
            self.test_patterns = data["Device"]["TestPatternConfig"]["TestPatternsSupported"]
        except (KeyError, TypeError):
            self.test_patterns = []

    async def _load_preview_supported(self) -> None:
        """Cache whether this device exposes the /preview JPEG snapshot feature."""
        data = await self._request("Preview")
        try:
            preview = data["Device"]["Preview"]
        except (KeyError, TypeError):
            preview = None
        self.preview_supported = bool(preview)

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
                allow_redirects=False,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as response:
                if response.status in _REAUTH_STATUSES and _retry:
                    _LOGGER.debug(
                        "Session expired for %s (HTTP %s), re-authenticating",
                        self.host,
                        response.status,
                    )
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
            # Only meaningful on receivers - absent (None) on a transmitter's
            # HDMI input, which has no IsOutputDisabled field at all.
            "output_disabled": hdmi.get("IsOutputDisabled"),
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
        """Switch video to the given DiscoveredStreams UID.

        Deliberately writes VideoSource only. Audio/USB following is the
        device's own job (AvRouting/RouteControl's
        IsSecondaryAudioFollowsVideoEnabled / IsUsbFollowsVideoEnabled) -
        confirmed live that with the audio flag on, writing VideoSource
        alone is enough for AudioSource to update on its own. Explicitly
        writing AudioSource here as well - which is what earlier versions
        of this method did - would fight anyone who's turned audio-follow
        off to route audio independently via set_audio_source().
        """
        body = {
            "Device": {
                "AvRouting": {
                    "Routes": [
                        {
                            "VideoSource": source_uid,
                        }
                    ]
                }
            }
        }
        return self._post_ok(await self._request("AvRouting/Routes/0", method="POST", json_body=body))

    async def set_route_off(self) -> bool:
        """Clear video, audio and USB together - confirmed live to blank the output cleanly.

        Unlike set_route(), this always clears all three regardless of the
        audio-follows-video setting: "Off" is a deliberate full blank, not a
        source switch, so lingering independent audio on the old source
        would be surprising.
        """
        body = {
            "Device": {
                "AvRouting": {
                    "Routes": [{"VideoSource": "", "AudioSource": "", "UsbSource": ""}]
                }
            }
        }
        return self._post_ok(await self._request("AvRouting/Routes/0", method="POST", json_body=body))

    async def get_route_control(self) -> Optional[dict]:
        """AvRouting-wide flags, notably IsSecondaryAudioFollowsVideoEnabled."""
        data = await self._request("AvRouting/RouteControl")
        try:
            return data["Device"]["AvRouting"]["RouteControl"]
        except (KeyError, TypeError):
            return None

    async def set_audio_follows_video(self, enabled: bool) -> bool:
        """Toggle whether AudioSource auto-tracks VideoSource on future switches.

        When turning this on, also immediately syncs AudioSource to the
        current VideoSource - the flag only affects future video switches,
        so without this an already-independent audio source would keep
        playing until the next video change.
        """
        body = {
            "Device": {
                "AvRouting": {"RouteControl": {"IsSecondaryAudioFollowsVideoEnabled": enabled}}
            }
        }
        ok = self._post_ok(await self._request("AvRouting/RouteControl", method="POST", json_body=body))
        if ok and enabled:
            route = await self.get_current_route()
            video_uid = (route or {}).get("VideoSource")
            if video_uid:
                ok = await self.set_audio_source(video_uid)
        return ok

    async def set_audio_source(self, source_uid: str) -> bool:
        """Route audio only to the given DiscoveredStreams UID, independent of video."""
        body = {"Device": {"AvRouting": {"Routes": [{"AudioSource": source_uid}]}}}
        return self._post_ok(await self._request("AvRouting/Routes/0", method="POST", json_body=body))

    async def get_device_specific(self) -> Optional[dict]:
        """DeviceSpecific object - VideoSource/ActiveVideoSource used for HDMI input switching."""
        data = await self._request("DeviceSpecific")
        try:
            return data["Device"]["DeviceSpecific"]
        except (KeyError, TypeError):
            return None

    async def set_video_source(self, value: str) -> bool:
        """Set DeviceSpecific.VideoSource - e.g. "Stream", "Input1", "Input2".

        Used both for a receiver's local-HDMI-vs-stream switch and a
        multi-input transmitter's HDMI input switch - same field either way.
        """
        body = {"Device": {"DeviceSpecific": {"VideoSource": value}}}
        return self._post_ok(await self._request("DeviceSpecific", method="POST", json_body=body))

    async def get_osd(self) -> Optional[dict]:
        """OSD state (Text, IsEnabled, Location, ...), or None if unsupported.

        Not every model has an OSD - unsupported devices return the literal
        string "UNSUPPORTED PROPERTY, CHECK REST API!!!" in place of the
        object rather than a normal error, so a dict/non-dict check is what
        distinguishes "supported but empty" from "not supported at all".
        """
        data = await self._request("Osd")
        try:
            osd = data["Device"]["Osd"]
        except (KeyError, TypeError):
            return None
        return osd if isinstance(osd, dict) else None

    async def set_osd(self, *, text: Optional[str] = None, enabled: Optional[bool] = None) -> bool:
        """Set OSD text and/or enabled state - only the given fields are written."""
        fields = {}
        if text is not None:
            fields["Text"] = text
        if enabled is not None:
            fields["IsEnabled"] = enabled
        if not fields:
            return True
        body = {"Device": {"Osd": fields}}
        return self._post_ok(await self._request("Osd", method="POST", json_body=body))

    async def get_test_pattern(self) -> Optional[str]:
        """Currently active test pattern on Output1, or None if unsupported/unknown."""
        data = await self._request("TestPatternConfig/Outputs/Output1/CurrentTestPattern")
        try:
            return data["Device"]["TestPatternConfig"]["Outputs"]["Output1"]["CurrentTestPattern"]
        except (KeyError, TypeError):
            return None

    async def set_test_pattern(self, pattern: str) -> bool:
        """Set the active test pattern on Output1 - "Off" restores the real source.

        Confirmed live on a DM-NVX-E30 transmitter: applies immediately (no
        read-after-write lag like Osd) and cleanly reverts.
        """
        body = {
            "Device": {
                "TestPatternConfig": {"Outputs": {"Output1": {"CurrentTestPattern": pattern}}}
            }
        }
        return self._post_ok(
            await self._request(
                "TestPatternConfig/Outputs/Output1/CurrentTestPattern",
                method="POST",
                json_body=body,
            )
        )

    async def set_output_disabled(self, disabled: bool) -> bool:
        """Force-disable (blank) or re-enable a receiver's physical HDMI output.

        Independent of AvRouting - this blanks the output itself rather than
        clearing the routed source underneath, so the route is preserved and
        resumes as soon as the output is re-enabled. Confirmed live on a
        receiver: the write is accepted immediately but takes a couple of
        seconds to actually propagate (same read-after-write lag as Osd) -
        an immediate readback can still show the old state.
        """
        body = {
            "Device": {
                "AudioVideoInputOutput": {
                    "Outputs": [{"Ports": [{"Hdmi": {"IsOutputDisabled": disabled}}]}]
                }
            }
        }
        return self._post_ok(
            await self._request(
                "AudioVideoInputOutput/Outputs/0/Ports/0/Hdmi/IsOutputDisabled",
                method="POST",
                json_body=body,
            )
        )

    async def get_preview_image(self, size: str = "540px") -> Optional[bytes]:
        """Fetch a JPEG snapshot of what this device currently shows.

        Not under /Device/ like everything else - it's a plain authenticated
        file at /preview/preview_<size>.jpeg on the same cookie session.
        Confirmed live: 401 without valid session cookies, and a stale
        session redirects to the login page the same way /Device/ requests
        do (see _REAUTH_STATUSES on _request), so the same handling applies
        here rather than reusing _request itself, which is JSON-only.
        """
        url = f"{self._base_url}/preview/preview_{size}.jpeg"
        for attempt in (1, 2):
            try:
                async with self._session.get(
                    url,
                    ssl=self._ssl,
                    allow_redirects=False,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status in _REAUTH_STATUSES and attempt == 1:
                        await self.login()
                        continue
                    if response.status != 200:
                        return None
                    return await response.read()
            except TimeoutError:
                _LOGGER.error("Timeout fetching preview image for %s", self.host)
                return None
            except aiohttp.ClientError as err:
                _LOGGER.error("Error fetching preview image for %s: %s", self.host, err)
                return None
        return None

    @staticmethod
    def _post_ok(result: Optional[dict]) -> bool:
        try:
            return result["Actions"][0]["Results"][0]["StatusId"] == 0
        except (KeyError, TypeError, IndexError):
            return False

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
