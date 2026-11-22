import pytest
from pydantic import ValidationError

from app.schemas.admin import VoiceSettingsUpdate
from app.services import app_settings

DEFAULT_VOICE = {"transport": "RELAY", "maxLiveSessions": 5, "voiceId": "JBFqnCBsd6RMkjVDRZzb"}


def test_the_voice_block_shows_each_setting_beside_its_default() -> None:
    assert app_settings.voice_view(dict(app_settings.DEFAULTS)) == {
        **DEFAULT_VOICE,
        "defaults": DEFAULT_VOICE,
    }
    chosen = {**app_settings.DEFAULTS, "voice.transport": "AGENT", "voice.max_live_sessions": 20}
    view = app_settings.voice_view(chosen)
    assert (view["transport"], view["maxLiveSessions"], view["defaults"]) == ("AGENT", 20, DEFAULT_VOICE)


def test_only_the_settings_sent_are_changed() -> None:
    sent = VoiceSettingsUpdate(maxLiveSessions=12).model_dump()
    assert app_settings.voice_changes(sent) == {"voice.max_live_sessions": 12}
    every = VoiceSettingsUpdate(transport="AGENT", maxLiveSessions=0, voiceId="Xb7hH8MSUJpSbSDYk0k2")
    assert app_settings.voice_changes(every.model_dump()) == {
        "voice.transport": "AGENT",
        "voice.max_live_sessions": 0,
        "voice.voice_id": "Xb7hH8MSUJpSbSDYk0k2",
    }


@pytest.mark.parametrize(
    "sent",
    [
        {"transport": "PHONE"},
        {"maxLiveSessions": -1},
        {"maxLiveSessions": 101},
        {"voiceId": "not a voice"},
        {"voiceId": ""},
        {"agentId": "agent_1"},
    ],
)
def test_a_setting_off_its_range_is_refused(sent: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        VoiceSettingsUpdate.model_validate(sent)
