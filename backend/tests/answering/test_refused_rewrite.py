import pytest
from pydantic import ValidationError

from app.composer.candidates import compose_request
from app.composer.composer import ModelComposer
from app.composer.prompt import REGENERATE_SYSTEM_PROMPT
from app.research.composition import ComposeFocus, ComposeRequest, RefusedSentence
from app.services.answer_events import CitedClaims
from app.services.section_blocks import DroppedSentence, KeptSentence
from app.services.section_rewrite import drop_reasons, rewrite_request

from ..composer.fixtures import (
    ALUM_CLAIM_ID,
    GUESS_CLAIM_ID,
    QUESTION,
    pack,
    quote,
    replacements,
    section_reply,
    sentence,
)
from ..planner.fakes import FakeModel
from .fakes import FakeStore, SectionModel, pipeline, streamed
from .piece_fakes import MemoryPieces
from .test_answer_flow import LAKE_PAPER, events
from .test_sections import asked

CHEMISTRY = ComposeFocus(discipline="CHEMISTRY", title="The chemistry")
ALUM_SAID = sentence(
    "Alum is the mordant that binds alizarin to cotton.",
    quote(ALUM_CLAIM_ID, "Alum is the mordant that binds alizarin to cotton"),
)
LAKE_SAID = sentence(
    "Mordant baths held 8 g/L alum and were heated to 60 °C.",
    quote(LAKE_PAPER, "Mordanting baths of 8 g/L alum were heated to 60 °C"),
)
GUESS_SAID = sentence(
    "Lime in the wash water may brighten the red.",
    quote(GUESS_CLAIM_ID, "Lime in the wash water may brighten the red"),
)
UNKEPT = KeptSentence(LAKE_SAID["text"], (), (LAKE_PAPER,), False)


def refused_request() -> ComposeRequest:
    first = compose_request(pack(), QUESTION, focus=CHEMISTRY)
    again = rewrite_request(first, [DroppedSentence(UNKEPT, ("cites no stored claim",))], CitedClaims())
    assert again is not None
    return again


def test_a_rewrite_offers_only_the_section_s_stored_claims_and_names_each_refused_sentence() -> None:
    again = refused_request()
    assert [candidate.id for candidate in again.candidates] == [str(ALUM_CLAIM_ID), str(GUESS_CLAIM_ID)]
    assert again.refused == [RefusedSentence(text=LAKE_SAID["text"], problems=["cites no stored claim"])]
    assert again.focus == CHEMISTRY


def test_no_rewrite_is_asked_without_a_refused_sentence_or_a_section() -> None:
    first = compose_request(pack(), QUESTION, focus=CHEMISTRY)
    late = [DroppedSentence(UNKEPT, ("cites no stored claim",))]
    assert rewrite_request(first, [], CitedClaims()) is None
    assert rewrite_request(first.model_copy(update={"focus": None}), late, CitedClaims()) is None


def test_only_a_section_of_stored_claims_is_written_again() -> None:
    first = compose_request(pack(), QUESTION, focus=CHEMISTRY)
    with pytest.raises(ValidationError):
        ComposeRequest(
            question=first.question,
            craft=first.craft,
            candidates=first.candidates,
            searched=first.searched,
            focus=CHEMISTRY,
            refused=[RefusedSentence(text=LAKE_SAID["text"], problems=["cites no stored claim"])],
        )


async def test_the_composer_rewrites_refused_sentences_once_with_the_regenerate_prompt() -> None:
    model = FakeModel([replacements((0, ALUM_SAID))])
    composed = await ModelComposer(model=model).compose(refused_request())
    (call,) = model.calls
    assert call["system"] == REGENERATE_SYSTEM_PROMPT
    assert "Failed sentence 0: cites no stored claim" in call["user"]
    (section,) = composed.sections
    assert [one.text for one in section.sentences] == [ALUM_SAID["text"]]


async def test_a_rewrite_that_still_cites_unkept_evidence_gives_nothing() -> None:
    composed = await ModelComposer(model=FakeModel([replacements((0, LAKE_SAID))])).compose(refused_request())
    assert composed.sections == [] and composed.not_enough_evidence is not None


def test_dropped_sentences_are_counted_by_reason() -> None:
    dropped = [
        DroppedSentence(UNKEPT, ("cites no stored claim",)),
        DroppedSentence(UNKEPT, ("cites no stored claim", "states 60, which no cited claim or quote holds")),
    ]
    assert drop_reasons(dropped) == {"cites no stored claim": 2, "states": 1}


async def test_a_section_whose_evidence_sentence_lost_its_write_back_is_rewritten_from_stored_claims() -> (
    None
):
    model = SectionModel(
        replies={"The chemistry": [section_reply(LAKE_SAID, GUESS_SAID), replacements((0, ALUM_SAID))]}
    )
    held = MemoryPieces(held_fields=("CHEMISTRY",))
    found = events(
        await streamed(asked(), pipeline(store=FakeStore(written={}), compose_model=model, pieces=held))
    )
    assert [call["system"] == REGENERATE_SYSTEM_PROMPT for call in model.calls] == [False, True]
    (block,) = [payload["block"] for name, payload in found if name == "block"]
    assert [one["text"] for one in block["sentences"]] == [ALUM_SAID["text"]]
