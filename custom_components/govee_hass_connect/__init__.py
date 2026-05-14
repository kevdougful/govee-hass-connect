"""The Govee Hass Connect integration."""

import asyncio
from contextlib import suppress
from errno import EADDRINUSE
import logging
import socket

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_LISTENING_PORT, CONF_STATIC_IPS, DISCOVERY_TIMEOUT, DOMAIN
from .coordinator import GoveeHassConnectConfigEntry, GoveeHassConnectCoordinator

PLATFORMS: list[Platform] = [Platform.LIGHT]

_LOGGER = logging.getLogger(__name__)


def _get_local_source_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "0.0.0.0"


async def async_setup_entry(hass: HomeAssistant, entry: GoveeHassConnectConfigEntry) -> bool:
    """Set up Govee Hass Connect from a config entry."""

    static_ips: list[str] = entry.options.get(
        CONF_STATIC_IPS, entry.data.get(CONF_STATIC_IPS, [])
    )

    source_ip: str = await hass.async_add_executor_job(_get_local_source_ip)

    _LOGGER.debug(
        "Setting up Govee Hass Connect: source_ip=%s static_ips=%s",
        source_ip,
        static_ips,
    )

    coordinator = GoveeHassConnectCoordinator(
        hass=hass,
        config_entry=entry,
        source_ip=source_ip,
        static_ips=static_ips,
    )

    async def _cleanup():
        done: asyncio.Event = coordinator.cleanup()
        with suppress(TimeoutError):
            await asyncio.wait_for(done.wait(), 1)

    entry.async_on_unload(_cleanup)

    try:
        await coordinator.start()
    except OSError as ex:
        if ex.errno == EADDRINUSE:
            _LOGGER.error("UDP port %s is already in use", CONF_LISTENING_PORT)
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="port_in_use",
                translation_placeholders={"port": str(CONF_LISTENING_PORT)},
            ) from ex
        _LOGGER.error("Failed to start controller: %s", ex)
        return False

    await coordinator.async_config_entry_first_refresh()

    try:
        async with asyncio.timeout(delay=DISCOVERY_TIMEOUT):
            while not coordinator.devices:
                await asyncio.sleep(1)
    except TimeoutError as ex:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="no_devices_found",
        ) from ex

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: GoveeHassConnectConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
