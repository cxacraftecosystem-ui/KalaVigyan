from typing import Any

from app.composer.candidates import compose_request
from app.composer.drafts import WHOLE_ANSWER_FORM, AnswerForm, parsed_answer

from .fixtures import ALUM_CLAIM_ID, QUESTION, pack, quote, sentence

CLAIM = str(ALUM_CLAIM_ID)
SAID = sentence(
    "Alum binds alizarin to cotton in Ajrakh.",
    quote(CLAIM, "Alum is the mordant that binds alizarin to cotton"),
)


def reply(sections: int, sentences: int, follow_ups: int) -> dict[str, Any]:
    return {
        "sections": [
            {"heading": f"Part {chr(65 + n)}", "sentences": [SAID] * sentences} for n in range(sections)
        ],
        "followUps": [f"Which plant gives shade {chr(65 + n)}?" for n in range(follow_ups)],
    }


def test_the_whole_answer_form_is_six_sections_of_eight_sentences_and_five_follow_ups() -> None:
    assert AnswerForm(sections=6, sentences=8, follow_ups=5) == WHOLE_ANSWER_FORM


def test_a_whole_answer_reply_is_trimmed_to_its_form() -> None:
    allowed = compose_request(pack(), QUESTION).allowed
    draft = parsed_answer(reply(9, 11, 7), allowed)
    assert [section.heading for section in draft.sections] == [f"Part {letter}" for letter in "ABCDEF"]
    assert {len(section.sentences) for section in draft.sections} == {8}
    assert len(draft.follow_ups) == 5


def test_a_narrower_form_trims_to_its_own_limits() -> None:
    allowed = compose_request(pack(), QUESTION).allowed
    spoken = AnswerForm(sections=1, sentences=3, follow_ups=0)
    draft = parsed_answer(reply(2, 5, 2), allowed, form=spoken)
    assert [section.heading for section in draft.sections] == ["Part A"]
    assert len(draft.sections[0].sentences) == 3
    assert draft.follow_ups == ()
