"""The device's buttons: start and stop recording a voiceprint, calibrate."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SpeakerIdConfigEntry, device_info
from .const import ENTITY_IDS
from .enrollment import async_calibrate_from_device, async_start_from_device, async_stop_enrollment


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SpeakerIdConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([StartButton(entry), StopButton(entry), CalibrateButton(entry)])


class SpeakerIdButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False
    key: str

    def __init__(self, entry: SpeakerIdConfigEntry) -> None:
        self._entry = entry
        self._attr_translation_key = self.key
        self._attr_unique_id = f"{entry.entry_id}-{self.key}"
        self.entity_id = ENTITY_IDS[self.key]
        self._attr_device_info = device_info(entry)


class StartButton(SpeakerIdButton):
    """Record the chosen person on the chosen satellite: it asks for each sentence itself."""

    key = "start_enrollment"

    async def async_press(self) -> None:
        await async_start_from_device(self.hass, self._entry)


class StopButton(SpeakerIdButton):
    key = "stop_enrollment"

    async def async_press(self) -> None:
        await async_stop_enrollment(self.hass, self._entry)


class CalibrateButton(SpeakerIdButton):
    """Check how well the voices are told apart: the result shows as a notification."""

    key = "calibrate"

    async def async_press(self) -> None:
        await async_calibrate_from_device(self.hass, self._entry)
