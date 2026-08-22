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

### `DeviceCapabilities/PortConfig` (GET only)
`NumberOfHdmiInputs`, `NumberOfHdmiOutputs`, `NumberOfDmInputs`,
`NumberOfEthernetAdapters` - the authoritative source for how many physical
ports a device has. This varies a lot even within one role: a DM-NVX-E30
transmitter has 1 HDMI input, a DM-NVX-352 transmitter has 2; a DM-NVX-D30
receiver has 0 local HDMI inputs, a DM-NVX-350 receiver has 2. Read once at
login and used to decide whether input-switching select entities make sense
for a given device at all.

### `DeviceSpecific/VideoSource` (GET, POST)
The source-mode selector: `"Stream"` (receive the network route configured
in `AvRouting`) or `"Input1"` / `"Input2"` / etc. (a local HDMI input).
Confirmed live: writing an `InputN` value switches a receiver to that local
input; writing `"Stream"` switches it back to the network route *without*
needing to re-write `AvRouting` - the existing route is remembered and
resumed. `DeviceSpecific/ActiveVideoSource` (GET only) tracks the same value
once it's been explicitly written, but the two fields aren't reliably in
sync until then - a single-HDMI-input transmitter observed `VideoSource:
None, ActiveVideoSource: "Input1"` (nothing to explicitly select on a
single-input device), while a two-input transmitter observed `VideoSource:
"Input1", ActiveVideoSource: None` (selection exists, but no signal is
currently present on it). For the multi-input case this integration
actually creates an entity for, `VideoSource` reads reliably, so that's the
field used for both "what's currently selected" and for writing. Same field
name is used for both a receiver's local-vs-stream switch and a multi-input
transmitter's input-select - on a transmitter, `"Stream"` isn't a valid
value, only `InputN`.

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
- `POST AvRouting/Routes/0` with `VideoSource`, `AudioSource`, and/or
  `UsbSource` set to a `DiscoveredStreams` `UniqueId` **switches sources
  correctly** - confirmed across multiple live source changes with visual +
  audio confirmation. **Use this, not StreamReceive directly.**
- Every write response here comes back `"Operation": "SetPartial"`, and
  it's true to its name: POSTing only one of the three fields (e.g. just
  `AudioSource`) leaves the other two untouched - confirmed live. This is
  how the integration implements independent audio routing.

```json
POST /Device/AvRouting/Routes/0
{"Device": {"AvRouting": {"Routes": [{"VideoSource": "00000000-0000-4002-0054-040440c30b06"}]}}}
```

Setting all three fields to an **empty string** (`""`) clears the route -
confirmed live to cleanly blank the output (no video/audio routed) rather
than erroring or leaving the last frame frozen. This is how the integration
implements the select entity's "Off" option - and unlike a normal source
switch, "Off" always clears all three regardless of the follow-video
setting below, since a deliberate blank shouldn't leave old audio playing.

### `AvRouting/RouteControl` (GET, POST)

`IsSecondaryAudioFollowsVideoEnabled` and `IsUsbFollowsVideoEnabled` (bools,
both default `true` on every receiver checked), plus `IsLayer3Enabled` and
`IsChangeUsbRemoteDeviceEnabled`. Confirmed live: with
`IsSecondaryAudioFollowsVideoEnabled` on, POSTing only `VideoSource` to
`AvRouting/Routes/0` is enough - `AudioSource` (and `UsbSource`, via its own
flag) update on the device's own initiative. This is the real mechanism
behind "audio follows video": the integration's main video-source select
only ever writes `VideoSource`, and lets this flag decide whether audio
tags along. Turning the flag off (via the `switch.<name>_audio_follows_video`
entity) is what makes the independent `select.<name>_audio_source` entity
meaningful - toggling it back on also immediately re-syncs `AudioSource` to
match the current `VideoSource`, since the flag only affects *future* video
switches, not retroactively.

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

- **`DeviceSpecific.AudioMode` / the secondary `StreamReceive` slot** - the
  *other*, lower-level audio-breakaway mechanism (distinct from
  `AvRouting`'s `AudioSource`/`RouteControl`, which this integration does
  use). Not exposed - `AvRouting` already covers independent audio routing
  for the cases this integration targets.
- **Outbound CEC control** (turning a display on/off, changing its volume
  from Home Assistant) - not requested; this integration is a CEC listener,
  not a CEC controller.
- **Transmitter multicast configuration** (`StreamTransmit`) - read/write
  support for changing what a transmitter sends isn't implemented.
- **USB routing control** - `UsbSource`/`IsUsbFollowsVideoEnabled` exist and
  are readable, but there's no dedicated entity to route USB independently
  of video (unlike audio, which got one at the user's request).
