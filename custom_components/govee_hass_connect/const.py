"""Constants for the Govee Hass Connect integration."""

from datetime import timedelta

DOMAIN = "govee_hass_connect"
MANUFACTURER = "Govee"

CONF_STATIC_IPS = "static_ips"

CONF_MULTICAST_ADDRESS = "239.255.255.250"
CONF_TARGET_PORT = 4001
CONF_LISTENING_PORT = 4002
CONF_DISCOVERY_INTERVAL = 60

SCAN_INTERVAL = timedelta(seconds=30)
DEVICE_TIMEOUT = SCAN_INTERVAL * 3
DISCOVERY_TIMEOUT = 5
