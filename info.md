{% if installed %}
## Changes in {{version}}

Check the [release notes](https://github.com/capslockapocalypse/crestron-nvx-homeassistant-addon/releases) for details.

{% endif %}

## Crestron NVX Home Assistant Integration

Control your Crestron NVX video over IP transmitters and receivers directly from Home Assistant!

### Features

- 📺 **Real-time Status Monitoring** - Resolution, HDMI signal/sink status, HDCP state, and network status
- 🎛️ **Stream Switching** - Dropdown to switch a receiver's video, audio, and USB together to any discovered source
- 🎮 **CEC Listener** - fires Home Assistant events (power/volume/mute) when a connected source device (e.g. an Apple TV) sends CEC remote commands, for use as automation triggers
- 🔄 **Automatic Discovery** - Receivers automatically discover available transmitter streams
- ⚡ **Configurable polling interval** (10-300 seconds) for status; CEC events are pushed in near-real-time via long-poll, not on the polling interval

### Supported Devices

Verified against DM-NVX-E30, DM-NVX-352, DM-NVX-350, and DM-NVX-D30 (firmware
7.1.5259.00090). Other DM NVX models with REST API support should work but
haven't been directly tested.

### Quick Start

1. Install via HACS
2. Go to Settings → Devices & Services
3. Click Add Integration
4. Search for "Crestron NVX"
5. Enter the device's IP, username/password (authentication must already be
   enabled on the device - the API is HTTPS-only)
6. Role (Transmitter/Receiver) is detected automatically

### Requirements

- Home Assistant 2023.1.0 or newer
- Crestron NVX devices on your network, reachable over HTTPS (port 443),
  with authentication enabled
- Valid admin credentials for each device

### Documentation

- [Installation Guide](https://github.com/capslockapocalypse/crestron-nvx-homeassistant-addon/blob/master/INSTALLATION.md)
- [API Documentation](https://github.com/capslockapocalypse/crestron-nvx-homeassistant-addon/blob/master/API_DOCUMENTATION.md)
- [Configuration Examples](https://github.com/capslockapocalypse/crestron-nvx-homeassistant-addon/blob/master/configuration_example.yaml)

### Support

Found a bug or have a feature request? [Open an issue](https://github.com/capslockapocalypse/crestron-nvx-homeassistant-addon/issues)!
