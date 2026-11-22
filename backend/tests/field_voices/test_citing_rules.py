import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from app.api.public_deps import reading_acls
from app.composer.candidates import compose_request
from app.research.composition import ComposedAnswer, ComposedSection, ComposedSentence, QuotedSpan
from app.research.evidence import EvidenceItem, SourceDocument
from app.research.media_refs import MediaRef
from app.research.planning import FacetCoverage
from app.research.retrieval import ChunkHit, KnowledgeHits, chunk_acls_for
from app.services.research_write_back import writes_back
from app.services.write_back_plan import write_back_plan
from tests.composer.fixtures import ABSTRACT_ITEM, LONG_ITEM, PLAN, STORED, pack, packed
from tests.write_back.names import AJRAKH_NAMES

QUOTE = "We grind the alum with tamarind seed, and the paste must rest overnight."
FIELD_CHUNK = uuid.UUID(int=41)
FIELD_SOURCE = uuid.UUID(int=42)
FIELD_ID = f"field_voices:{FIELD_CHUNK}"
READING_URL = "https://kalavigyan.example.org/voices/9b3b6f0e-0000-4000-8000-000000000001"


class Reader:
    def __init__(self, role: str) -> None:
        self.id = uuid.uuid4()
        self.role = role


def test_every_reader_quotes_field_transcripts_and_only_researchers_quote_closed_text() -> None:
    assert chunk_acls_for(None) == ("PUBLIC", "SIGNED_IN")
    assert chunk_acls_for("STUDENT") == ("PUBLIC", "SIGNED_IN")
    assert chunk_acls_for(Reader("STUDENT")) == ("PUBLIC", "SIGNED_IN")
    assert chunk_acls_for(Reader("ARTISAN")) == ("PUBLIC", "SIGNED_IN")
    assert set(chunk_acls_for(Reader("RESEARCHER"))) == {"PUBLIC", "RESEARCHER", "SIGNED_IN"}
    assert set(chunk_acls_for("RESEARCHER")) == {"PUBLIC", "RESEARCHER", "SIGNED_IN"}
    assert reading_acls(None) == ("PUBLIC", "SIGNED_IN")


def field_hit() -> ChunkHit:
    return ChunkHit(
        chunk_id=FIELD_CHUNK,
        source_id=FIELD_SOURCE,
        ordinal=0,
        locator="0:06–0:33",
        text=QUOTE,
        score=0.04,
        source_kind="FIELD_TESTIMONY",
        source_title="Field interview, Ajrakh documentation visit, 14 March 2026",
    )


def field_pack(facet: str = "PROCESS_STAGE") -> Any:
    plan = PLAN.model_copy(update={"facets": [PLAN.facets[0].model_copy(update={"type": facet})]})
    stored = KnowledgeHits(craft_slug=STORED.craft_slug, claims=(), chunks=(*STORED.chunks, field_hit()))
    return pack(plan=plan, stored=stored, evidence=(), documents=())


def field_document() -> SourceDocument:
    item = EvidenceItem(
        id=FIELD_ID,
        adapter="field_voices",
        tier="T3",
        source_type="FIELD_TESTIMONY",
        url=READING_URL,
        title="Field interview, Ajrakh documentation visit, 14 March 2026",
        authors=["Asha Demo"],
        published="2026",
        retrieved_at=datetime(2026, 11, 18, tzinfo=UTC),
        trust="A",
    )
    digest = hashlib.sha256(QUOTE.encode("utf-8")).hexdigest()
    return SourceDocument(item=item, text=QUOTE, text_sha256=digest, truncated=False, content="EXCERPT")


def said(text: str) -> ComposedAnswer:
    sentence = ComposedSentence(
        text=text, claim_ids=[], evidence_ids=[FIELD_ID], spans=[QuotedSpan(ref=FIELD_ID, text=QUOTE)]
    )
    return ComposedAnswer(sections=[ComposedSection(heading="Mordant", sentences=[sentence])])


def test_a_field_interview_passage_is_offered_to_the_composer_labelled_as_one() -> None:
    request = compose_request(field_pack(), "How is the mordant prepared?")
    field = [candidate for candidate in request.candidates if candidate.id == FIELD_ID]
    assert len(field) == 1
    assert field[0].source_label.startswith("field interview: Field interview, Ajrakh documentation visit")
    assert field[0].text == QUOTE
    assert not [candidate for candidate in request.candidates if candidate.text == "stored passage"]
    assert writes_back(field_pack())


def test_a_field_interview_alone_may_support_the_speakers_own_process() -> None:
    plan = write_back_plan(
        field_pack(),
        said("The alum paste rests overnight before printing."),
        found_by="ANSWER",
        answer_id=uuid.uuid4(),
        field_documents={FIELD_ID: field_document()},
        names=AJRAKH_NAMES,
    )
    assert len(plan.claims) == 1
    citation = plan.claims[0].citations[0]
    assert (citation.evidence.url, citation.quote_check) == (READING_URL, "PASS")


def test_a_field_interview_alone_never_supports_a_chemistry_claim() -> None:
    plan = write_back_plan(
        field_pack("MECHANISM"),
        said("Alum binds the dye by forming a lake."),
        found_by="ANSWER",
        answer_id=uuid.uuid4(),
        field_documents={FIELD_ID: field_document()},
        names=AJRAKH_NAMES,
    )
    assert plan.claims == ()
    assert plan.skipped[0].reason == "a field interview alone supports only the speaker's own practice"


def planned_pack(*kinds: str, evidence: tuple[Any, ...] = ()) -> Any:
    facets = [PLAN.facets[0].model_copy(update={"type": kind}) for kind in kinds]
    stored = KnowledgeHits(craft_slug=STORED.craft_slug, claims=(), chunks=(*STORED.chunks, field_hit()))
    coverage = tuple(FacetCoverage(facet_index=index) for index in range(len(kinds)))
    documents = tuple(
        document for document in pack().documents if document.item in [e.item for e in evidence]
    )
    return pack(
        plan=PLAN.model_copy(update={"facets": facets}),
        stored=stored,
        coverage=coverage,
        evidence=evidence,
        documents=documents,
    )


def said_with(text: str, other: str) -> ComposedAnswer:
    sentence = ComposedSentence(
        text=text,
        claim_ids=[],
        evidence_ids=[FIELD_ID, other],
        spans=[QuotedSpan(ref=FIELD_ID, text=QUOTE)],
    )
    return ComposedAnswer(sections=[ComposedSection(heading="Mordant", sentences=[sentence])])


def written(evidence_pack: Any, answer: ComposedAnswer) -> Any:
    return write_back_plan(
        evidence_pack,
        answer,
        found_by="ANSWER",
        answer_id=uuid.uuid4(),
        field_documents={FIELD_ID: field_document()},
        names=AJRAKH_NAMES,
    )


def test_a_field_interview_alone_is_not_written_back_when_the_section_plans_chemistry_too() -> None:
    plan = written(planned_pack("PROCESS_STAGE", "MECHANISM"), said("Alum binds the dye by forming a lake."))
    assert plan.claims == ()
    assert plan.skipped[0].reason == "a field interview alone supports only the speaker's own practice"


def test_a_field_interview_alone_is_filed_under_the_practice_its_section_plans() -> None:
    plan = written(planned_pack("MATERIAL", "PROCESS_STAGE"), said("The alum paste rests overnight."))
    assert [claim.subject.concept_type for claim in plan.claims] == ["MATERIAL"]


def test_a_field_interview_beside_a_c_source_never_supports_a_chemistry_claim() -> None:
    evidence = (packed(LONG_ITEM, "web"),)
    plan = written(
        planned_pack("MECHANISM", evidence=evidence), said_with("Alum forms a lake.", LONG_ITEM.id)
    )
    assert plan.claims == ()
    assert (
        plan.skipped[0].reason == "a field interview supports another discipline only beside an A or B source"
    )


def test_a_field_interview_beside_a_b_source_may_support_a_chemistry_claim_filed_under_that_source() -> None:
    evidence = (packed(ABSTRACT_ITEM, "crossref"),)
    plan = written(
        planned_pack("MECHANISM", "PROCESS_STAGE", evidence=evidence),
        said_with("Alum forms a red lake with alizarin.", ABSTRACT_ITEM.id),
    )
    assert len(plan.claims) == 1
    assert plan.claims[0].subject.concept_type == "MECHANISM"
    assert {citation.evidence.id for citation in plan.claims[0].citations} == {FIELD_ID, ABSTRACT_ITEM.id}


def media(**changes: Any) -> dict[str, Any]:
    url = "https://api.kalavigyan.example.org/api/field-voices/images/9b3b6f0e-0000-4000-8000-000000000002"
    fields: dict[str, Any] = {
        "id": uuid.uuid4(),
        "display": "INLINE",
        "provider": "field_repository",
        "pageUrl": url,
        "imageUrl": url,
        "width": 2400,
        "height": 1600,
        "title": "Printing the first resist",
        "alt": "Photograph of Ajrakh Print of Kutch: Printing the first resist",
        "author": "Asha Demo",
        "site": "Field Repository",
        "credit": "Asha Demo · Ajrakh documentation visit, 14 March 2026 · Field Repository",
        "licence": None,
        "licenceUrl": None,
        "sourceId": None,
        "retrievedAt": "2026-11-18T02:00:00Z",
    }
    return fields | changes


def test_a_credited_field_photograph_is_shown_inline_without_an_open_licence() -> None:
    assert MediaRef.model_validate(media()).licence is None
    with pytest.raises(ValidationError, match="credit"):
        MediaRef.model_validate(media(credit=None))
    with pytest.raises(ValidationError, match="open licence"):
        MediaRef.model_validate(media(provider="openverse"))
