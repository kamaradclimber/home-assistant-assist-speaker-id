"""The device's choices for recording a voiceprint: the person and the voice satellite."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EVENT_STATE_CHANGED, STATE_UNAVAILABLE
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import (
    async_track_state_added_domain,
    async_track_state_removed_domain,
)
from homeassistant.helpers.restore_state import RestoreEntity

from . import SpeakerIdConfigEntry, device_info
from .const import ENTITY_IDS


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SpeakerIdConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([PersonSelect(entry), SatelliteSelect(entry)])


class ChoiceSelect(SelectEntity, RestoreEntity):
    """Option = the entity's name, value = its entity id (kept in the runtime data).

    The options follow the entities of `domain` as they come and go; the chosen one survives a
    restart (attribute `value`) even before its entity is back.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False
    key: str
    domain: str

    def __init__(self, entry: SpeakerIdConfigEntry) -> None:
        self._entry = entry
        self._attr_translation_key = self.key
        self._attr_unique_id = f"{entry.entry_id}-{self.key}"
        self.entity_id = ENTITY_IDS[self.key]
        self._attr_device_info = device_info(entry)

    @property
    def value(self) -> str | None:
        return getattr(self._entry.runtime_data, self.key)

    @callback
    def choices(self) -> dict[str, str]:
        """label -> entity id: the entities that are up, and the chosen one even when not."""
        if self.hass is None:
            return {}
        return {
            state.name: state.entity_id
            for state in sorted(self.hass.states.async_all(self.domain), key=lambda s: s.name)
            if state.state != STATE_UNAVAILABLE or state.entity_id == self.value
        }

    @property
    def options(self) -> list[str]:
        return list(self.choices())

    @property
    def current_option(self) -> str | None:
        return next((label for label, v in self.choices().items() if v == self.value), None)

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        return {"value": self.value}

    async def async_select_option(self, option: str) -> None:
        setattr(self._entry.runtime_data, self.key, self.choices()[option])
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self.value is None and (last := await self.async_get_last_state()):
            value = last.attributes.get("value") or self.choices().get(last.state)
            if value is not None:
                setattr(self._entry.runtime_data, self.key, value)
        for track in (async_track_state_added_domain, async_track_state_removed_domain):
            self.async_on_remove(track(self.hass, self.domain, self._entities_changed))
        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_STATE_CHANGED, self._availability_changed)
        )

    @callback
    def _entities_changed(self, _event: Event) -> None:
        self.async_write_ha_state()

    @callback
    def _availability_changed(self, event: Event) -> None:
        old, new = event.data.get("old_state"), event.data.get("new_state")
        if not event.data["entity_id"].startswith(f"{self.domain}.") or old is None or new is None:
            return
        if (old.state == STATE_UNAVAILABLE) != (new.state == STATE_UNAVAILABLE) or (
            old.name != new.name
        ):
            self.async_write_ha_state()


class PersonSelect(ChoiceSelect):
    """Whose voice to record: a person of Home Assistant (the voice is mapped to them)."""

    key = "person"
    domain = "person"


class SatelliteSelect(ChoiceSelect):
    """The voice satellite that guides the recording (no wake word needed)."""

    key = "satellite"
    domain = "assist_satellite"
