"""Crestron NVX API Client."""
import aiohttp
import asyncio
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

_LOGGER = logging.getLogger(__name__)


class CrestronNVXDevice:
    """Represents a Crestron NVX device (Transmitter or Receiver)."""

    def __init__(
        self,
        host: str,
        device_type: str,
        name: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        session: Optional[aiohttp.ClientSession] = None,
    ):
        """Initialize the NVX device."""
        self.host = host
        self.device_type = device_type  # "transmitter" or "receiver"
        self.name = name
        self.username = username
        self.password = password
        self._session = session
        self._own_session = session is None
        self.base_url = f"http://{host}/Device"
        
        # Status cache
        self._status_cache = {}
        self._last_update = None
        
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._own_session = True
        return self._session

    async def close(self):
        """Close the session if we own it."""
        if self._own_session and self._session:
            await self._session.close()
            self._session = None

    async def _make_request(
        self, 
        endpoint: str, 
        method: str = "GET",
        data: Optional[Dict] = None
    ) -> Optional[Dict]:
        """Make an API request to the NVX device."""
        url = f"{self.base_url}/{endpoint}"
        session = await self._get_session()
        
        auth = None
        if self.username and self.password:
            auth = aiohttp.BasicAuth(self.username, self.password)
        
        try:
            async with session.request(
                method, 
                url, 
                auth=auth,
                json=data,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    _LOGGER.error(
                        f"Request to {url} failed with status {response.status}"
                    )
                    return None
        except asyncio.TimeoutError:
            _LOGGER.error(f"Timeout connecting to {self.host}")
            return None
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Error connecting to {self.host}: {err}")
            return None

    async def get_video_status(self) -> Optional[Dict]:
        """Get video signal status."""
        data = await self._make_request("VideoStatus")
        if data:
            self._status_cache['video_status'] = data
            self._last_update = datetime.now()
        return data

    async def get_resolution(self) -> Optional[str]:
        """Get current video resolution."""
        status = await self.get_video_status()
        if status and 'Resolution' in status:
            return status['Resolution']
        return None

    async def get_signal_status(self) -> Optional[bool]:
        """Check if video signal is present."""
        status = await self.get_video_status()
        if status and 'SignalDetected' in status:
            return status['SignalDetected']
        return None

    async def get_hdcp_status(self) -> Optional[Dict]:
        """Get HDCP status."""
        return await self._make_request("HdcpStatus")

    async def get_audio_status(self) -> Optional[Dict]:
        """Get audio status."""
        return await self._make_request("AudioStatus")

    async def send_cec_command(self, command: str) -> bool:
        """Send a CEC command."""
        data = {"Command": command}
        result = await self._make_request("CEC", method="POST", data=data)
        return result is not None

    async def get_cec_status(self) -> Optional[Dict]:
        """Get CEC status."""
        return await self._make_request("CEC")

    async def get_subscriptions(self) -> Optional[List[Dict]]:
        """Get available stream subscriptions (for receivers)."""
        if self.device_type != "receiver":
            _LOGGER.warning(f"Device {self.name} is not a receiver")
            return None
        
        data = await self._make_request("Subscriptions")
        if data and 'Subscriptions' in data:
            return data['Subscriptions']
        return []

    async def subscribe_to_stream(self, stream_id: str) -> bool:
        """Subscribe receiver to a specific stream."""
        if self.device_type != "receiver":
            _LOGGER.warning(f"Device {self.name} is not a receiver")
            return False
        
        data = {"StreamId": stream_id}
        result = await self._make_request("Subscribe", method="POST", data=data)
        return result is not None

    async def get_device_info(self) -> Optional[Dict]:
        """Get device information."""
        return await self._make_request("DeviceInfo")

    async def get_network_status(self) -> Optional[Dict]:
        """Get network status."""
        return await self._make_request("NetworkStatus")

    async def set_multicast_address(self, address: str) -> bool:
        """Set multicast address for transmitter."""
        if self.device_type != "transmitter":
            _LOGGER.warning(f"Device {self.name} is not a transmitter")
            return False
        
        data = {"MulticastAddress": address}
        result = await self._make_request("Multicast", method="POST", data=data)
        return result is not None

    async def update_all_status(self) -> Dict[str, Any]:
        """Update all status information."""
        tasks = [
            self.get_video_status(),
            self.get_audio_status(),
            self.get_hdcp_status(),
            self.get_network_status(),
        ]
        
        if self.device_type == "receiver":
            tasks.append(self.get_subscriptions())
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return {
            'video_status': results[0] if not isinstance(results[0], Exception) else None,
            'audio_status': results[1] if not isinstance(results[1], Exception) else None,
            'hdcp_status': results[2] if not isinstance(results[2], Exception) else None,
            'network_status': results[3] if not isinstance(results[3], Exception) else None,
            'subscriptions': results[4] if len(results) > 4 and not isinstance(results[4], Exception) else None,
        }


class CrestronNVXAPI:
    """Main API handler for Crestron NVX devices."""

    def __init__(self):
        """Initialize the API handler."""
        self.devices: Dict[str, CrestronNVXDevice] = {}
        self._session: Optional[aiohttp.ClientSession] = None

    async def add_device(
        self,
        host: str,
        device_type: str,
        name: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> CrestronNVXDevice:
        """Add a new NVX device."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
        
        device = CrestronNVXDevice(
            host=host,
            device_type=device_type,
            name=name,
            username=username,
            password=password,
            session=self._session,
        )
        
        self.devices[name] = device
        _LOGGER.info(f"Added {device_type} device: {name} at {host}")
        return device

    async def remove_device(self, name: str):
        """Remove a device."""
        if name in self.devices:
            del self.devices[name]
            _LOGGER.info(f"Removed device: {name}")

    def get_device(self, name: str) -> Optional[CrestronNVXDevice]:
        """Get a device by name."""
        return self.devices.get(name)

    async def close(self):
        """Close all connections."""
        if self._session:
            await self._session.close()
            self._session = None
