# Crestron NVX Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub release](https://img.shields.io/github/release/capslockapocalypse/crestron-nvx-homeassistant-addon.svg)](https://github.com/capslockapocalypse/crestron-nvx-homeassistant-addon/releases)
[![License](https://img.shields.io/github/license/capslockapocalypse/crestron-nvx-homeassistant-addon.svg)](LICENSE)

A comprehensive Home Assistant integration for controlling Crestron NVX video over IP transmitters and receivers.

## Features

### For Both Transmitters and Receivers:
- **Real-time Status Monitoring**
  - Video resolution detection
  - Signal detection status
  - HDCP status monitoring
  - Audio presence detection
  - Network connection status

- **CEC Control**
  - Power On/Off commands
  - Volume Up/Down
  - Mute toggle
  - Send custom CEC commands

### For Receivers Only:
- **Stream Switching**
  - Automatic discovery of available stream subscriptions
  - Easy switching between streams via dropdown menu
  - Real-time subscription status updates

## Installation

### Method 1: HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to "Integrations"
3. Click the three dots in the top right and select "Custom repositories"
4. Add this repository URL: `https://github.com/capslockapocalypse/crestron-nvx-homeassistant-addon`
5. Category: Integration
6. Click "Add"
7. Find "Crestron NVX" in HACS and click "Download"
8. Restart Home Assistant

### Method 2: Manual Installation

1. Copy the `crestron_nvx` folder to your `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

### Via UI (Recommended)

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "Crestron NVX"
4. Fill in the device information:
   - **Device Name**: Friendly name for the device
   - **IP Address**: IP address or hostname of the NVX device
   - **Device Type**: Select "Transmitter" or "Receiver"
   - **Username** (optional): Authentication username
   - **Password** (optional): Authentication password
   - **Update Interval**: How often to poll the device (default: 30 seconds)

### Via YAML (Legacy)

Add to your `configuration.yaml`:

```yaml
crestron_nvx:
  devices:
    - name: "Conference Room TX"
      host: "192.168.1.100"
      device_type: transmitter
      username: admin
      password: password
      
    - name: "Display 1 RX"
      host: "192.168.1.101"
      device_type: receiver
      scan_interval: 30
```

## Entities Created

### Sensors (All Devices)

- **Resolution Sensor**: Current video resolution (e.g., "1920x1080@60")
- **Signal Status**: Detected / No Signal
- **HDCP Status**: Active / Inactive
- **Audio Status**: Present / Absent
- **Network Status**: Connected / Disconnected

### Select Entity (Receivers Only)

- **Stream Source**: Dropdown to select which transmitter stream to receive

### Buttons (All Devices)

- **CEC Power On**: Send power on command
- **CEC Power Off**: Send standby command
- **CEC Volume Up**: Increase volume
- **CEC Volume Down**: Decrease volume
- **CEC Mute**: Toggle mute

## Usage Examples

### Automation: Switch Display When Meeting Starts

```yaml
automation:
  - alias: "Conference Room - Switch to Laptop"
    trigger:
      - platform: calendar
        event: start
        entity_id: calendar.conference_room
    action:
      - service: select.select_option
        target:
          entity_id: select.display_1_rx_stream_source
        data:
          option: "Laptop TX"
```

### Automation: Power On Display When Signal Detected

```yaml
automation:
  - alias: "Auto Power On Display"
    trigger:
      - platform: state
        entity_id: sensor.display_1_rx_signal_status
        to: "detected"
    action:
      - service: button.press
        target:
          entity_id: button.display_1_rx_cec_power_on
```

### Script: Switch Multiple Displays

```yaml
script:
  switch_all_displays_to_camera:
    alias: "Switch All Displays to Camera"
    sequence:
      - service: select.select_option
        target:
          entity_id:
            - select.display_1_rx_stream_source
            - select.display_2_rx_stream_source
            - select.display_3_rx_stream_source
        data:
          option: "Camera TX"
```

### Lovelace Dashboard Example

```yaml
type: entities
title: Conference Room AV
entities:
  - entity: sensor.display_1_rx_resolution
    name: Resolution
  - entity: sensor.display_1_rx_signal_status
    name: Signal
  - entity: select.display_1_rx_stream_source
    name: Video Source
  - type: button
    name: Power On
    tap_action:
      action: call-service
      service: button.press
      service_data:
        entity_id: button.display_1_rx_cec_power_on
  - type: button
    name: Power Off
    tap_action:
      action: call-service
      service: button.press
      service_data:
        entity_id: button.display_1_rx_cec_power_off
```

## API Endpoints Used

This integration uses the Crestron NVX REST API. The following endpoints are utilized:

- `GET /Device/VideoStatus` - Video signal and resolution info
- `GET /Device/AudioStatus` - Audio signal detection
- `GET /Device/HdcpStatus` - HDCP encryption status
- `GET /Device/NetworkStatus` - Network connectivity
- `GET /Device/Subscriptions` - Available streams (receivers)
- `POST /Device/Subscribe` - Switch stream (receivers)
- `GET /Device/CEC` - CEC status
- `POST /Device/CEC` - Send CEC commands
- `GET /Device/DeviceInfo` - Device information

## Troubleshooting

### Device Not Responding

1. Verify the NVX device is powered on and connected to the network
2. Check that the IP address is correct
3. Ensure Home Assistant can reach the device (ping test)
4. Verify credentials if authentication is enabled

### No Streams Available (Receivers)

1. Ensure transmitters are powered on and transmitting
2. Check multicast routing between transmitters and receivers
3. Verify the receiver is properly subscribed to multicast groups
4. Check the scan interval - streams are discovered during updates

### CEC Commands Not Working

1. Verify CEC is enabled on both the NVX device and the connected display
2. Check HDMI cable connections
3. Some displays have specific CEC requirements or limitations
4. Try power cycling the display

## Support

For issues, feature requests, or contributions:
- GitHub Issues: https://github.com/capslockapocalypse/crestron-nvx-homeassistant-addon/issues
- Home Assistant Community: https://community.home-assistant.io/

## License

MIT License - See LICENSE file for details

## Credits

Developed by [Your Name]
Based on Crestron NVX REST API documentation
