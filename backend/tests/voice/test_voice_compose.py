import json

from app.composer.candidates import compose_request
from app.voice.compose import VOICE_FORM, voice_composed

from ..composer.fixtures import ALUM_CLAIM_ID, QUESTION, pack, quote, sentence
from .fakes import FakeModel

SAID = sentence(
    "Alum binds alizarin to cotton in Ajrakh.",
    quote(ALUM_CLAIM_ID, "Alum is the mordant that binds alizarin to cotton"),
)
LONG_REPLY = json.dumps(
    {
        "sections": [
            {"heading": "Answer", "sentences": [SAID] * 5},
            {"heading": "More", "sentences": [SAID] * 2},
        ],
        "followUps": ["Which plant gives the red?", "Why is the cloth washed?"],
    }
)


def test_the_voice_form_is_one_section_of_three_sentences_and_no_follow_ups() -> None:
    assert (VOICE_FORM.sections, VOICE_FORM.sentences, VOICE_FORM.follow_ups) == (1, 3, 0)


async def test_a_longer_voice_reply_is_trimmed_to_one_section_of_three_sentences() -> None:
    composed = await voice_composed(FakeModel([LONG_REPLY]), compose_request(pack(), QUESTION))
    assert [section.heading for section in composed.sections] == ["Answer"]
    assert len(composed.sections[0].sentences) == 3
    assert composed.follow_ups == []
