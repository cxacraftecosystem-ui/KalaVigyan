from typing import Any

from pydantic import TypeAdapter

from app.research.explainer import Block
from app.services.explainer_events import ExplainerStream
from app.services.gap_routing import routed_gaps

from .indigo_blocks import prose
from .indigo_claims import EDWARDS, IJTK, SOURCES, Claim
from .test_streamed_indigo import Recorded

BLOCK = TypeAdapter(Block)
REFS = {ref["id"]: ref for ref in SOURCES}
CAST = Claim("bidri-cast", "Bidri ware is cast from an alloy of zinc and copper.", (IJTK,))
PATINA = Claim(
    "bidri-patina",
    "The black patina protects the ware from corrosion, but the compounds that form it have not been "
    "identified.",
    (EDWARDS,),
)
ORIGINS = Claim("bidri-origins", "The craft's origins are unknown.", (EDWARDS,))


def asked(recorded: Recorded) -> list[dict[str, Any]]:
    return [data["sentence"] for name, data in recorded.events if name == "open_question"]


async def test_a_sentence_admitting_a_gap_goes_to_the_open_questions_with_its_citation() -> None:
    recorded = Recorded()
    stream = ExplainerStream(recorded, language="en")
    said = BLOCK.validate_python(prose("s1.b1", (CAST.text, (CAST,)), (PATINA.text, (PATINA,))))
    (sent,) = await stream.blocks("s1", [said], REFS)
    assert [sentence.text for sentence in sent.cited_sentences()] == [CAST.text]
    (question,) = asked(recorded)
    assert question["text"] == PATINA.text
    assert question["id"] == "open.1"
    assert [citation["claimId"] for citation in question["citations"]] == [PATINA.id]
    names = [name for name, _ in recorded.events]
    assert names.index("source", names.index("block") + 1) < names.index("open_question")
    assert EDWARDS["id"] in {ref["id"] for ref in recorded.sources()}


async def test_a_block_that_only_admits_gaps_is_not_shown_but_every_gap_is_asked() -> None:
    recorded = Recorded()
    stream = ExplainerStream(recorded, language="en")
    gaps = BLOCK.validate_python(prose("s2.b1", (ORIGINS.text, (ORIGINS,)), (PATINA.text, (PATINA,))))
    assert await stream.blocks("s2", [gaps], REFS) == []
    assert [question["text"] for question in asked(recorded)] == [ORIGINS.text, PATINA.text]
    assert not [name for name, _ in recorded.events if name == "block"]


async def test_a_gap_is_asked_in_the_answer_language() -> None:
    async def in_hindi(block: Block) -> Block:
        payload = block.model_dump(mode="json", by_alias=True)
        for sentence in payload["sentences"]:
            sentence |= {
                "text": f"हिंदी: {sentence['text']}",
                "translated": True,
                "original": sentence["text"],
            }
        return BLOCK.validate_python(payload)

    recorded = Recorded()
    stream = ExplainerStream(recorded, language="hi")
    gaps = BLOCK.validate_python(prose("s2.b1", (ORIGINS.text, (ORIGINS,))))
    await stream.blocks("s2", [gaps], REFS, in_language=in_hindi)
    (question,) = asked(recorded)
    assert (question["text"], question["original"]) == (f"हिंदी: {ORIGINS.text}", ORIGINS.text)


def test_a_block_with_no_gap_passes_untouched() -> None:
    said = BLOCK.validate_python(prose("s1.b1", (CAST.text, (CAST,))))
    routed = routed_gaps([said])
    assert routed.blocks[0] is said
    assert routed.gaps == ()
