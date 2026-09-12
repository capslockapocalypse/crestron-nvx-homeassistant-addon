"""Constants for the Crestron NVX integration."""

DOMAIN = "crestron_nvx"

# Configuration
CONF_DEVICES = "devices"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_VERIFY_SSL = "verify_ssl"
CONF_ENABLE_PREVIEW_CAMERA = "enable_preview_camera"

# Coordinator data keys
ATTR_HORIZONTAL_RESOLUTION = "horizontal_resolution"
ATTR_VERTICAL_RESOLUTION = "vertical_resolution"
ATTR_FRAMES_PER_SECOND = "frames_per_second"
ATTR_VIDEO_CONNECTED = "video_connected"
ATTR_HDCP_STATE = "hdcp_state"
ATTR_NETWORK_CONNECTED = "network_connected"
ATTR_IP_ADDRESS = "ip_address"

# CEC event entity (transmitters only - listens to Apple-TV-style remote
# presses arriving over HDMI-CEC on the HDMI input, see crestron_nvx_api.py)
CEC_EVENT_TYPES = ["power_on", "power_off", "volume_up", "volume_down", "mute"]
