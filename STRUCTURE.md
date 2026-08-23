# Repository Structure

This repository follows the Home Assistant custom component standard structure:

```
crestron-nvx-homeassistant-addon/
├── .env                             # Real device creds for test_live.py (gitignored)
├── .gitignore                       # Git ignore rules
├── LICENSE                          # MIT License
├── README.md                        # Main documentation
├── VERSION                          # Version tracking
├── hacs.json                        # HACS metadata
├── icon.png, icon@2x.png            # HACS store icon (original design, on-brand colors - not Crestron's logo)
├── info.md                          # HACS store description
├── INSTALLATION.md                  # Installation guide
├── API_DOCUMENTATION.md             # Verified Crestron DM NVX REST API reference
├── test_live.py                     # Manual regression harness against real hardware
└── custom_components/
    └── crestron_nvx/                # Integration module
        ├── __init__.py              # Integration setup, DataUpdateCoordinator
        ├── manifest.json            # Integration metadata
        ├── strings.json             # UI strings
        ├── const.py                 # Constants
        ├── config_flow.py           # Config flow (UI setup, auto-detects device role)
        ├── crestron_nvx_api.py      # Real DM NVX REST API client (auth, AvRouting, CEC decode, OSD)
        ├── entity.py                # Shared device_info builder (real model, config URL, firmware)
        ├── sensor.py                # Status sensors (all devices)
        ├── select.py                # Stream/audio/HDMI-input selects (AvRouting + DeviceSpecific)
        ├── switch.py                # Audio Follows Video toggle (receivers)
        ├── notify.py                # OSD message notify entity (receivers with OSD support)
        ├── number.py                # OSD display duration setting (receivers with OSD support)
        ├── event.py                 # CEC command listener (transmitters, via Longpoll)
        └── translations/
            └── en.json              # English translations
```

## Installation

### HACS (Recommended)
1. Open HACS
2. Click "Integrations"
3. Click the menu (⋮) → "Custom repositories"
4. Add `https://github.com/capslockapocalypse/crestron-nvx-homeassistant-addon`
5. Select category "Integration"
6. Install "Crestron NVX"

### Manual
1. Copy `custom_components/crestron_nvx` to your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant
3. Add integration via UI

## For Development

```bash
# Clone repository
git clone https://github.com/capslockapocalypse/crestron-nvx-homeassistant-addon.git

# Link to Home Assistant for testing
ln -s $(pwd)/custom_components/crestron_nvx ~/.homeassistant/custom_components/
```
