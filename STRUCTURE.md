# Repository Structure

This repository follows the Home Assistant custom component standard structure:

```
crestron-nvx-homeassistant-addon/
├── .gitignore                      # Git ignore rules
├── LICENSE                         # MIT License
├── README.md                       # Main documentation
├── VERSION                         # Version tracking
├── hacs.json                       # HACS metadata
├── info.md                         # HACS store description
├── INSTALLATION.md                 # Installation guide
├── API_DOCUMENTATION.md            # Crestron API reference
├── configuration_example.yaml      # Example configurations
└── custom_components/
    └── crestron_nvx/              # Integration module
        ├── __init__.py             # Integration setup
        ├── manifest.json           # Integration metadata
        ├── strings.json            # UI strings
        ├── const.py                # Constants
        ├── config_flow.py          # Config flow (UI setup)
        ├── crestron_nvx_api.py     # API client
        ├── sensor.py               # Sensor entities
        ├── select.py               # Select entities (stream switching)
        ├── button.py               # Button entities (CEC controls)
        ├── services.yaml           # Custom services
        └── translations/
            └── en.json             # English translations
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
