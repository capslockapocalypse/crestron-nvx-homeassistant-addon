{% if installed %}
## Changes in {{version}}

Check the [release notes](https://github.com/capslockapocalypse/crestron-nvx-home-assistant/releases) for details.

{% endif %}

## Crestron NVX Home Assistant Integration

Control your Crestron NVX video over IP transmitters and receivers directly from Home Assistant!

### Features

- 📺 **Real-time Status Monitoring** - Resolution, signal detection, HDCP, audio, and network status
- 🎛️ **Stream Switching** - Easy dropdown menu to switch between video sources on receivers
- 🎮 **CEC Control** - Power, volume, and mute control for connected displays
- 🔄 **Automatic Discovery** - Receivers automatically discover available transmitter streams
- ⚡ **Fast Updates** - Configurable polling interval (10-300 seconds)

### Supported Devices

- Crestron DM-NVX-350 Series
- Crestron DM-NVX-D30 Series
- Other Crestron NVX devices with REST API support

### Quick Start

1. Install via HACS
2. Go to Settings → Devices & Services
3. Click Add Integration
4. Search for "Crestron NVX"
5. Enter your device details and credentials
6. Start controlling your AV system!

### Requirements

- Home Assistant 2023.1.0 or newer
- Crestron NVX devices on your network
- Valid credentials for each device

### Documentation

- [Installation Guide](https://github.com/capslockapocalypse/crestron-nvx-home-assistant/blob/master/INSTALLATION.md)
- [API Documentation](https://github.com/capslockapocalypse/crestron-nvx-home-assistant/blob/master/API_DOCUMENTATION.md)
- [Configuration Examples](https://github.com/capslockapocalypse/crestron-nvx-home-assistant/blob/master/configuration_example.yaml)

### Support

Found a bug or have a feature request? [Open an issue](https://github.com/capslockapocalypse/crestron-nvx-home-assistant/issues)!
