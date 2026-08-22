# Crestron NVX REST API Reference

This documents the real Crestron DM NVX REST API (the "CresNext" JSON
interface) as used by this integration. Every endpoint below was verified
against live hardware (DM-NVX-E30, DM-NVX-352, DM-NVX-350, DM-NVX-D30,
firmware 7.1.5259.00090), not just read from the docs.

Official reference: https://sdkcon78221.crestron.com/sdk/DM_NVX_REST_API/

## Authentication

HTTPS only (port 443). Devices normally use a self-signed certificate -
clients must be configured to skip verification unless a trusted cert has
been installed.

1. `GET /userlogin.html` - seeds a `TRACKID` cookie.
2. `POST /userlogin.html` with headers `Origin: https://<device-ip>` and
   `Referer: https://<device-ip>/userlogin.html`, and a URL-encoded body
   `login=<username>&passwd=<password>`.
3. On success (`200 OK`), the device sets 6 cookies: `AuthByPasswd`,
   `TRACKID`, `iv`, `tag`, `userid`, `userstr`. All 6 must be sent on every
   subsequent request. **`AuthByPasswd` rotates on every response** - update
   it from each response before the next request, or the session breaks.
4. `403 Forbidden` on any request means the session is invalid/expired -
   re-run the login flow.
5. `GET /logout` ends the session.

## Making requests

`GET /Device/<path>` returns the current value, wrapped in the object tree
matching the path: `GET /Device/DeviceInfo` returns
`{"Device": {"DeviceInfo": {...}}}`.

`POST /Device/<path>` with a JSON body shaped the same way sets values, e.g.
`POST /Device/Ethernet/HostName` with body
`{"Device": {"Ethernet": {"HostName": "MyDevice"}}}`. The response is:

```json
{
  "Actions": [{
    "Operation": "SetPartial",
    "TargetObject": "...",
    "Results": [{"Path": "...", "Property": "...", "StatusId": 0, "StatusInfo": "OK"}]
  }]
}
```

`StatusId`: negative = error, `0` = success, positive = informational (e.g.
reboot required).

Requesting a specific array index (e.g. `.../Outputs/0/Ports/0`) still
returns the array wrapper, just with a single element at that position -
arrays are never flattened to plain objects.

## Endpoints used by this integration

All paths below are relative to `/Device/`.

### `DeviceInfo` (GET only)
`Model`, `SerialNumber`, `DeviceVersion` (firmware), `MacAddress`, `Name`.

### `DeviceSpecific/DeviceMode` (GET, POST)
`"Transmitter"` or `"Receiver"` - read from the device itself rather than
trusted from user config, since some models are field-switchable.

### `AudioVideoInputOutput/Inputs/0/Ports/0` (transmitters)
Only port index 0 exists on every model tested. Top-level: `IsSyncDetected`
(bool), `HorizontalResolution`, `VerticalResolution`, `FramesPerSecond`.
Nested `Hdmi` object: `HdcpState` (string, e.g. `"Authenticated"`,
`"Non-HDCPSource"`), `IsSourceHdcpActive` (bool), `ReceiveCecMessage` /
`TransmitCecMessage` (see CEC section below).

### `AudioVideoInputOutput/Outputs/0/Ports/0` (receivers)
Same resolution fields, plus top-level `IsSinkConnected` (bool). Nested
`Hdmi`: `HdcpState`, `DisabledByHdcp`, `Transmitting`, `ReceiveCecMessage` /
`TransmitCecMessage`.

**No dedicated "audio detected" field exists anywhere in the API** -
confirmed absent on every port object checked. Not exposed by this
integration.

### `Ethernet` (GET, partial POST)
`Adapters[0].LinkStatus` (bool), `Adapters[0].MacAddress`,
`Adapters[0].IPv4.Addresses[0].Address`.

### `DiscoveredStreams` (GET only)
Network-wide map of every stream currently visible, keyed by `UniqueId`:
`{"<uuid>": {"SessionName": "...", "MulticastAddress": "...", "Resolution": "...", ...}}`.
`SessionName` matches the source transmitter's configured `Name`.

### `AvRouting/Routes/0` (GET, POST) - **the real source-switching mechanism**

This is the important one, and it was not obvious from the docs alone -
confirmed by live testing on real hardware:

- `POST .../StreamReceive/Streams/0/MulticastAddress` alone returns success
  but **does nothing** - the RTSP session never renegotiates.
- `POST .../StreamReceive/Streams/0/StreamLocation` (the RTSP URL) **does**
  switch video, but on a receiver with audio breakaway configured
  (`DeviceSpecific.AudioMode: "Insert"`), audio stays on the old source -
  it's a separate stream subscription StreamReceive doesn't touch.
- `POST AvRouting/Routes/0` with `VideoSource`, `AudioSource`, and
  `UsbSource` all set to a `DiscoveredStreams` `UniqueId` **switches
  everything together correctly**. Confirmed across multiple live source
  changes with visual + audio confirmation. **Use this, not StreamReceive
  directly.**

```json
POST /Device/AvRouting/Routes/0
{
  "Device": {
    "AvRouting": {
      "Routes": [{
        "VideoSource": "00000000-0000-4002-0054-040440c30b06",
        "AudioSource": "00000000-0000-4002-0054-040440c30b06",
        "UsbSource": "00000000-0000-4002-0054-040440c30b06"
      }]
    }
  }
}
```

### CEC - inbound listening, not outbound control

There is no `CecControl.Type` preset object on this firmware (a direct GET
returns `null`, despite appearing in some documentation). Raw CEC frames are
exposed via `Hdmi.ReceiveCecMessage` / `Hdmi.TransmitCecMessage` as plain
base64: `base64(header_byte + opcode [+ operand])`, no extra wrapping.
Confirmed by decoding real captured frames, e.g. a volume-up press on an
Apple TV remote (with its Volume Control setting on HDMI-CEC) produced bytes
`40 44 41`: header `0x40` (source `0x4` "Playback Device 1" = the Apple TV,
dest `0x0` "TV"), opcode `0x44` "User Control Pressed", operand `0x41`
"Volume Up".

This integration only *listens* for this traffic (via `/Device/Longpoll`,
below) on a transmitter's HDMI input, and turns it into a Home Assistant
event - it never writes to `TransmitCecMessage`.

Recognized opcodes:
| Bytes (after header) | Meaning | HA event |
|---|---|---|
| `0x04` | Image View On | `power_on` |
| `0x36` | Standby | `power_off` |
| `0x44 0x41` | User Control Pressed: Volume Up | `volume_up` |
| `0x44 0x42` | User Control Pressed: Volume Down | `volume_down` |
| `0x44 0x43` | User Control Pressed: Mute | `mute` |
| `0x45` | User Control Released (key-up) | ignored |

### `Longpoll` (GET, blocking)

`GET /Device/Longpoll` blocks (observed ~19s internal window) until any
property on the device changes, then returns immediately with the changed
subtree in the same `{"Device": {...}}` shape as a normal GET. If nothing
changes within the window, it returns `{"Device": "Response Timeout"}` with
`200 OK` - not an error, just "keep polling". This integration uses it in a
tight loop (no fixed interval) to catch CEC commands in near-real-time
without the latency or missed-repeat-press risk of fixed-interval polling.

## Not implemented / out of scope

- **Audio breakaway control** - switching a receiver's audio independently
  of video (`DeviceSpecific.AudioMode`, the secondary `StreamReceive` slot).
  `AvRouting` already keeps them in sync for the switching this integration
  does; manually decoupling them is a separate feature.
- **Outbound CEC control** (turning a display on/off, changing its volume
  from Home Assistant) - not requested; this integration is a CEC listener,
  not a CEC controller.
- **Transmitter multicast configuration** (`StreamTransmit`) - read/write
  support for changing what a transmitter sends isn't implemented; only
  receivers are switched.
