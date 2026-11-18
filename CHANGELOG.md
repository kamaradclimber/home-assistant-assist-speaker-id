# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versions: [SemVer](https://semver.org/).
Add-on (service) changes: [speaker_id/CHANGELOG.md](speaker_id/CHANGELOG.md).

## [0.3.0] - 2026-11-18

### Added
- **Recording a voiceprint from the device**, like Wake Word Recorder: the Assist Speaker ID device
  has **Person** (a person of Home Assistant), **Satellite**, **Samples to record** (1-50, 10 by
  default) and the buttons **Start recording** / **Stop recording** - the satellite guides the
  recording, no `speaker_id.start_enrollment` to write. The voice gets the person's id and is mapped
  to the person in the options at once (without reloading, the recording goes on); a person already
  mapped adds to their voice. The **Recording** sensor shows the progress (`done`, `total`,
  `target`), also for the action. The choices survive a restart.
- **Calibrate** button: the report shows at once as a notification (a table per person: samples,
  worst own, closest other, separable, suggested threshold) and in the **Calibration** sensor
  (voices separable / overlap). It changes nothing; thresholds stay in the options.

### Changed
- The conversation agent streams its reply when the agent requests are passed to streams, so text
  to speech starts on the first sentence of a streaming LLM agent instead of waiting for the whole
  answer (#1, thanks @OptikCrash). A non-streaming agent and the agent's own replies work as before.

### Fixed
- Recording in a quiet room no longer saves noise as the person's voice: an utterance without words
  (Whisper heard nothing, or only its usual „Dziękuję.”) is no sample, and the satellite says
  „Nic nie usłyszałem.” instead of „Za krótko.”. Needs the add-on (service)
  0.3.0.

## [0.2.1] - 2026-11-12

### Added
- `async_last_recording(hass, max_age=None)` in `api.py`: the WAV of the last utterance for another
  integration to play, e.g. the [Intercom](https://github.com/witold-gren/home-assistant-intercom)
  through Assist Router („Komunikat do kuchni, ...” in the speaker's own voice); None without a
  fresh one.

## [0.2.0] - 2026-10-25

### Added
- Probable speaker: an unrecognized voice (below its person's threshold or too close to the
  runner-up) whose best similarity reaches the new option **Probable speaker from** (default
  0.40) is reported as `probable`, `probable_name`, `probable_person`, `probable_user_id` -
  sensor attributes, the `speaker_id_identified` event and `get_speaker()`. "Agent with
  speaker" adds a "probably {name}" prompt line; nothing runs as that person's user.
- Sensor attribute `user_id` (the recognized person's HA user).
- Adding samples in series: another enrollment adds to the saved samples and the satellite counts
  all of them („Dogrywam próbki głosu: Anna, zapisane są 20, nagrywam do 30”, „Nagrano 24 z 30”,
  „Gotowe. Wzorzec głosu: Anna, liczba próbek: 30.”). Needs the service 0.2.0, which keeps the
  recording of every sample; an older service counts the series only.
- Actions `speaker_id.reset_speaker` (delete the samples and recordings, keep the person) and
  `speaker_id.rebuild_voiceprints` (embed all samples again from their recordings). The thresholds
  options show samples and recordings per person; `delete_speaker` deletes the recordings too.

### Changed
- Entity ids no longer depend on the HA language: `sensor.speaker_id_last_speaker`,
  `stt.speaker_id_speech_to_text`, `conversation.speaker_id_agent`. Default ids of 0.1.x
  (e.g. `sensor.speaker_id_ostatni_mowca`) are renamed on setup; ids changed by hand stay.
  Pipelines that use the old speech-to-text id must be switched to the new one.

## [0.1.1] - 2026-10-25

### Added
- Logo images (`logo`, `dark_logo`) next to the icons in `brand/`.

## [0.1.0] - 2026-10-25

First public release of the Assist Speaker ID integration (domain `speaker_id`).

### Added
- `prefer_players` for announcements (`speaker_id.announce_last`, `async_announce_last()`):
  one speaker per room - an available media player (e.g. a HomePod) plays instead of the
  satellite in that room; a player in state `off` (a disconnected HomePod in Apple TV) counts as
  unavailable and the satellite plays; the room the announcement comes from gets nothing.
- Speech to text with the speaker ("Speech to text with speaker"); the result is available to
  the conversation agent of the same pipeline run (`get_speaker()`), the "Last speaker" sensor,
  the `speaker_id_identified` event.
- "Agent with speaker": passes requests to the chosen agent with a line about the speaker in
  the prompt.
- Guided voiceprint enrollment on a satellite (without the wake word), short agent replies
  during enrollment (`enrollment_reply()`), threshold calibration.
- Options: agent and people (linking voices to HA persons), recognition thresholds.
- "Reconfigure": change the host, ports and API token without losing the options.
- Announcements (intercom): `speaker_id.announce_last` - the speaker's recording on other speakers.
