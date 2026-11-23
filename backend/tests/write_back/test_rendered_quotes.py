import uuid

from app.research.composition import ComposedAnswer, ComposedSection, ComposedSentence, QuotedSpan
from app.research.evidence import Quote
from app.services.write_back_plan import QUOTED_REASON, write_back_plan
from app.sources.adapter import build_document

from ..composer.fixtures import pack, packed
from ..research.fixtures import evidence_item
from .names import AJRAKH_NAMES

ANSWER_ID = uuid.UUID("0b1c2d3e-4f50-4617-8293-a4b5c6d7e8f9")
HINDI_PAGE = "wikipedia:hi:4242"
HINDI_QUOTE = "फिटकरी लाल रंग को सूती कपड़े पर पक्का करती है"
HINDI_TEXT = f"अजरख की छपाई में {HINDI_QUOTE}। रंगाई के बाद कपड़ा धोया जाता है।"
RENDERED = "Alum fixes the red colour on cotton cloth"
STATED = "Alum fixes the red colour on cotton cloth in Ajrakh."
HINDI_ITEM = evidence_item(
    id=HINDI_PAGE,
    adapter="wikipedia",
    tier="T4",
    sourceType="ENCYCLOPEDIA",
    url="https://hi.wikipedia.org/wiki/Ajrakh",
    title="अजरख",
    doi=None,
    quotes=[],
)


def hindi_pack() -> object:
    return pack(
        evidence=(packed(HINDI_ITEM, "wikipedia"),),
        documents=(build_document(HINDI_ITEM, HINDI_TEXT, "FULL_TEXT"),),
    )


def composed(renderings: dict[str, str]) -> ComposedAnswer:
    sentence = ComposedSentence(
        text=STATED, evidence_ids=[HINDI_PAGE], spans=[QuotedSpan(ref=HINDI_PAGE, text=HINDI_QUOTE)]
    )
    section = ComposedSection(heading="Mordant", sentences=[sentence])
    return ComposedAnswer(sections=[section], renderings=renderings)


def test_a_sentence_resting_on_a_hindi_passage_is_written_back_quoted_by_its_rendering() -> None:
    plan = write_back_plan(
        hindi_pack(),
        composed({HINDI_QUOTE: RENDERED}),
        found_by="ANSWER",
        answer_id=ANSWER_ID,
        names=AJRAKH_NAMES,
    )
    (claim,) = plan.claims
    assert (claim.text, claim.label, claim.level_reason) == (STATED, "QUOTED", QUOTED_REASON)
    (citation,) = claim.citations
    assert (citation.quote, citation.relation) == (Quote(text=HINDI_QUOTE), "DIRECT")


def test_without_its_rendering_the_hindi_quote_backs_only_an_inferred_fact() -> None:
    plan = write_back_plan(
        hindi_pack(), composed({}), found_by="ANSWER", answer_id=ANSWER_ID, names=AJRAKH_NAMES
    )
    (claim,) = plan.claims
    (citation,) = claim.citations
    assert (claim.label, citation.quote, citation.relation) == (
        "INFERRED",
        Quote(text=HINDI_QUOTE),
        "CONTEXTUAL",
    )
