"""Sensors: the last speaker (state: name, or "unknown"; scores and enrollment as attributes),
the recording of a voiceprint on the device and the last calibration.

The recognised text is deliberately not stored - the recorder keeps sensor history.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SpeakerIdConfigEntry, device_info
from .const import ENTITY_IDS, SIGNAL_CALIBRATION, SIGNAL_ENROLLMENT, SIGNAL_RESULT
from .speaker import SpeakerResult

UNKNOWN = "unknown"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SpeakerIdConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(
        [LastSpeakerSensor(entry), EnrollmentSensor(entry), CalibrationSensor(entry)]
    )


class LastSpeakerSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "last_speaker"
    _attr_should_poll = False

    def __init__(self, entry: SpeakerIdConfigEntry) -> None:
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}-last_speaker"
        self.entity_id = ENTITY_IDS["last_speaker"]  # the same in every HA language
        self._attr_device_info = device_info(entry)
        self._result: SpeakerResult | None = None

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_RESULT.format(entry_id=self._entry.entry_id), self._update
            )
        )

    @callback
    def _update(self, result: SpeakerResult) -> None:
        self._result = result
        self.async_write_ha_state()

    @property
    def native_value(self) -> str | None:
        if self._result is None:
            return None
        return self._result.name or self._result.speaker or UNKNOWN

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        return self._result.as_dict() if self._result else None


class DeviceSensor(SensorEntity):
    """A sensor of the device that follows one dispatcher signal of the entry."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_device_class = SensorDeviceClass.ENUM
    key: str
    signal: str
    options_list: tuple[str, ...]

    def __init__(self, entry: SpeakerIdConfigEntry) -> None:
        self._entry = entry
        self._attr_translation_key = self.key
        self._attr_options = list(self.options_list)
        self._attr_unique_id = f"{entry.entry_id}-{self.key}"
        self.entity_id = ENTITY_IDS[self.key]
        self._attr_device_info = device_info(entry)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self.signal.format(entry_id=self._entry.entry_id), self._changed
            )
        )

    @callback
    def _changed(self) -> None:
        self.async_write_ha_state()


class EnrollmentSensor(DeviceSensor):
    """Recording a voiceprint: idle or recording, with the progress of the last series."""

    key = "enrollment"
    signal = SIGNAL_ENROLLMENT
    options_list = ("idle", "recording")

    @property
    def native_value(self) -> str:
        guide = self._entry.runtime_data.guide
        return "recording" if guide is not None and guide.active else "idle"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        guide = self._entry.runtime_data.guide
        if guide is None:
            return None
        return {
            "speaker": guide.speaker,
            "name": guide.name,
            "satellite": guide.satellite,
            "done": guide.done,
            "count": guide.count,
            "total": guide.start + guide.done,
            "target": guide.start + guide.count,
        }


class CalibrationSensor(DeviceSensor):
    """The last calibration from the device: are all voices separable; the report per person."""

    key = "calibration"
    signal = SIGNAL_CALIBRATION
    options_list = ("separable", "overlap", "no_voices")

    def _rows(self) -> dict[str, dict[str, Any]]:
        calibration = self._entry.runtime_data.calibration or {}
        return calibration.get("report", {}).get("speakers", {})

    @property
    def native_value(self) -> str | None:
        if self._entry.runtime_data.calibration is None:
            return None
        rows = [row for row in self._rows().values() if "own_min" in row]
        if not rows:
            return "no_voices"
        return "separable" if all(row.get("separable") for row in rows) else "overlap"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        calibration = self._entry.runtime_data.calibration
        if calibration is None:
            return None
        names = calibration.get("names", {})
        return {
            "margin": calibration["report"].get("margin"),
            "speakers": {
                speaker: {"name": names.get(speaker, speaker), **row}
                for speaker, row in self._rows().items()
            },
        }
