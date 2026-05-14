"""Light entity for Govee Hass Connect."""

from datetime import datetime
import logging
from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
    filter_supported_color_modes,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEVICE_TIMEOUT, DOMAIN, MANUFACTURER
from .coordinator import GoveeHassConnectConfigEntry, GoveeHassConnectCoordinator
from .govee_api import GoveeDevice, GoveeLightFeatures

_LOGGER = logging.getLogger(__name__)

_NONE_SCENE = "none"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: GoveeHassConnectConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator: GoveeHassConnectCoordinator = config_entry.runtime_data

    def discovery_callback(device: GoveeDevice, is_new: bool) -> bool:
        if is_new:
            async_add_entities([GoveeLight(coordinator, device)])
        return True

    async_add_entities(
        GoveeLight(coordinator, device) for device in coordinator.devices
    )

    coordinator.set_discovery_callback(discovery_callback)


class GoveeLight(CoordinatorEntity[GoveeHassConnectCoordinator], LightEntity):
    """Govee light entity."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_color_modes: set[ColorMode]
    _fixed_color_mode: ColorMode | None = None
    _attr_effect_list: list[str] | None = None
    _attr_effect: str | None = None
    _attr_supported_features: LightEntityFeature = LightEntityFeature(0)
    _last_color_state: (
        tuple[
            ColorMode | str | None,
            int | None,
            tuple[int, int, int] | tuple[int | None] | None,
        ]
        | None
    ) = None

    def __init__(
        self,
        coordinator: GoveeHassConnectCoordinator,
        device: GoveeDevice,
    ) -> None:
        super().__init__(coordinator)
        self._device = device
        self._attr_unique_id = device.fingerprint

        capabilities = device.capabilities
        color_modes: set[ColorMode] = {ColorMode.ONOFF}

        if capabilities:
            if GoveeLightFeatures.COLOR_RGB & capabilities.features:
                color_modes.add(ColorMode.RGB)
            if GoveeLightFeatures.COLOR_KELVIN_TEMPERATURE & capabilities.features:
                color_modes.add(ColorMode.COLOR_TEMP)
                self._attr_max_color_temp_kelvin = 9000
                self._attr_min_color_temp_kelvin = 2000
            if GoveeLightFeatures.BRIGHTNESS & capabilities.features:
                color_modes.add(ColorMode.BRIGHTNESS)
            if (
                GoveeLightFeatures.SCENES & capabilities.features
                and capabilities.scenes
            ):
                self._attr_supported_features = LightEntityFeature.EFFECT
                self._attr_effect_list = [_NONE_SCENE, *capabilities.scenes.keys()]

        self._attr_supported_color_modes = filter_supported_color_modes(color_modes)
        if len(self._attr_supported_color_modes) == 1:
            self._fixed_color_mode = next(iter(self._attr_supported_color_modes))

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.fingerprint)},
            name=device.sku,
            manufacturer=MANUFACTURER,
            model_id=device.sku,
            serial_number=device.fingerprint,
        )

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        return datetime.now() - self._device.lastseen < DEVICE_TIMEOUT

    @property
    def is_on(self) -> bool:
        return self._device.on

    @property
    def brightness(self) -> int:
        return int((self._device.brightness / 100.0) * 255.0)

    @property
    def color_temp_kelvin(self) -> int | None:
        return self._device.temperature_color

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        return self._device.rgb_color

    @property
    def color_mode(self) -> ColorMode:
        if self._fixed_color_mode:
            return self._fixed_color_mode
        if (
            self._device.temperature_color is not None
            and self._device.temperature_color > 0
        ):
            return ColorMode.COLOR_TEMP
        return ColorMode.RGB

    def _save_last_color_state(self) -> None:
        self._last_color_state = (
            self._attr_color_mode,
            self._device.brightness,
            self._device.rgb_color if self.color_mode == ColorMode.RGB else None,
        )

    async def _restore_last_color_state(self) -> None:
        if not self._last_color_state:
            return
        mode, brightness, rgb = self._last_color_state
        if mode == ColorMode.RGB and rgb:
            await self.coordinator.set_rgb_color(self._device, *rgb)
        elif mode == ColorMode.COLOR_TEMP and self._device.temperature_color:
            await self.coordinator.set_temperature(
                self._device, self._device.temperature_color
            )
        if brightness is not None:
            await self.coordinator.set_brightness(self._device, brightness)

    async def async_turn_on(self, **kwargs: Any) -> None:
        if ATTR_BRIGHTNESS in kwargs:
            brightness = int((float(kwargs[ATTR_BRIGHTNESS]) / 255.0) * 100.0)
            await self.coordinator.set_brightness(self._device, brightness)

        if ATTR_RGB_COLOR in kwargs:
            self._attr_color_mode = ColorMode.RGB
            self._attr_effect = None
            self._last_color_state = None
            red, green, blue = kwargs[ATTR_RGB_COLOR]
            await self.coordinator.set_rgb_color(self._device, red, green, blue)
        elif ATTR_COLOR_TEMP_KELVIN in kwargs:
            self._attr_color_mode = ColorMode.COLOR_TEMP
            self._attr_effect = None
            self._last_color_state = None
            await self.coordinator.set_temperature(
                self._device, int(kwargs[ATTR_COLOR_TEMP_KELVIN])
            )
        elif ATTR_EFFECT in kwargs:
            effect = kwargs[ATTR_EFFECT]
            if effect and self._attr_effect_list and effect in self._attr_effect_list:
                if effect == _NONE_SCENE:
                    self._attr_effect = None
                    await self._restore_last_color_state()
                else:
                    self._attr_effect = effect
                    self._save_last_color_state()
                    await self.coordinator.set_scene(self._device, effect)

        if not self.is_on or not kwargs:
            await self.coordinator.turn_on(self._device)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.turn_off(self._device)

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()
