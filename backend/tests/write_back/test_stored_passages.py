import hashlib
import uuid
from typing import Any

import pytest
from pydantic import ValidationError

from app.composer.candidates import compose_request
from app.models import Source
from app.research.composition import ComposedAnswer, ComposedSection, ComposedSentence, QuotedSpan
from app.research.evidence import Quote
from app.research.evidence_pack import EvidencePack
from app.research.planning import Facet, FacetCoverage
from app.research.retrieval import ChunkHit
from app.research.sections import DISCIPLINE_TITLES
from app.research.write_back import FOUND_BY, ClaimWriteBack
from app.services.research_write_back import WRITERS, writes_back
from app.services.write_back_plan import SKIP_UNKEPT, WriteBackPlan, write_back_plan
from app.services.write_back_stored import stored_document

from ..composer.fixtures import ALUM_CLAIM_ID, GUESS_CLAIM_ID, PLAN, QUESTION, STORED, pack
from ..research.fixtures import RETRIEVED, evidence_item
from .names import AJRAKH_NAMES, BAGH

ANSWER_ID = uuid.UUID("5e6f7a8b-9c0d-4e1f-8a2b-3c4d5e6f7a8b")
BOOK_ID = uuid.UUID(int=52)
CHUNK_ID = uuid.UUID(int=51)
STORED_ID = f"stored_passages:{CHUNK_ID}"
BOOK_URL = "https://books.example.org/block-printing-of-kutch"
PASSAGE = (
    "Ajrakh printers boil the mordanted cloth with alum so the madder takes a fast red. "
    "The cloth is then washed in running water."
)
QUOTE = "boil the mordanted cloth with alum so the madder takes a fast red"
SENTENCE = "Ajrakh printers boil the mordanted cloth with alum so the madder takes a fast red."
BAGH_PASSAGE = (
    "Bagh Print workshops boil the cloth with alum and dhawda flowers for a bright red.\n\n"
    "The river water is said to help the colour."
)
BAGH_QUOTE = "boil the cloth with alum and dhawda flowers for a bright red"


def book(**changes: Any) -> Source:
    fields: dict[str, Any] = {
        "id": BOOK_ID,
        "kind": "BOOK",
        "title": "Block printing of Kutch",
        "authors": ["S. Writer"],
        "year": 2015,
        "doi": None,
        "url": BOOK_URL,
        "publisher": "Crafts Press",
        "licence": "CC BY 4.0",
        "attribution": None,
        "reliability": "B",
        "retrievedAt": RETRIEVED,
    }
    return Source(**(fields | changes))


def passage(text: str = PASSAGE, *, locator: str | None = "p. 41") -> ChunkHit:
    return ChunkHit(
        chunk_id=CHUNK_ID,
        source_id=BOOK_ID,
        ordinal=2,
        locator=locator,
        text=text,
        score=0.03,
        source_kind="BOOK",
        source_title="Block printing of Kutch",
    )


def passage_pack(hit: ChunkHit, *, facets: tuple[tuple[str, str], ...] = ()) -> EvidencePack:
    plan = PLAN
    if facets:
        chosen = [Facet(type=kind, target=target) for kind, target in facets]
        plan = PLAN.model_copy(update={"facets": chosen})
    coverage = tuple(FacetCoverage(facet_index=index) for index in range(len(plan.facets)))
    stored = STORED.model_copy(update={"chunks": (*STORED.chunks, hit)})
    return pack(plan=plan, stored=stored, coverage=coverage, evidence=(), documents=())


def said(text: str, quote: str, heading: str = "Mordant") -> ComposedAnswer:
    sentence = ComposedSentence(
        text=text, evidence_ids=[STORED_ID], spans=[QuotedSpan(ref=STORED_ID, text=quote)]
    )
    return ComposedAnswer(sections=[ComposedSection(heading=heading, sentences=[sentence])])


def written(
    evidence_pack: EvidencePack, answer: ComposedAnswer, source: Source | None = None
) -> WriteBackPlan:
    hit = evidence_pack.stored.chunks[-1]
    document = stored_document(hit, source or book())
    return write_back_plan(
        evidence_pack,
        answer,
        found_by="ANSWER",
        answer_id=ANSWER_ID,
        names=AJRAKH_NAMES,
        stored_documents={STORED_ID: document} if document is not None else {},
    )


def expected_key(text: str, craft: str, field: str) -> str:
    return hashlib.sha256(
        "\x1f".join(["claim-write-back/v2", craft, field, text]).encode("utf-8")
    ).hexdigest()


def test_a_stored_passage_is_offered_to_the_composer_as_evidence_in_its_own_words() -> None:
    request = compose_request(passage_pack(passage()), QUESTION)
    assert [(c.id, c.kind) for c in request.candidates] == [
        (str(ALUM_CLAIM_ID), "CLAIM"),
        (str(GUESS_CLAIM_ID), "CLAIM"),
        (STORED_ID, "EVIDENCE"),
    ]
    offered = request.allowed[STORED_ID]
    assert (offered.text, offered.quotes, offered.level) == (PASSAGE, [], "PROVISIONAL")
    assert offered.source_label == "stored passage: Block printing of Kutch, p. 41"
    unplaced = compose_request(passage_pack(passage(locator=None)), QUESTION).allowed[STORED_ID]
    assert unplaced.source_label == "stored passage: Block printing of Kutch, passage 3"


def test_a_passage_too_short_to_quote_is_neither_offered_nor_written_back() -> None:
    assert "stored passage" in [hit.text for hit in STORED.chunks]
    alone = pack(evidence=(), documents=())
    assert [c.kind for c in compose_request(alone, QUESTION).candidates] == ["CLAIM", "CLAIM"]
    assert not writes_back(alone)
    assert writes_back(passage_pack(passage()))


def test_a_sentence_citing_a_stored_passage_is_kept_as_a_claim_of_its_source_with_its_quote() -> None:
    plan = written(passage_pack(passage()), said(SENTENCE, QUOTE))
    assert plan.skipped == ()
    (claim,) = plan.claims
    assert (claim.craft_slug, claim.field, claim.label, claim.evidence_level) == (
        "Kutch-Ajrakh",
        "MATERIALS",
        "QUOTED",
        "PROVISIONAL",
    )
    assert (claim.subject.concept_type, claim.subject.concept_name) == ("MATERIAL", "alum")
    (citation,) = claim.citations
    assert (citation.quote, citation.quote_check, citation.relation) == (Quote(text=QUOTE), "PASS", "DIRECT")
    evidence = citation.evidence
    assert (evidence.id, evidence.url, evidence.title, evidence.source_type) == (
        STORED_ID,
        BOOK_URL,
        "Block printing of Kutch",
        "BOOK",
    )
    assert (evidence.trust, evidence.licence, evidence.published, evidence.retrieved_at) == (
        "B",
        "CC BY 4.0",
        "2015",
        RETRIEVED,
    )
    assert evidence.quotes == [Quote(text=QUOTE)]
    folded = "ajrakh printers boil the mordanted cloth with alum so the madder takes a fast red"
    assert claim.dedupe_key == expected_key(folded, "Kutch-Ajrakh", "MATERIALS")
    assert plan.sentence_keys == (claim.dedupe_key,)


def test_a_stored_passage_about_another_craft_files_its_fact_under_that_craft() -> None:
    sentence = "The cloth is boiled with alum and dhawda flowers for a bright red."
    plan = written(passage_pack(passage(BAGH_PASSAGE)), said(sentence, BAGH_QUOTE))
    (claim,) = plan.claims
    assert (claim.craft_slug, claim.category_slug, claim.held_because) == (BAGH.slug, None, None)


def test_a_stored_passage_cited_in_a_section_is_filed_under_the_section_s_facet() -> None:
    facets = (("MATERIAL", "alum"), ("MECHANISM", "alum and madder lake"))
    plan = written(
        passage_pack(passage(), facets=facets), said(SENTENCE, QUOTE, DISCIPLINE_TITLES["CHEMISTRY"])
    )
    (claim,) = plan.claims
    assert (claim.subject.concept_type, claim.subject.concept_name) == ("MECHANISM", "alum and madder lake")
    assert (claim.craft_slug, claim.field) == ("Kutch-Ajrakh", "CHEMISTRY")


def test_a_stored_passage_whose_source_has_no_address_or_reading_date_is_not_cited() -> None:
    assert stored_document(passage(), book(url=None)) is None
    assert stored_document(passage(), book(retrievedAt=None)) is None
    with_doi = stored_document(passage(), book(url=None, doi="10.1000/Kutch.1"))
    assert with_doi is not None
    assert (with_doi.item.url, with_doi.item.source_key) == (
        "https://doi.org/10.1000/Kutch.1",
        "doi:10.1000/kutch.1",
    )
    plan = written(passage_pack(passage()), said(SENTENCE, QUOTE), source=book(url=None))
    assert plan.claims == ()
    assert [skipped.reason for skipped in plan.skipped] == [SKIP_UNKEPT]


def voice_write_back(**changes: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "craftSlug": "Kutch-Ajrakh",
        "subject": {"conceptType": "MATERIAL", "conceptName": "alum"},
        "predicate": "states",
        "text": SENTENCE,
        "label": "INFERRED",
        "levelReason": "test",
        "citations": [
            {"evidence": evidence_item(), "quote": None, "quoteCheck": "NA", "relation": "CONTEXTUAL"}
        ],
        "foundBy": "VOICE",
    }
    return fields | changes


def test_a_voice_write_back_names_no_answer_and_every_finder_names_its_writer() -> None:
    assert ClaimWriteBack.model_validate(voice_write_back()).answer_id is None
    with pytest.raises(ValidationError, match="BACKGROUND or VOICE one does not"):
        ClaimWriteBack.model_validate(voice_write_back(answerId=str(ANSWER_ID)))
    assert set(WRITERS) == set(FOUND_BY) == {"ANSWER", "BACKGROUND", "VOICE"}
