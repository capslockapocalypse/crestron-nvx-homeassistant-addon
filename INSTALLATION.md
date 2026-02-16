# Crestron NVX Home Assistant Integration - Installation Guide

## Prerequisites

- Home Assistant 2023.1 or newer
- Crestron NVX Transmitters and/or Receivers on your network
- Network connectivity between Home Assistant and NVX devices
- (Optional) Credentials for NVX devices if authentication is enabled

## Installation Methods

### Option 1: HACS Installation (Recommended)

HACS (Home Assistant Community Store) is the easiest way to install and manage custom integrations.

#### Step 1: Install HACS
If you haven't already installed HACS, follow the instructions at: https://hacs.xyz/docs/setup/download

#### Step 2: Add Custom Repository
1. Open HACS in your Home Assistant interface
2. Click on "Integrations"
3. Click the three dots (⋮) in the top right corner
4. Select "Custom repositories"
5. Add the repository URL: `https://github.com/yourusername/crestron-nvx`
6. Select category: "Integration"
7. Click "Add"

#### Step 3: Install Integration
1. Find "Crestron NVX" in the HACS integrations list
2. Click on it
3. Click "Download"
4. Select the latest version
5. Restart Home Assistant

### Option 2: Manual Installation

#### Step 1: Download Integration Files
Download all files from this repository to your local machine.

#### Step 2: Copy Files to Home Assistant
1. Connect to your Home Assistant instance (via SSH, Samba, or file editor)
2. Navigate to your configuration directory (usually `/config/`)
3. Create a `custom_components` folder if it doesn't exist
4. Create a `crestron_nvx` folder inside `custom_components`
5. Copy all integration files into `/config/custom_components/crestron_nvx/`

Your directory structure should look like:
```
/config/
├── custom_components/
│   └── crestron_nvx/
│       ├── __init__.py
│       ├── button.py
│       ├── config_flow.py
│       ├── const.py
│       ├── crestron_nvx_api.py
│       ├── manifest.json
│       ├── select.py
│       ├── sensor.py
│       ├── services.yaml
│       └── strings.json
```

#### Step 3: Restart Home Assistant
Restart Home Assistant to load the new integration.

## Configuration

### Adding Devices via UI (Recommended)

1. **Navigate to Integrations**
   - Go to Settings → Devices & Services
   - Click the "+ ADD INTEGRATION" button

2. **Search for Crestron NVX**
   - Type "Crestron NVX" in the search box
   - Click on the integration when it appears

3. **Configure First Device**
   Fill in the following information:
   - **Device Name**: Give your device a friendly name (e.g., "Conference Room Display")
   - **IP Address**: Enter the IP address of your NVX device (e.g., "192.168.1.100")
   - **Device Type**: Select either "Transmitter" or "Receiver"
   - **Username** (optional): If authentication is enabled, enter username
   - **Password** (optional): If authentication is enabled, enter password
   - **Update Interval**: How often to poll the device (default: 30 seconds)

4. **Add More Devices**
   - Repeat the process for each NVX device you want to add
   - Each device will be added as a separate integration instance

### Adding Devices via YAML (Alternative)

If you prefer YAML configuration, add this to your `configuration.yaml`:

```yaml
crestron_nvx:
  devices:
    - name: "Conference Room TX"
      host: "192.168.1.100"
      device_type: transmitter
      username: admin        # Optional
      password: password     # Optional
    
    - name: "Main Display RX"
      host: "192.168.1.101"
      device_type: receiver
      username: admin        # Optional
      password: password     # Optional
  
  scan_interval: 30  # Optional: Global update interval in seconds
```

After adding to YAML:
1. Check configuration: Developer Tools → YAML → Check Configuration
2. Restart Home Assistant

## Verifying Installation

### Check Device Status

1. **Navigate to Devices**
   - Go to Settings → Devices & Services
   - Click on "Crestron NVX"
   - You should see all your configured devices

2. **Check Entities**
   Each device should create multiple entities:
   - **Sensors**: Resolution, Signal Status, HDCP Status, Audio Status, Network Status
   - **Select** (Receivers only): Stream Source dropdown
   - **Buttons**: CEC controls (Power On, Power Off, Volume Up/Down, Mute)

3. **View Entity States**
   - Go to Developer Tools → States
   - Filter by "crestron_nvx"
   - All entities should show current values

### Test Functionality

1. **Test Status Sensors**
   - Check that resolution sensor shows correct value
   - Verify signal status matches actual state
   - Confirm network status shows "connected"

2. **Test CEC Controls** (if supported by your display)
   - Try the Power On button
   - Try the Volume Up/Down buttons
   - Verify display responds to commands

3. **Test Stream Switching** (Receivers only)
   - Open the Stream Source dropdown
   - Select a different stream
   - Verify the receiver switches to the new source

## Troubleshooting Installation

### Integration Not Showing Up

**Problem**: Can't find "Crestron NVX" when searching for integrations.

**Solutions**:
1. Verify files are in correct location: `/config/custom_components/crestron_nvx/`
2. Check that `manifest.json` exists and is valid JSON
3. Restart Home Assistant again
4. Check Home Assistant logs for errors: Settings → System → Logs

### Configuration Errors

**Problem**: Integration shows errors during setup.

**Solutions**:
1. Verify NVX device IP address is correct
2. Test network connectivity: `ping <device_ip>` from Home Assistant host
3. Ensure device is powered on and responding
4. Check credentials if authentication is required
5. Review Home Assistant logs for specific error messages

### Entities Not Created

**Problem**: Device added but no entities appear.

**Solutions**:
1. Wait 30 seconds for first update cycle
2. Force entity refresh: Developer Tools → States → Reload
3. Check coordinator status in logs
4. Verify device REST API is accessible
5. Try increasing scan interval to 60 seconds

### "Cannot Connect" Error

**Problem**: Setup fails with "cannot connect" error.

**Solutions**:
1. Verify IP address is correct and reachable
2. Check firewall rules between Home Assistant and NVX device
3. Ensure NVX REST API is enabled on device
4. Try accessing `http://<device_ip>/Device/DeviceInfo` in a browser
5. Check if authentication credentials are required

## Network Configuration

### Required Ports
- **HTTP**: Port 80 (default REST API port)
- **HTTPS**: Port 443 (if SSL is configured)

### Firewall Rules
Allow traffic from Home Assistant to NVX devices on port 80/443.

### Multicast Requirements (for stream switching)
- Receivers need to be on the same network segment as transmitters
- IGMP snooping should be properly configured on network switches
- Multicast routing must be enabled between VLANs if devices are separated

## Next Steps

After successful installation:

1. **Create Automations**
   - See `configuration_example.yaml` for automation ideas
   - Create scenes for common AV configurations

2. **Build Dashboard**
   - Add entities to Lovelace dashboards
   - Create custom cards for AV control

3. **Set Up Notifications**
   - Configure alerts for signal loss
   - Monitor device health

4. **Integrate with Other Systems**
   - Link with calendar for meeting room automation
   - Connect to presence detection
   - Integrate with lighting control

## Getting Help

- **GitHub Issues**: Report bugs or request features
- **Home Assistant Community**: Ask questions in the forums
- **Documentation**: Check README.md for detailed information

## Updating the Integration

### Via HACS
1. HACS will notify you of updates
2. Click "Update" when a new version is available
3. Restart Home Assistant

### Manual Update
1. Download new version files
2. Replace files in `/config/custom_components/crestron_nvx/`
3. Restart Home Assistant

## Uninstalling

1. Remove integration: Settings → Devices & Services → Crestron NVX → Delete
2. Delete folder: `/config/custom_components/crestron_nvx/`
3. Restart Home Assistant
