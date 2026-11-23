import json
from dataclasses import replace

import httpx
import pytest

from app.providers.elevenlabs import ElevenLabs
from app.research.vocabulary import ANSWER_LANGUAGE_SPECS
from app.voice.languages import VOICE_LANGUAGES
from app.voice.phrases import SOURCE_WORDS

from .fakes import ALUM, FakeModel, tools, translation, translation_reply
from .test_languages import ELEVEN_V4_TURBO_DOCS, SCRIBE_V3_DOCS
from .test_relay import REPLY_AUDIO, deps, events, live_store, turn_text

ENGLISH_QUESTION = "Why do Ajrakh printers use alum?"
SCRIBE_CODES = {ELEVEN_V4_TURBO_DOCS[name]: code for name, code in SCRIBE_V3_DOCS.items()}


def heard_and_said(language: str) -> tuple[str, str]:
    if language == "en":
        return ENGLISH_QUESTION, ALUM
    autonym = ANSWER_LANGUAGE_SPECS[language].autonym
    return f"{autonym}?", f"{autonym} {autonym}."


@pytest.mark.usefixtures("allowances_an_owner_might_set")
@pytest.mark.parametrize("language", VOICE_LANGUAGES)
async def test_a_relay_turn_hears_and_speaks_each_offered_language(language: str) -> None:
    heard, said = heard_and_said(language)
    seen: list[httpx.Request] = []

    def answer(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/v1/speech-to-text":
            words = [{"text": "x", "start": 0.0, "end": 2.4, "type": "word"}]
            return httpx.Response(200, json={"text": heard, "words": words})
        return httpx.Response(200, content=REPLY_AUDIO)

    voice = ElevenLabs(
        api_key="test-only-elevenlabs-key", client=httpx.AsyncClient(transport=httpx.MockTransport(answer))
    )
    store = live_store(language=language)
    replies = (
        []
        if language == "en"
        else [translation_reply(question=ENGLISH_QUESTION), translation_reply(**{"s1.1": said})]
    )
    relay = replace(deps(store, voice), tools=tools(translated=translation(FakeModel(replies))))
    found = events(await turn_text(store, relay))
    assert f'name="language_code"\r\n\r\n{SCRIBE_CODES[language]}\r\n' in seen[0].content.decode("utf-8")
    speech = json.loads(seen[1].content)
    assert speech["language_code"] == language
    assert speech["text"] == f"{said} {SOURCE_WORDS[language][0]}: GI Journal 188."
    assert found[0] == ("heard", {"text": heard, "language": language})
