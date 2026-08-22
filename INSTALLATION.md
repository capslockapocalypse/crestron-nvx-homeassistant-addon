# Crestron NVX Home Assistant Integration - Installation Guide

## Prerequisites

- Home Assistant 2023.1 or newer
- Crestron NVX Transmitters and/or Receivers on your network, with
  **authentication enabled on the device** (the real REST API requires it -
  see [API_DOCUMENTATION.md](API_DOCUMENTATION.md))
- Network connectivity from Home Assistant to each device on **port 443
  (HTTPS)** - the API has no unauthenticated HTTP mode
- Admin credentials for each device

## Installation Methods

### Option 1: HACS Installation (Recommended)

#### Step 1: Install HACS
If you haven't already installed HACS, follow the instructions at: https://hacs.xyz/docs/setup/download

#### Step 2: Add Custom Repository
1. Open HACS in your Home Assistant interface
2. Click on "Integrations"
3. Click the three dots (⋮) in the top right corner
4. Select "Custom repositories"
5. Add the repository URL: `https://github.com/capslockapocalypse/crestron-nvx-homeassistant-addon`
6. Select category: "Integration"
7. Click "Add"

#### Step 3: Install Integration
1. Find "Crestron NVX" in the HACS integrations list
2. Click on it, then "Download"
3. Restart Home Assistant

### Option 2: Manual Installation

Copy `custom_components/crestron_nvx/` from this repository into your Home
Assistant config directory, so you end up with:

```
/config/
└── custom_components/
    └── crestron_nvx/
        ├── __init__.py
        ├── config_flow.py
        ├── const.py
        ├── crestron_nvx_api.py
        ├── event.py
        ├── manifest.json
        ├── select.py
        ├── sensor.py
        ├── strings.json
        └── translations/
            └── en.json
```

Then restart Home Assistant.

## Configuration

There is **no YAML configuration** - set up each device through the UI:

1. Settings → Devices & Services → **+ Add Integration**
2. Search for "Crestron NVX"
3. Fill in:
   - **Device Name** - friendly name, used to name every entity for this device
   - **IP Address or Hostname**
   - **Username** / **Password**
   - **Verify SSL Certificate** - leave unchecked unless you've installed a
     trusted cert (devices ship with self-signed certs)
   - **Update Interval** - status polling interval, seconds (default 30)
4. Repeat for each device - one config entry per device. Transmitter vs.
   receiver role is detected automatically from the device; there's nothing
   to select.

## Verifying Installation

1. **Settings → Devices & Services → Crestron NVX** - each device you added
   should be listed.
2. **Developer Tools → States**, filter by `crestron_nvx` - you should see:
   - `sensor.<name>_resolution`, `sensor.<name>_hdcp_state`,
     `sensor.<name>_network_status`, and `sensor.<name>_signal_detected`
     (transmitters) or `sensor.<name>_sink_connected` (receivers)
   - `select.<name>_stream_source` on receivers only
   - `event.<name>_cec_command` on transmitters only
3. **Test the select entity** (receivers) - pick a different source from the
   dropdown and confirm the connected display actually switches.
4. **Test the event entity** (transmitters) - press a button on the
   connected source's remote (see the CEC troubleshooting note in
   [README.md](README.md) re: Apple TV's Volume Control setting) and watch
   for the event in Developer Tools → Events, or use it directly as a device
   trigger in an automation.

## Troubleshooting

### Integration not showing up
- Confirm files are at `/config/custom_components/crestron_nvx/`
- Check `manifest.json` is valid JSON
- Restart Home Assistant again, then check Settings → System → Logs

### "Cannot connect" during setup
- Confirm the device is reachable: try `https://<device-ip>/userlogin.html`
  in a browser first (accept the self-signed cert warning) - if that
  doesn't load, it's a network/firewall issue, not this integration
- Confirm authentication is actually enabled on the device - the API has no
  unauthenticated mode to fall back to
- Check port 443 isn't blocked between Home Assistant and the device

### "Invalid auth" during setup
- Double check username/password against what the device's own web UI
  accepts

### No sources in the Stream Source dropdown
- The source transmitter needs to actually be powered on and transmitting
  before it's discoverable
- Confirm receivers and transmitters are on the same network segment /
  multicast routing and IGMP snooping are configured correctly between them

## Updating

**HACS**: HACS will notify you of updates; click "Update" and restart Home
Assistant.

**Manual**: replace the files in `/config/custom_components/crestron_nvx/`
and restart Home Assistant.

## Uninstalling

1. Settings → Devices & Services → Crestron NVX → Delete (for each device)
2. Delete `/config/custom_components/crestron_nvx/`
3. Restart Home Assistant
