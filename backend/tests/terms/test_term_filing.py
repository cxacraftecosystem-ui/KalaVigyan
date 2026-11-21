import uuid

from app.research.composition import ComposedSentence, QuotedSpan
from app.research.evidence import EvidenceItem
from app.services.term_research import GlossaryTerm, TermConceptRef
from app.services.term_store import TERM_FACET, claim_for_sentence, write_back_subject
from app.sources.adapter import build_document

from ..sources.recorded import RETRIEVED

ALUM_IN_BAGH = uuid.UUID("5a1d2c3e-0000-4000-8000-0000000a1b00")
PAGE = "https://crafts.example.org/alum"
TEXT = "Alum is a double sulphate of aluminium. It is used as a mordant by many dyers."


def alum(*crafts: str, concepts: tuple[TermConceptRef, ...] = ()) -> GlossaryTerm:
    return GlossaryTerm(
        id=uuid.uuid4(),
        key="alum",
        label="Alum",
        meaning="potash alum",
        craft_slugs=crafts,
        concepts=concepts,
    )


def test_a_term_of_one_craft_is_filed_under_that_craft() -> None:
    assert write_back_subject(alum("Kutch-Ajrakh"))[0] == "Kutch-Ajrakh"


def test_a_term_of_several_crafts_is_filed_under_the_one_owning_its_concept() -> None:
    owned = TermConceptRef(ALUM_IN_BAGH, "Bagh-Prints-of-Madhya-Pradesh", "MATERIAL", "Alum", None)
    craft, subject = write_back_subject(
        alum("Bagh-Prints-of-Madhya-Pradesh", "Kutch-Ajrakh", concepts=(owned,))
    )
    assert (craft, subject.concept_id, subject.concept_type) == (
        "Bagh-Prints-of-Madhya-Pradesh",
        ALUM_IN_BAGH,
        "MATERIAL",
    )


def test_a_term_shared_by_several_crafts_is_filed_as_shared_knowledge_never_the_first_craft() -> None:
    craft, subject = write_back_subject(alum("Bagh-Prints-of-Madhya-Pradesh", "Kutch-Ajrakh"))
    assert (craft, subject.concept_type, subject.concept_name) == (None, TERM_FACET, "Alum")


def test_a_term_quote_is_direct_only_when_it_carries_the_sentence() -> None:
    item = EvidenceItem(
        id=f"searxng:{PAGE}",
        adapter="searxng",
        tier="T4",
        source_type="WEB_PAGE",
        url=PAGE,
        title="Alum",
        retrieved_at=RETRIEVED,
        trust="C",
    )
    sentence = ComposedSentence(
        text="Alum is a double sulphate used as a mordant.",
        evidence_ids=[item.id],
        spans=[
            QuotedSpan(ref=item.id, text="Alum is a double sulphate of aluminium"),
            QuotedSpan(ref=item.id, text="It is used as a mordant by many dyers"),
        ],
    )
    documents = {item.id: build_document(item, TEXT, "FULL_TEXT")}
    _, subject = write_back_subject(alum("Kutch-Ajrakh"))
    claim = claim_for_sentence(sentence, documents, "Kutch-Ajrakh", subject)
    assert [citation.relation for citation in claim.citations] == ["DIRECT", "CONTEXTUAL"]
