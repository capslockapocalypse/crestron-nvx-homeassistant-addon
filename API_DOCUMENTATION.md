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
4. A request made with an invalid/expired session does **not** reliably get
   a clean `403 Forbidden` - confirmed live by logging out server-side and
   reusing the old cookies: the device returned `301 Moved Permanently` with
   `Location: /userlogin.html`. A client that auto-follows redirects (the
   default for most HTTP clients, including aiohttp) sees this as a plain
   `200 OK` containing the login page's HTML instead of JSON, never notices
   the session died, and never re-authenticates - every subsequent request
   then fails the same way forever. **Disable automatic redirect-following
   on these requests** and treat any of `301/302/303/307/308/403` as
   "re-run the login flow", not just `403`. This was the root cause of this
   integration not recovering after a device restarted or a session was
   otherwise invalidated - see `crestron_nvx_api.py`'s `_REAUTH_STATUSES`.
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
`Model`, `SerialNumber`, and `DeviceVersion` are cached on the device object
at login and surfaced on each device's Home Assistant device page (real
model like `"DM-NVX-E30"` rather than just its role, plus firmware/serial),
so it's obvious which physical unit you're looking at when there are
several.

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

### `Osd` (GET, partial POST) - not supported on every model

`Text` (string), `IsEnabled` (bool), plus device-configured `Location`,
`XPosition`/`YPosition`, `BackgroundTransparency`. **Not every model has an
OSD** - unsupported devices return the literal string
`"UNSUPPORTED PROPERTY, CHECK REST API!!!"` in place of the object on `GET
/Device/Osd`, rather than a normal HTTP error - confirmed live on a
DM-NVX-D30 and DM-NVX-E30. A DM-NVX-350 receiver, and even a DM-NVX-352
*while acting as a transmitter*, both returned real objects - OSD support
tracks whether a device has its own local HDMI output, not its
transmitter/receiver role. Support is checked once at login
(`osd_supported` on the device) and gates whether the `notify`/`number`
entities below are created at all, since there's no dedicated capability
flag for this in `DeviceCapabilities`.

**Read-after-write lag**: a `GET /Device/Osd` issued immediately after a
successful `POST` (`StatusId: 0`) can return the *previous* value - a real
device-side propagation delay, confirmed live (the actual on-screen text
did update correctly; only the immediate follow-up read lagged by about one
write cycle). Not an issue in practice since this integration never reads
back after writing, but worth knowing if debugging via curl.

```json
POST /Device/Osd
{"Device": {"Osd": {"Text": "Source: Laptop", "IsEnabled": true}}}
```

This integration exposes it as a `notify` entity (any text, via
`notify.send_message`) that auto-clears itself via a Home Assistant-side
timer after `number.<name>_osd_display_duration` seconds (a setting that
lives entirely in this integration, not on the device) - see README.md.

### `TestPatternConfig` (GET, POST) - transmitter-only

`Outputs/Output1/CurrentTestPattern` (string) and `TestPatternsSupported`
(array of the valid values for it, e.g. `"Off"`, `"SMPTE ColorBars"`,
`"Black"`, `"White"`, `"Vertical Lines"`, `"Grid"`, `"Color Bars"`,
`"Gray Gradient"`, `"RGB Gradient"`, `"Frequency Adjust"`). Confirmed live on
a DM-NVX-E30 transmitter: writing a pattern overrides whatever's on the
HDMI input immediately (no read-after-write lag), and `"Off"` cleanly
restores the real source. Confirmed absent on a receiver (`GET
/Device/TestPatternConfig` returns `{"Device": {}}`, the same "not present"
shape used elsewhere in this API) - this integration only creates the
select entity for transmitters that report a non-empty
`TestPatternsSupported`, cached once at login as `device.test_patterns`.

### `AudioVideoInputOutput/Outputs/0/Ports/0/Hdmi/IsOutputDisabled` (GET, POST) - receivers

Force-blanks the physical HDMI output independent of `AvRouting` - the
routed source is preserved and resumes as soon as the output is
re-enabled. Confirmed live on a receiver: `Transmitting` flips to `false`
while disabled. **Has the same read-after-write lag as `Osd`** - an
immediate readback after a successful (`StatusId: 0`) write returned the
*previous* value; a write is reliably reflected after a couple of seconds,
not immediately.

### `Preview` (GET only) - live JPEG snapshot

`ImageList.Image{1,2,3}` each describe a JPEG at 135/270/540px width, served
from a **separate, non-`/Device/` path**: `https://<host>/preview/preview_
{135,270,540}px.jpeg`. Confirmed live on both a transmitter and a receiver.
Requires the same session cookies as everything else (confirmed `401`
without them) - a stale session redirects the same way `/Device/` requests
do (see the Authentication section above), so fetching this needs the same
reauth-on-redirect handling, not just the JSON-shaped one `_request` uses.
Presence is checked once at login (`Preview` returns `{"Device": {}}` on
unsupported models, cached as `device.preview_supported`) since there's no
dedicated capability flag for it. This integration exposes it as an opt-in
`camera` entity (off by default - see README.md) rather than always-on,
since it's a heavier feature than the small JSON status calls everything
else here makes.

### Output/stream "Volume" fields - investigated, not exposed

Two different fields both look like a general HDMI-output volume control
and are not:

- `AudioVideoInputOutput/Outputs/0/Ports/0/Audio/Volume` - accepted an
  out-of-range write (`9999`) with `StatusId: 0 "OK"` but the value never
  changed on readback. Appears to be a no-op/read-only field on this
  firmware rather than a real gain control.
- `StreamReceive/Streams/N/Volume` - unlike the field above, this one
  actually validates: writing `9999` correctly returned `StatusId: -1
  "Value out of range"`. But every value tried *other than the current one*
  (`100`, `50`, `1`, `-1`, `-80`, `-81`) was rejected the same way, even
  though the field isn't at a documented boundary - it's gated by something
  not yet understood, most likely tied to `DeviceSpecific.AudioMode`
  (`"Insert"` on the receiver tested) and/or the per-stream `AudioMode`
  (`"Automatic"`) rather than being freely adjustable. This is the same
  "other, lower-level audio-breakaway mechanism" already called out as out
  of scope below - a real volume entity here would need a dedicated
  investigation into what state makes it writable, not a quick field
  mapping.

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
  for the cases this integration targets. This is also where the
  `StreamReceive/Streams/N/Volume` field investigated above lives - see
  "Output/stream 'Volume' fields" for why it wasn't turned into an entity.
- **Outbound CEC control** (turning a display on/off, changing its volume
  from Home Assistant) - not requested; this integration is a CEC listener,
  not a CEC controller.
- **Transmitter multicast configuration** (`StreamTransmit`) - read/write
  support for changing what a transmitter sends isn't implemented.
- **USB routing control** - `UsbSource`/`IsUsbFollowsVideoEnabled` exist and
  are readable, but there's no dedicated entity to route USB independently
  of video (unlike audio, which got one at the user's request).
