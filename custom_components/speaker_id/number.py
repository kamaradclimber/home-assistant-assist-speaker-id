"""How many samples one recording session takes (the device's choice, 1-50)."""

from __future__ import annotations

from homeassistant.components.number import NumberMode, RestoreNumber
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SpeakerIdConfigEntry, device_info
from .const import ENTITY_IDS


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SpeakerIdConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([SamplesNumber(entry)])


class SamplesNumber(RestoreNumber):
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "samples"
    _attr_native_min_value = 1
    _attr_native_max_value = 50
    _attr_native_step = 1
    _attr_mode = NumberMode.BOX

    def __init__(self, entry: SpeakerIdConfigEntry) -> None:
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}-samples"
        self.entity_id = ENTITY_IDS["samples"]
        self._attr_device_info = device_info(entry)

    @property
    def native_value(self) -> float:
        return self._entry.runtime_data.samples

    async def async_set_native_value(self, value: float) -> None:
        self._entry.runtime_data.samples = int(value)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_number_data()) and last.native_value is not None:
            self._entry.runtime_data.samples = int(last.native_value)
