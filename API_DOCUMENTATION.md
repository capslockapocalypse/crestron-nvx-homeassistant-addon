# Crestron NVX REST API Integration Guide

This document details the Crestron NVX REST API endpoints used by this integration.

## Base URL Structure

All API calls are made to:
```
http://<device_ip>/Device/<endpoint>
```

## Authentication

If authentication is enabled on the NVX device, use HTTP Basic Authentication:
```
Authorization: Basic base64(username:password)
```

## API Endpoints Reference

### Device Information

#### Get Device Info
```http
GET /Device/DeviceInfo
```

**Response**:
```json
{
  "ModelName": "DM-NVX-350",
  "SerialNumber": "12345678",
  "FirmwareVersion": "1.6.0.2041",
  "MacAddress": "00:11:22:33:44:55",
  "DeviceType": "Receiver"
}
```

### Video Status

#### Get Video Status
```http
GET /Device/VideoStatus
```

**Response**:
```json
{
  "SignalDetected": true,
  "Resolution": "1920x1080@60",
  "ColorSpace": "RGB",
  "ColorDepth": "8-bit",
  "Framerate": 60.0,
  "InterlaceMode": "Progressive",
  "PixelClock": 148.5
}
```

**Fields**:
- `SignalDetected` (boolean): Whether video signal is present
- `Resolution` (string): Current video resolution
- `ColorSpace` (string): RGB, YUV444, YUV422, YUV420
- `ColorDepth` (string): 8-bit, 10-bit, 12-bit
- `Framerate` (float): Frames per second
- `InterlaceMode` (string): Progressive or Interlaced

### Audio Status

#### Get Audio Status
```http
GET /Device/AudioStatus
```

**Response**:
```json
{
  "AudioDetected": true,
  "Format": "PCM",
  "SampleRate": 48000,
  "Channels": 2,
  "BitDepth": 16
}
```

**Fields**:
- `AudioDetected` (boolean): Whether audio signal is present
- `Format` (string): Audio format (PCM, Dolby, DTS, etc.)
- `SampleRate` (integer): Audio sample rate in Hz
- `Channels` (integer): Number of audio channels
- `BitDepth` (integer): Audio bit depth

### HDCP Status

#### Get HDCP Status
```http
GET /Device/HdcpStatus
```

**Response**:
```json
{
  "Active": true,
  "Version": "2.2",
  "Encrypted": true
}
```

**Fields**:
- `Active` (boolean): Whether HDCP is active
- `Version` (string): HDCP version (1.4, 2.2, 2.3)
- `Encrypted` (boolean): Whether content is encrypted

### Network Status

#### Get Network Status
```http
GET /Device/NetworkStatus
```

**Response**:
```json
{
  "Connected": true,
  "IPAddress": "192.168.1.100",
  "SubnetMask": "255.255.255.0",
  "Gateway": "192.168.1.1",
  "LinkSpeed": "1000 Mbps",
  "DHCPEnabled": true
}
```

### Stream Management (Receivers)

#### Get Available Subscriptions
```http
GET /Device/Subscriptions
```

**Response**:
```json
{
  "Subscriptions": [
    {
      "Id": "stream-001",
      "Name": "Conference Room TX",
      "StreamId": "239.1.1.100",
      "MulticastAddress": "239.1.1.100:5004",
      "Active": false,
      "Available": true
    },
    {
      "Id": "stream-002",
      "Name": "Laptop TX",
      "StreamId": "239.1.1.101",
      "MulticastAddress": "239.1.1.101:5004",
      "Active": true,
      "Available": true
    }
  ]
}
```

**Fields**:
- `Id` (string): Unique subscription identifier
- `Name` (string): Friendly name of the stream source
- `StreamId` (string): Multicast address or stream identifier
- `MulticastAddress` (string): Full multicast address with port
- `Active` (boolean): Whether this subscription is currently active
- `Available` (boolean): Whether this stream is available

#### Subscribe to Stream
```http
POST /Device/Subscribe
Content-Type: application/json

{
  "StreamId": "239.1.1.101"
}
```

**Request Body**:
- `StreamId` (string): The stream ID or multicast address to subscribe to

**Response**:
```json
{
  "Success": true,
  "Message": "Successfully subscribed to stream"
}
```

#### Unsubscribe from Current Stream
```http
POST /Device/Unsubscribe
```

**Response**:
```json
{
  "Success": true,
  "Message": "Successfully unsubscribed"
}
```

### CEC Control

#### Get CEC Status
```http
GET /Device/CEC
```

**Response**:
```json
{
  "Enabled": true,
  "DeviceConnected": true,
  "PowerState": "On",
  "VolumeLevel": 50,
  "Muted": false
}
```

#### Send CEC Command
```http
POST /Device/CEC
Content-Type: application/json

{
  "Command": "ImageOn"
}
```

**Common CEC Commands**:
- `ImageOn` - Power on display
- `Standby` - Power off display
- `VolumeUp` - Increase volume
- `VolumeDown` - Decrease volume
- `Mute` - Toggle mute
- `ActiveSource` - Make this device active source
- `MenuOn` - Open device menu
- `MenuOff` - Close device menu

**Response**:
```json
{
  "Success": true,
  "CommandSent": "ImageOn"
}
```

### Transmitter-Specific Endpoints

#### Get Multicast Configuration
```http
GET /Device/Multicast
```

**Response**:
```json
{
  "MulticastAddress": "239.1.1.100",
  "Port": 5004,
  "TTL": 32,
  "Enabled": true
}
```

#### Set Multicast Address
```http
POST /Device/Multicast
Content-Type: application/json

{
  "MulticastAddress": "239.1.1.100",
  "Port": 5004,
  "TTL": 32
}
```

## Error Responses

All endpoints may return error responses in the following format:

```json
{
  "Error": "Error message description",
  "Code": 400,
  "Details": "Additional error details"
}
```

**Common HTTP Status Codes**:
- `200 OK` - Request successful
- `400 Bad Request` - Invalid request parameters
- `401 Unauthorized` - Authentication required or failed
- `403 Forbidden` - Access denied
- `404 Not Found` - Endpoint or resource not found
- `500 Internal Server Error` - Device error
- `503 Service Unavailable` - Device temporarily unavailable

## Rate Limiting

Crestron NVX devices may implement rate limiting. Recommended polling interval:
- Normal status updates: 30-60 seconds
- During active operation: 10-15 seconds
- Maximum: No more than 1 request per second per endpoint

## Best Practices

### Efficient Polling

1. **Batch Requests**: If possible, combine multiple status checks
2. **Cache Results**: Store status locally and only refresh when needed
3. **Event-Driven**: Update only when state changes are likely
4. **Exponential Backoff**: If a device becomes unavailable, increase retry interval

### Error Handling

1. **Timeout**: Set appropriate timeouts (recommended: 10 seconds)
2. **Retry Logic**: Implement retry with exponential backoff
3. **Graceful Degradation**: Continue operation with cached data if device unavailable
4. **Logging**: Log errors for debugging but don't spam logs

### Connection Management

1. **Keep-Alive**: Use persistent connections when possible
2. **Connection Pool**: Reuse HTTP connections
3. **Session Management**: Maintain authentication sessions

## Example Python Implementation

```python
import aiohttp
import asyncio

class CrestronNVXClient:
    def __init__(self, host, username=None, password=None):
        self.host = host
        self.base_url = f"http://{host}/Device"
        self.auth = None
        if username and password:
            self.auth = aiohttp.BasicAuth(username, password)
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()
    
    async def get_video_status(self):
        async with self.session.get(
            f"{self.base_url}/VideoStatus",
            auth=self.auth,
            timeout=aiohttp.ClientTimeout(total=10)
        ) as response:
            if response.status == 200:
                return await response.json()
            else:
                raise Exception(f"HTTP {response.status}")
    
    async def subscribe_to_stream(self, stream_id):
        async with self.session.post(
            f"{self.base_url}/Subscribe",
            auth=self.auth,
            json={"StreamId": stream_id},
            timeout=aiohttp.ClientTimeout(total=10)
        ) as response:
            return response.status == 200

# Usage
async def main():
    async with CrestronNVXClient("192.168.1.100", "admin", "password") as client:
        status = await client.get_video_status()
        print(f"Resolution: {status['Resolution']}")
        
        # Switch stream
        await client.subscribe_to_stream("239.1.1.101")

asyncio.run(main())
```

## Device Compatibility

This API specification is based on:
- Crestron DM-NVX-350 Series
- Crestron DM-NVX-D30 Series
- Firmware version 1.6.0 and later

Specific endpoints and response formats may vary by model and firmware version. Always test with your specific hardware.

## Additional Resources

- [Crestron NVX Product Page](https://www.crestron.com/Products/Video/Video-Distribution-Routing-Switching/Video-Over-IP-Solutions)
- [Crestron REST API Documentation](https://www.crestron.com/getmedia/xxxx)
- [Home Assistant Integration Development](https://developers.home-assistant.io/)
