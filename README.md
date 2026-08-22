# Crestron NVX Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub release](https://img.shields.io/github/release/capslockapocalypse/crestron-nvx-homeassistant-addon.svg)](https://github.com/capslockapocalypse/crestron-nvx-homeassistant-addon/releases)
[![License](https://img.shields.io/github/license/capslockapocalypse/crestron-nvx-homeassistant-addon.svg)](LICENSE)

A Home Assistant integration for Crestron DM NVX AV-over-IP transmitters and
receivers, built and verified against the real DM NVX REST API on live
hardware (DM-NVX-E30, DM-NVX-352, DM-NVX-350, DM-NVX-D30). See
[API_DOCUMENTATION.md](API_DOCUMENTATION.md) for the full endpoint reference,
including a couple of things that aren't obvious from Crestron's own docs
(the real source-switching mechanism, and the real CEC frame format).

## Features

### All devices
- Video resolution, HDMI signal/sink status, HDCP state, and network status
  sensors, polled on a configurable interval.

### Receivers
- **Stream Source** select entity - switches video, audio, and USB together
  by routing to a source discovered elsewhere on the NVX network.

### Transmitters
- **CEC Command** event entity - listens for CEC commands a connected source
  device sends toward the display (e.g. an Apple TV, with its Volume Control
  setting on HDMI-CEC, sending volume/mute/power from its remote) and fires
  a Home Assistant event (`power_on`, `power_off`, `volume_up`,
  `volume_down`, `mute`) that automations can trigger on. This is a
  **listener**, not a controller - nothing is sent to the display.

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant → Integrations
2. Three dots (top right) → Custom repositories
3. Add `https://github.com/capslockapocalypse/crestron-nvx-homeassistant-addon`, category "Integration"
4. Find "Crestron NVX" in HACS and download it
5. Restart Home Assistant

### Manual

1. Copy `custom_components/crestron_nvx` into your `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

Via the UI only (**Settings → Devices & Services → Add Integration →
Crestron NVX**) - there is no YAML configuration. One device per config
entry:

- **Device Name** - friendly name, used for entity naming
- **IP Address or Hostname**
- **Username** / **Password**
- **Verify SSL Certificate** - leave off unless you've installed a trusted
  cert on the device (they ship with self-signed certs)
- **Update Interval** - status polling interval in seconds (default 30)

Transmitter vs. receiver role is **detected automatically** from the device
during setup - there's no manual selector, so it can't be misconfigured.

## Entities

### Sensors (all devices)
- `sensor.<name>_resolution` - e.g. `"1920x1080@60"`
- `sensor.<name>_signal_detected` (transmitters) / `sensor.<name>_sink_connected` (receivers)
- `sensor.<name>_hdcp_state` - the device's real HDCP state string (e.g.
  `Authenticated`, `Non-HDCPSource`, `NoHDCPReceiverInDownstream`) rather
  than a flattened active/inactive
- `sensor.<name>_network_status` - connected/disconnected, with `ip_address` attribute

### Select (receivers only)
- `select.<name>_stream_source` - options are every source currently
  discovered on the NVX network; selecting one switches video, audio, and
  USB together

### Event (transmitters only)
- `event.<name>_cec_command` - fires `power_on` / `power_off` / `volume_up`
  / `volume_down` / `mute` when the connected source sends the matching CEC
  command

## Automation example

Trigger off the CEC event entity to react to a real Apple TV remote press:

```yaml
automation:
  - alias: "Apple TV volume up -> living room speaker"
    trigger:
      - platform: event
        event_type: state_changed
        event_data: {}
    # Simpler in the UI: Settings -> Automations -> Add -> choose a Device
    # Trigger on the "CEC Command" entity and pick the event type directly.
    condition: []
    action:
      - service: media_player.volume_up
        target:
          entity_id: media_player.living_room_speaker
```

(The UI-based device trigger picker on the event entity is the easiest way
to build this - it lists `power_on`/`power_off`/`volume_up`/`volume_down`/`mute`
directly.)

Switch a receiver's source:

```yaml
automation:
  - alias: "Meeting starts -> switch projector to laptop"
    trigger:
      - platform: calendar
        event: start
        entity_id: calendar.meeting_room
    action:
      - service: select.select_option
        target:
          entity_id: select.bog_proj_dec_stream_source
        data:
          option: "BOG-PC-ENC"
```

## Troubleshooting

**Device won't connect / login fails** - the real API is HTTPS-only. Confirm
you can reach `https://<device-ip>/userlogin.html` in a browser (accepting
the self-signed cert warning). If auth isn't enabled on the device yet,
enable it first - there's no unauthenticated fallback.

**No sources in the Stream Source dropdown** - sources only appear once
they're actually transmitting and discovered on the network
(`DiscoveredStreams`); an idle/powered-off transmitter won't show up.

**CEC events never fire** - on an Apple TV, check **Settings → Video and
Audio → Volume Control** is set to use HDMI-CEC; by default it doesn't put
remote presses on the CEC bus at all. For other sources, confirm they
actually emit CEC (not every device does).

## Support

- GitHub Issues: https://github.com/capslockapocalypse/crestron-nvx-homeassistant-addon/issues
- Home Assistant Community: https://community.home-assistant.io/

## License

MIT License - see [LICENSE](LICENSE).
