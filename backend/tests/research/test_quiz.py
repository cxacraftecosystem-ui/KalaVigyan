import uuid
from typing import Any

import pytest
from pydantic import ValidationError

from app.research.blocks import ExplainerSentence
from app.research.blocks_learning import QUIZ_BLANK, QUIZ_OPTIONS_MAX
from app.research.explainer import Explainer
from app.research.quiz import (
    QUIZ_DISTRACTORS_MAX,
    QUIZ_TERM_MIN_CHARS,
    ExplainerQuiz,
    explainer_quiz,
    quiz_block,
    quiz_sentences,
)

from ..contracts.explainer_golden import DOCUMENT, golden_json

WATER_ALUM_CLAIM = "826c1d72"
DOCUMENT_QUIZ = [
    (
        "Outlines where white is required are printed with a carved block and a lime and tree-gum _____.",
        ["harde", "kut", "mavi", "resist-paste"],
        3,
    ),
    (
        "Presence of iron in the water supply dulls and darkens the final result; _____, tin or chrome "
        "deposits help brighten colours.",
        ["alum", "gach", "indigo", "soft-water"],
        0,
    ),
    (
        "Ajrakh colours come from _____, madder and iron acetate.",
        ["gach", "indigo", "kut", "resist-paste"],
        1,
    ),
    (
        "Areas where black is required are printed with _____ paste, usually an infill (datla) between "
        "khariyanu outlines.",
        ["alizarin", "harde", "kut", "mavi"],
        2,
    ),
    (
        "Ajrakh printing got concentrated where extra _____ was available.",
        ["gach", "indigo", "resist-paste", "soft-water"],
        3,
    ),
    (
        "_____ with alum is printed where larger red areas are required (red ground gudh or mavi infill); the "
        "clay and millet resist indigo while the alum acts as mordant.",
        ["gach", "harde", "kut", "resist-paste"],
        0,
    ),
    (
        "Printed on _____-treated cloth, kut develops a deep fast chocolate-black as iron reacts with the "
        "tannic acid.",
        ["alizarin", "alum", "harde", "mavi"],
        2,
    ),
    (
        "Pa, a smooth paste of alum in tamarind-seed paste, is printed with blocks patterned for the _____ "
        "areas where red is required.",
        ["alizarin", "indigo", "mavi", "soft-water"],
        2,
    ),
    (
        "_____ crystals or steeped madder roots are heated in a copper pot; dyeing the purest reds continues "
        "for up to four hours.",
        ["alizarin", "alum", "indigo", "soft-water"],
        0,
    ),
]


def document() -> Explainer:
    return Explainer.model_validate(golden_json(DOCUMENT))


def every_claim(explainer: Explainer) -> frozenset[str]:
    return frozenset(c.claim_id for s in explainer.sections for b in s.blocks for c in b.citations())


def sentence(sentence_id: str, text: str, terms: list[tuple[str, str]], claim: str, quote: str = "") -> Any:
    return ExplainerSentence.model_validate(
        {
            "id": sentence_id,
            "text": text,
            "level": "PROVISIONAL",
            "citations": [
                {
                    "id": f"cite-{sentence_id}",
                    "claimId": claim,
                    "sourceId": "source-1",
                    "quote": quote or text,
                    "locator": "p. 1",
                    "context": None,
                    "evidence": "QUOTED",
                    "level": "PROVISIONAL",
                }
            ],
            "translated": False,
            "terms": [{"text": shown, "termKey": key} for shown, key in terms],
        }
    )


ALUM = sentence("a", "Alum fixes the red.", [("Alum", "alum")], "c1", "Alum fixes the red dye of madder.")
MADDER = sentence("b", "Madder gives the red.", [("Madder", "madder")], "c2")
INDIGO = sentence("c", "Indigo gives the blue.", [("Indigo", "indigo")], "c3")
LIME = sentence("d", "Lime is used in the vat.", [("Lime", "lime")], "c4")


def test_the_document_quiz_blanks_its_own_sentences_with_terms_of_other_claims() -> None:
    quiz = explainer_quiz(document(), visible_claim_ids=every_claim(document()))
    assert quiz is not None
    found = [(q.prompt, [o.term_key for o in q.options], q.answer) for q in quiz.quiz.questions]
    assert found == DOCUMENT_QUIZ
    texts = {s.text for sec in document().sections for b in sec.blocks for s in b.cited_sentences()}
    assert all(o.sentence.text in texts for q in quiz.quiz.questions for o in q.options)
    assert quiz.answer_id == document().answer_id and quiz.language == "en"


def test_a_quiz_answer_whose_claim_is_no_longer_shown_is_dropped() -> None:
    visible = frozenset(c for c in every_claim(document()) if not c.startswith(WATER_ALUM_CLAIM))
    quiz = explainer_quiz(document(), visible_claim_ids=visible)
    assert quiz is not None
    cited = {c.claim_id[:8] for q in quiz.quiz.questions for o in q.options for c in o.sentence.citations}
    assert WATER_ALUM_CLAIM not in cited
    assert all("_____, tin or chrome" not in q.prompt for q in quiz.quiz.questions)
    assert explainer_quiz(document(), visible_claim_ids=frozenset()) is None


def test_a_distractor_is_never_drawn_from_the_keyed_claim() -> None:
    quiz = explainer_quiz(document(), visible_claim_ids=every_claim(document()))
    assert quiz is not None
    for question in quiz.quiz.questions:
        keyed = question.options[question.answer]
        claims = {c.claim_id for c in keyed.sentence.citations}
        for number, option in enumerate(question.options):
            if number != question.answer:
                assert not claims & {c.claim_id for c in option.sentence.citations}
                assert option.term_key != keyed.term_key


def test_a_term_the_keyed_sentence_or_its_quote_states_is_no_distractor() -> None:
    block = quiz_block([[ALUM, MADDER, INDIGO, LIME]], block_id="t")
    assert block is not None
    first = block.questions[0]
    assert first.prompt == f"{QUIZ_BLANK} fixes the red."
    assert [o.term_key for o in first.options] == ["alum", "indigo", "lime"]


def test_a_sentence_resting_on_the_keyed_claim_offers_no_distractor() -> None:
    kut = sentence("e", "Kut is printed for black.", [("Kut", "kut")], "c1")
    block = quiz_block([[ALUM, kut, INDIGO, LIME]], block_id="t")
    assert block is not None
    assert "kut" not in [o.term_key for o in block.questions[0].options]


def test_a_question_needs_two_distractors_and_terms_of_three_letters() -> None:
    short = sentence("f", "Pa is a paste of alum.", [("Pa", "pa")], "c5")
    assert quiz_block([[ALUM, INDIGO]], block_id="t") is None
    block = quiz_block([[short, ALUM, INDIGO, LIME]], block_id="t")
    assert block is not None
    assert all(len(o.text) >= QUIZ_TERM_MIN_CHARS for q in block.questions for o in q.options)
    assert all(q.options[q.answer].term_key != "pa" for q in block.questions)


def test_the_quiz_visits_each_section_in_turn_and_keys_each_term_once() -> None:
    again = sentence("g", "Alum is boiled down.", [("Alum", "alum")], "c6")
    block = quiz_block([[ALUM, MADDER, again], [INDIGO, LIME]], block_id="t")
    assert block is not None
    keys = [q.options[q.answer].term_key for q in block.questions]
    assert keys == ["alum", "indigo", "madder", "lime"]


def test_a_cloze_that_reads_like_an_earlier_one_is_asked_once() -> None:
    first = sentence("h", "Alum is a mordant.", [("Alum", "alum")], "c7")
    second = sentence("i", "Tin is a mordant.", [("Tin", "tin")], "c8")
    block = quiz_block([[first, second, INDIGO, LIME]], block_id="t")
    assert block is not None
    assert [q.prompt for q in block.questions].count(f"{QUIZ_BLANK} is a mordant.") == 1


def test_the_limits_hold() -> None:
    many = [
        sentence(f"m{n}", f"Term{n:02d} is used in step {n}.", [(f"Term{n:02d}", f"term{n:02d}")], f"k{n}")
        for n in range(20)
    ]
    block = quiz_block([many], block_id="t", limit=4)
    assert block is not None and len(block.questions) == 4
    assert all(len(q.options) == 1 + QUIZ_DISTRACTORS_MAX <= QUIZ_OPTIONS_MAX for q in block.questions)
    assert [o.sentence.id for o in block.questions[1].options] == [f"t.q2.{n}" for n in range(1, 5)]


def test_a_quiz_lists_the_sources_it_cites_in_order() -> None:
    quiz = explainer_quiz(document(), visible_claim_ids=every_claim(document()))
    assert quiz is not None
    payload = quiz.model_dump(mode="json", by_alias=True)
    with pytest.raises(ValidationError, match="every source it cites once"):
        ExplainerQuiz.model_validate(payload | {"sources": list(reversed(payload["sources"]))})
    assert ExplainerQuiz.model_validate(payload | {"answerId": str(uuid.UUID(int=1))}).quiz == quiz.quiz


def test_a_whole_answer_quiz_asks_from_its_lede_first_and_chosen_sections_leave_it_out() -> None:
    answered = Explainer.model_validate(golden_json("explainer.lede.golden.json"))
    whole = [[s.id for s in group] for group in quiz_sentences(answered)]
    assert whole == [
        ["lede.1", "lede.2", "lede.3"],
        ["s1.b1.1", "s1.b1.2"],
        ["s2.b1.1", "s2.b1.2"],
        ["s3.b1.1", "s3.b1.2"],
    ]
    assert [[s.id for s in group] for group in quiz_sentences(answered, ["s2"])] == [["s2.b1.1", "s2.b1.2"]]
