"""Coordinator for Govee Hass Connect."""

import asyncio
from collections.abc import Callable
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_DISCOVERY_INTERVAL,
    CONF_LISTENING_PORT,
    CONF_MULTICAST_ADDRESS,
    CONF_TARGET_PORT,
    SCAN_INTERVAL,
)
from .govee_api import GoveeController, GoveeDevice

_LOGGER = logging.getLogger(__name__)

type GoveeHassConnectConfigEntry = ConfigEntry[GoveeHassConnectCoordinator]


class GoveeHassConnectCoordinator(DataUpdateCoordinator[list[GoveeDevice]]):
    """Coordinator for Govee Hass Connect integration."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: GoveeHassConnectConfigEntry,
        source_ip: str,
        static_ips: list[str],
    ) -> None:
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            config_entry=config_entry,
            name="GoveeHassConnect",
            update_interval=SCAN_INTERVAL,
        )

        self._controller = GoveeController(
            loop=hass.loop,
            logger=_LOGGER,
            listening_address=source_ip,
            broadcast_address=CONF_MULTICAST_ADDRESS,
            broadcast_port=CONF_TARGET_PORT,
            listening_port=CONF_LISTENING_PORT,
            discovery_enabled=False,
            discovery_interval=CONF_DISCOVERY_INTERVAL,
            static_devices=static_ips,
            update_enabled=False,
        )
        self._connectivity_state: dict[str, bool] = {}

    async def start(self) -> None:
        _LOGGER.debug("Starting Govee controller, static_ips=%s", self._controller._static_device_ips)
        await self._controller.start()
        self._controller.send_update_message()

    def set_discovery_callback(self, callback: Callable[[GoveeDevice, bool], bool]) -> None:
        self._controller.set_device_discovered_callback(callback)

    def cleanup(self) -> asyncio.Event:
        return self._controller.cleanup()

    @property
    def devices(self) -> list[GoveeDevice]:
        return self._controller.devices

    async def _async_update_data(self) -> list[GoveeDevice]:
        self._controller.send_update_message()

        devices = self.devices
        for device in devices:
            is_connected = device.is_connected
            previous = self._connectivity_state.get(device.fingerprint)
            if previous is not None and previous != is_connected:
                _LOGGER.debug(
                    "Device %s (ip=%s) connectivity changed -> %s",
                    device.fingerprint,
                    device.ip,
                    "reachable" if is_connected else "unreachable",
                )
            self._connectivity_state[device.fingerprint] = is_connected

        return devices

    async def turn_on(self, device: GoveeDevice) -> None:
        await device.turn_on()

    async def turn_off(self, device: GoveeDevice) -> None:
        await device.turn_off()

    async def set_brightness(self, device: GoveeDevice, brightness: int) -> None:
        await device.set_brightness(brightness)

    async def set_rgb_color(self, device: GoveeDevice, red: int, green: int, blue: int) -> None:
        await device.set_rgb_color(red, green, blue)

    async def set_temperature(self, device: GoveeDevice, temperature: int) -> None:
        await device.set_temperature(temperature)

    async def set_scene(self, device: GoveeDevice, scene: str) -> None:
        await device.set_scene(scene)
