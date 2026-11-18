"""Recording a voiceprint and calibrating from the device (selects, number, buttons, sensors),
against a real wyoming-speaker-id on localhost."""

from __future__ import annotations

from homeassistant.components import persistent_notification
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_mock_service,
    mock_restore_cache_with_extra_data,
)

from custom_components.speaker_id.const import CONF_PEOPLE, DOMAIN, ENTITY_IDS
from custom_components.speaker_id.enrollment import (
    NOTIFICATION_ID,
    calibration_message,
    speaker_id_of,
)

from .conftest import Stack, pcm, voice
from .test_integration import _setup, _transcribe

PERSON = ENTITY_IDS["person"]
SATELLITE_SELECT = ENTITY_IDS["satellite"]
SAMPLES = ENTITY_IDS["samples"]
START = ENTITY_IDS["start_enrollment"]
STOP = ENTITY_IDS["stop_enrollment"]
CALIBRATE = ENTITY_IDS["calibrate"]
ENROLLMENT = ENTITY_IDS["enrollment"]
CALIBRATION = ENTITY_IDS["calibration"]
KITCHEN = "assist_satellite.kitchen"
BEDROOM = "assist_satellite.bedroom"


def _home(hass: HomeAssistant) -> None:
    """Two people and two satellites (one of them off)."""
    hass.states.async_set("person.anna_nowak", "home", {"friendly_name": "Anna", "user_id": "u-a"})
    hass.states.async_set("person.jan", "home", {"friendly_name": "Jan"})
    hass.states.async_set(KITCHEN, "idle", {"friendly_name": "Kitchen"})
    hass.states.async_set(BEDROOM, "unavailable", {"friendly_name": "Bedroom"})


async def _device(hass: HomeAssistant, entry: MockConfigEntry, **options):
    _home(hass)
    await _setup(hass, entry, **options)
    asks = async_mock_service(hass, "assist_satellite", "start_conversation")
    says = async_mock_service(hass, "assist_satellite", "announce")
    return asks, says


async def _choose(hass: HomeAssistant, entity_id: str, option: str) -> None:
    await hass.services.async_call(
        "select", "select_option", {"entity_id": entity_id, "option": option}, blocking=True
    )


async def _press(hass: HomeAssistant, entity_id: str) -> None:
    await hass.services.async_call("button", "press", {"entity_id": entity_id}, blocking=True)
    await hass.async_block_till_done()


async def test_the_device_has_the_controls(
    hass: HomeAssistant, stack: Stack, entry: MockConfigEntry
) -> None:
    await _device(hass, entry)
    registry = er.async_get(hass)
    device_ids = {registry.async_get(e).device_id for e in ENTITY_IDS.values()}
    assert len(device_ids) == 1  # all on the one "Assist Speaker ID" device
    assert hass.states.get(PERSON).attributes["options"] == ["Anna", "Jan"]
    assert hass.states.get(SATELLITE_SELECT).attributes["options"] == ["Kitchen"]  # only up
    assert hass.states.get(SAMPLES).state == "10"
    assert hass.states.get(ENROLLMENT).state == "idle"
    assert hass.states.get(CALIBRATION).state == "unknown"  # until the first calibration


async def test_satellite_options_follow_the_satellites(
    hass: HomeAssistant, stack: Stack, entry: MockConfigEntry
) -> None:
    await _device(hass, entry)
    hass.states.async_set(BEDROOM, "idle", {"friendly_name": "Bedroom"})
    hass.states.async_set("assist_satellite.hall", "idle", {"friendly_name": "Hall"})
    await hass.async_block_till_done()
    assert hass.states.get(SATELLITE_SELECT).attributes["options"] == ["Bedroom", "Hall", "Kitchen"]


@pytest.mark.parametrize(
    ("choose", "message"),
    [({}, "Person"), ({PERSON: "Anna"}, "Satellite")],
)
async def test_start_says_what_to_choose_first(
    hass: HomeAssistant, stack: Stack, entry: MockConfigEntry, choose, message
) -> None:
    asks, _ = await _device(hass, entry)
    for entity_id, option in choose.items():
        await _choose(hass, entity_id, option)
    with pytest.raises(HomeAssistantError) as err:
        await _press(hass, START)
    assert err.value.translation_key == (
        "choose_person" if message == "Person" else "choose_satellite"
    )
    assert not asks and stack.service.enrollment is None


async def test_start_records_the_person_on_the_satellite(
    hass: HomeAssistant, stack: Stack, entry: MockConfigEntry
) -> None:
    """No action to write: person, satellite, samples, Start - the satellite guides."""
    asks, says = await _device(hass, entry)
    await _choose(hass, PERSON, "Anna")
    await _choose(hass, SATELLITE_SELECT, "Kitchen")
    await hass.services.async_call(
        "number", "set_value", {"entity_id": SAMPLES, "value": 2}, blocking=True
    )
    await _press(hass, START)

    assert stack.service.enrollment.speaker == "anna_nowak"  # the person's id as the voice
    assert stack.service.store.speakers["anna_nowak"].name == "Anna"
    assert asks[0].data["entity_id"] == KITCHEN
    assert "Anna" in asks[0].data["start_message"]
    # the voice belongs to the person from now on - without reloading (the guide goes on)
    assert entry.options[CONF_PEOPLE] == {"anna_nowak": "person.anna_nowak"}
    guide = entry.runtime_data.guide
    assert guide is not None and guide.active
    state = hass.states.get(ENROLLMENT)
    assert state.state == "recording"
    expected = {"name": "Anna", "done": 0, "count": 2, "target": 2, "satellite": KITCHEN}
    assert {k: state.attributes[k] for k in expected} == expected

    hass.states.async_set(KITCHEN, "listening")
    await _transcribe(hass, pcm(voice(220, seed=1)))
    hass.states.async_set(KITCHEN, "idle")
    await hass.async_block_till_done()
    assert hass.states.get(ENROLLMENT).attributes["done"] == 1  # progress on the sensor

    await _press(hass, STOP)
    assert hass.states.get(ENROLLMENT).state == "idle"
    assert stack.service.enrollment is None
    assert says == [] or says[-1].data["entity_id"] == KITCHEN


async def test_a_mapped_voice_keeps_its_id(
    hass: HomeAssistant, stack: Stack, entry: MockConfigEntry
) -> None:
    """A person already mapped in the options adds to that voice, not to a new one."""
    stack.enroll("janek", "Janek", 180)
    await _device(hass, entry, **{CONF_PEOPLE: {"janek": "person.jan"}})
    await _choose(hass, PERSON, "Jan")
    await _choose(hass, SATELLITE_SELECT, "Kitchen")
    await _press(hass, START)
    assert stack.service.enrollment.speaker == "janek"
    assert stack.service.enrollment.start == 3  # another series adds to the saved samples
    assert entry.options[CONF_PEOPLE] == {"janek": "person.jan"}


async def test_the_choices_survive_a_restart(
    hass: HomeAssistant, stack: Stack, entry: MockConfigEntry
) -> None:
    from homeassistant.core import State

    mock_restore_cache_with_extra_data(
        hass,
        [
            (State(PERSON, "Jan", {"value": "person.jan"}), {}),
            (State(SATELLITE_SELECT, "Kitchen", {"value": KITCHEN}), {}),
            (
                State(SAMPLES, "15"),
                {
                    "native_value": 15,
                    "native_min_value": 1,
                    "native_max_value": 50,
                    "native_step": 1,
                    "native_unit_of_measurement": None,
                },
            ),
        ],
    )
    await _device(hass, entry)
    runtime = entry.runtime_data
    assert (runtime.person, runtime.satellite, runtime.samples) == ("person.jan", KITCHEN, 15)
    assert hass.states.get(PERSON).state == "Jan"


async def test_calibrate_shows_the_result(
    hass: HomeAssistant, stack: Stack, entry: MockConfigEntry
) -> None:
    stack.enroll("anna_nowak", "Anna", 220)
    stack.enroll("jan", "Jan", 180)
    await _device(hass, entry, **{CONF_PEOPLE: {"anna_nowak": "person.anna_nowak"}})
    await _press(hass, CALIBRATE)

    notes = persistent_notification._async_get_or_create_notifications(hass)
    note = notes[NOTIFICATION_ID]
    assert note["title"] == "Assist Speaker ID: calibration"
    assert "| Anna | 3 |" in note["message"] and "| Jan | 3 |" in note["message"]
    assert "Configure" in note["message"]  # where the threshold is set
    state = hass.states.get(CALIBRATION)
    assert state.state in ("separable", "overlap")
    assert state.attributes["speakers"]["anna_nowak"]["name"] == "Anna"
    assert "suggested_threshold" in state.attributes["speakers"]["jan"]
    # calibrating from the device changes nothing
    assert stack.service.store.speakers["jan"].threshold is None


async def test_calibrate_without_voices(
    hass: HomeAssistant, stack: Stack, entry: MockConfigEntry
) -> None:
    await _device(hass, entry)
    await _press(hass, CALIBRATE)
    assert hass.states.get(CALIBRATION).state == "no_voices"
    note = persistent_notification._async_get_or_create_notifications(hass)[NOTIFICATION_ID]
    assert "Start recording" in note["message"]


def test_calibration_message_in_polish(hass: HomeAssistant) -> None:
    hass.config.language = "pl"
    report = {
        "margin": 0.05,
        "speakers": {
            "anna": {"samples": 10, "own_min": 0.71, "own_p10": 0.78, "own_mean": 0.8,
                     "others_max": 0.31, "separable": True, "suggested_threshold": 0.54},
            "ola": {"samples": 10, "own_min": 0.6, "own_p10": 0.74, "own_mean": 0.7,
                    "others_max": 0.68, "separable": False, "suggested_threshold": 0.71},
            "tosia": {"samples": 2, "note": "needs at least 3 samples"},
        },
    }  # fmt: skip
    message = calibration_message(hass, report, {"anna": "Anna", "ola": "Ola"})
    assert "| Anna | 10 | 0.71 | 0.31 | tak | 0.54 |" in message
    assert "| Ola | 10 | 0.60 | 0.68 | **nie** | 0.71 |" in message
    assert "| tosia | 2 | za mało próbek |" in message
    assert "nakładają (Ola)" in message and "Konfiguruj" in message and "0.05" in message


@pytest.mark.parametrize(
    ("object_id", "speaker"),
    [("anna", "anna"), ("anna_nowak", "anna_nowak"), ("Ola-Kowalska", "ola_kowalska"),
     ("x" * 40, "x" * 32), ("__", "person")],
)  # fmt: skip
def test_speaker_id_of(object_id: str, speaker: str) -> None:
    assert speaker_id_of(object_id) == speaker


async def test_the_actions_still_work(
    hass: HomeAssistant, stack: Stack, entry: MockConfigEntry
) -> None:
    """speaker_id.start_enrollment / stop_enrollment and the sensor show the same."""
    await _device(hass, entry)
    await hass.services.async_call(
        DOMAIN, "start_enrollment",
        {"speaker": "jan", "name": "Jan", "count": 3, "satellite": KITCHEN}, blocking=True,
    )  # fmt: skip
    await hass.async_block_till_done()
    assert hass.states.get(ENROLLMENT).state == "recording"
    await hass.services.async_call(DOMAIN, "stop_enrollment", {}, blocking=True)
    await hass.async_block_till_done()
    assert hass.states.get(ENROLLMENT).state == "idle"
