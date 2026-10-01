"""What a panel can tell you about where it is."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS_MILLIWATT, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import PanelEntity, async_setup_panel_platform


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback,
) -> None:
    await async_setup_panel_platform(
        hass, entry, async_add_entities,
        lambda registry, panel_id: (
            PanelWifiSignal(registry, panel_id),
            PanelAmbientLight(registry, panel_id),
        ),
    )


class PanelWifiSignal(PanelEntity, SensorEntity):
    """How well this panel is hearing the house.

    Worth having on by default: a weak link does not present as a weak link,
    it presents as video that takes sixteen seconds and talkback that arrives
    late, and one panel at -79 beside two at -40 is the whole diagnosis.
    """

    _attr_translation_key = "wifi_signal"
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, registry, panel_id: str) -> None:
        super().__init__(registry, panel_id)
        self._attr_unique_id = f"{panel_id}_wifi_signal"

    @property
    def native_value(self) -> int | None:
        return self._state.rssi


class PanelAmbientLight(PanelEntity, SensorEntity):
    """The panel's light sensor, on the panel's own scale.

    Deliberately no unit and no device class: these panels report a number
    that is plainly not lux, and dressing it as illuminance would invite
    comparison with sensors that mean something.
    """

    _attr_translation_key = "ambient_light"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, registry, panel_id: str) -> None:
        super().__init__(registry, panel_id)
        self._attr_unique_id = f"{panel_id}_ambient_light"

    @property
    def native_value(self) -> int | None:
        return self._state.ambient_light
