"""Config flow for Govee Hass Connect."""

import asyncio
from contextlib import suppress
from errno import EADDRINUSE
from ipaddress import AddressValueError, IPv4Address
import logging
import socket
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlowWithReload
from homeassistant.helpers.selector import TextSelector

from .const import (
    CONF_DISCOVERY_INTERVAL,
    CONF_LISTENING_PORT,
    CONF_MULTICAST_ADDRESS,
    CONF_STATIC_IPS,
    CONF_TARGET_PORT,
    DISCOVERY_TIMEOUT,
    DOMAIN,
)
from .govee_api import GoveeController

_LOGGER = logging.getLogger(__name__)

CONF_STATIC_IPS_TEXT = "static_ips_text"

STEP_USER_SCHEMA = vol.Schema(
    {vol.Required(CONF_STATIC_IPS_TEXT): TextSelector()}
)

STEP_OPTIONS_SCHEMA = vol.Schema(
    {vol.Optional(CONF_STATIC_IPS_TEXT, default=""): TextSelector()}
)


def _parse_static_ips(value: str) -> list[str]:
    """Parse comma- or newline-separated IPv4 addresses.

    Raises AddressValueError for any invalid entry.
    """
    items = [item.strip() for item in value.replace("\n", ",").split(",")]
    seen: dict[str, None] = {}
    for item in items:
        if not item:
            continue
        try:
            addr = str(IPv4Address(item))
        except (AddressValueError, ValueError) as exc:
            raise AddressValueError(item) from exc
        seen[addr] = None
    return list(seen)


def _get_local_source_ip() -> str | None:
    """Return the primary outbound IPv4 address of this host."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "0.0.0.0"


async def _async_try_connect(hass, source_ip: str, static_ips: list[str]) -> bool:
    """Attempt to reach at least one device from source_ip."""
    controller = GoveeController(
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

    try:
        await controller.start()
    except OSError as ex:
        if ex.errno == EADDRINUSE:
            _LOGGER.debug("Port already in use on %s during config probe", source_ip)
        return False

    try:
        async with asyncio.timeout(delay=DISCOVERY_TIMEOUT):
            while not controller.devices:
                await asyncio.sleep(1)
    except TimeoutError:
        pass

    found = len(controller.devices) > 0
    done: asyncio.Event = controller.cleanup()
    with suppress(TimeoutError):
        await asyncio.wait_for(done.wait(), 1)

    return found


async def _async_has_devices(hass, static_ips: list[str]) -> bool:
    source_ip = await hass.async_add_executor_job(_get_local_source_ip)
    return await _async_try_connect(hass, source_ip, static_ips)


class GoveeHassConnectConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow for Govee Hass Connect."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                static_ips = _parse_static_ips(user_input[CONF_STATIC_IPS_TEXT])
            except AddressValueError:
                errors[CONF_STATIC_IPS_TEXT] = "invalid_ip"
            else:
                if not static_ips:
                    errors[CONF_STATIC_IPS_TEXT] = "no_ips"
                else:
                    if await _async_has_devices(self.hass, static_ips):
                        return self.async_create_entry(
                            title="Govee Hass Connect",
                            data={CONF_STATIC_IPS: static_ips},
                        )
                    errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_SCHEMA, user_input
            ),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry):
        return GoveeHassConnectOptionsFlow(config_entry)


class GoveeHassConnectOptionsFlow(OptionsFlowWithReload):
    """Options flow for Govee Hass Connect."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                static_ips = _parse_static_ips(user_input[CONF_STATIC_IPS_TEXT])
            except AddressValueError:
                errors[CONF_STATIC_IPS_TEXT] = "invalid_ip"
            else:
                if not static_ips:
                    errors[CONF_STATIC_IPS_TEXT] = "no_ips"
                else:
                    return self.async_create_entry(
                        data={CONF_STATIC_IPS: static_ips},
                    )

        current_ips: list[str] = self.config_entry.options.get(
            CONF_STATIC_IPS,
            self.config_entry.data.get(CONF_STATIC_IPS, []),
        )
        suggested = {CONF_STATIC_IPS_TEXT: "\n".join(current_ips)}

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                STEP_OPTIONS_SCHEMA, user_input or suggested
            ),
            errors=errors,
        )
