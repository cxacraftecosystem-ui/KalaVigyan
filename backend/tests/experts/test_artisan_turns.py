import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from app.composer.candidates import field_evidence_id
from app.models import FieldRecording, FieldSegment
from app.research.evidence import EvidenceItem
from app.research.field_voices import FIELD_VOICES_ADAPTER
from app.research.retrieval import ChunkHit
from app.services.artisan_seat import HeardQuote, attributed
from app.services.artisan_turns import TurnCite, UnquotedTurn, backing_rank, spoken_quote, unquoted_turns
from app.services.artisan_write_back import TurnFiling, turn_claim, writes_turns_back
from app.services.write_back_stored import passage_document
from tests.field_voices.fixtures import FR, recorded

SOURCE = uuid.UUID("5f000000-0000-4000-8000-000000000001")
OTHER_SOURCE = uuid.UUID("5f000000-0000-4000-8000-000000000002")
RECORDING = uuid.UUID("5f000000-0000-4000-8000-000000000003")
ANSWER = uuid.UUID("5f000000-0000-4000-8000-000000000004")
GRIND = "We grind the alum with tamarind seed, and the paste must rest overnight."
QUESTION = "How do you prepare the mordant for the red?"
WASH = "We wash the printed cloth in the river twice before the indigo."
PEOPLE: list[dict[str, Any]] = recorded("field-transcripts-all-1")["changes"][0]["people"]
FILING = TurnFiling("Kutch-Ajrakh", "Kutch Ajrakh", "PROCESS", ANSWER)


def recording() -> FieldRecording:
    return FieldRecording(
        id=RECORDING,
        portal=FR,
        portalMediaId="fr-media-1",
        sourceId=SOURCE,
        people=PEOPLE,
        context={"crafts": [{"name": "Ajrakh Print of Kutch"}]},
        recordedAt=datetime(2026, 3, 12, 10, 0, tzinfo=UTC),
    )


def turn(number: int, text: str, person: str, *, quotable: bool = True) -> FieldSegment:
    return FieldSegment(
        id=uuid.UUID(f"5e000000-0000-4000-8000-{number:012d}"),
        recordingId=RECORDING,
        portalSegmentId=f"fr-turn-{number}",
        position=number,
        personId=person,
        startMs=number * 1000,
        endMs=number * 1000 + 900,
        language="en",
        text=text,
        english=None,
        englishSource=None,
        quotable=quotable,
    )


ASKED = turn(1, QUESTION, "fr-user-1")
GROUND = turn(2, GRIND, "fr-art-1")
WASHED = turn(3, WASH, "fr-art-1")
UNQUOTABLE = turn(
    4, "We print the outline first, then the resist goes on top of it.", "fr-art-1", quotable=False
)
ROWS = [(segment, recording()) for segment in (ASKED, GROUND, WASHED, UNQUOTABLE)]


def hit(number: int, text: str, source: uuid.UUID = SOURCE) -> ChunkHit:
    return ChunkHit(
        chunk_id=uuid.UUID(f"5d000000-0000-4000-8000-{number:012d}"),
        source_id=source,
        ordinal=number,
        locator=f"0:0{number}–0:0{number}",
        text=text,
        score=1.0 / number,
        source_kind="FIELD_TESTIMONY",
    )


def test_a_short_turn_is_quoted_whole() -> None:
    assert spoken_quote(GRIND) == GRIND


def test_a_long_turn_is_quoted_to_the_last_whole_sentence_within_300_characters() -> None:
    first = " ".join(["alum"] * 40) + "."
    second = " ".join(["paste"] * 30) + "."
    assert len(first) == 200 and len(f"{first} {second}") == 381
    assert spoken_quote(f"{first} {second}") == first


def test_one_long_sentence_is_quoted_to_the_last_whole_word_within_300_characters() -> None:
    quote = spoken_quote(" ".join(["indigo"] * 70))
    assert quote == " ".join(["indigo"] * 43)
    assert quote is not None and len(quote) == 300


@pytest.mark.parametrize("text", ["Yes, we do.", "x" * 301])
def test_a_trivial_or_unbroken_turn_gives_no_quote(text: str) -> None:
    assert spoken_quote(text) is None


def test_an_uncited_quotable_artisan_turn_is_written_back_from_its_chunk() -> None:
    (found,) = unquoted_turns([hit(1, GRIND)], [], ROWS, limit=3)
    assert (found.turn.segment, found.quote, found.hit.chunk_id) == (GROUND, GRIND, hit(1, GRIND).chunk_id)
    assert found.turn.voice.speaker.name == "Asha Demo"


def test_a_researcher_s_turn_an_unquotable_turn_and_another_source_are_not_written_back() -> None:
    hits = [
        hit(1, QUESTION),
        hit(2, "We print the outline first, then the resist goes on top of it."),
        hit(3, GRIND, OTHER_SOURCE),
    ]
    assert unquoted_turns(hits, [], ROWS, limit=3) == []


def test_a_turn_a_citation_links_or_already_quotes_is_not_written_back_twice() -> None:
    linked = TurnCite(uuid.uuid4(), SOURCE, hit(1, GRIND).chunk_id, "the paste must rest overnight")
    quoted_elsewhere = TurnCite(uuid.uuid4(), SOURCE, None, "We wash the printed cloth in the river")
    hits = [hit(1, GRIND), hit(2, WASH)]
    assert unquoted_turns(hits, [linked, quoted_elsewhere], ROWS, limit=3) == []


def test_two_chunks_of_one_turn_write_it_back_once_and_the_limit_holds() -> None:
    hits = [hit(1, GRIND), hit(2, "We grind the alum with tamarind seed"), hit(3, WASH)]
    assert [one.turn.segment for one in unquoted_turns(hits, [], ROWS, limit=3)] == [GROUND, WASHED]
    assert [one.turn.segment for one in unquoted_turns(hits, [], ROWS, limit=1)] == [GROUND]
    assert unquoted_turns(hits, [], ROWS, limit=0) == []


def test_a_citation_backs_the_first_chunk_it_links_or_lies_within() -> None:
    hits = [hit(1, WASH), hit(2, GRIND)]
    by_link = TurnCite(uuid.uuid4(), SOURCE, hits[1].chunk_id, "a quote of another chunk")
    by_text = TurnCite(uuid.uuid4(), SOURCE, None, "the paste must rest overnight")
    elsewhere = TurnCite(uuid.uuid4(), OTHER_SOURCE, None, "the paste must rest overnight")
    assert [backing_rank(cite, hits) for cite in (by_link, by_text, elsewhere)] == [1, 1, None]


def document_for(found: ChunkHit) -> Any:
    item = EvidenceItem(
        id=field_evidence_id(found),
        adapter=FIELD_VOICES_ADAPTER,
        tier="T3",
        source_type="FIELD_TESTIMONY",
        url="https://kalavigyan.example.org/voices/1",
        title="Interview at an Ajrakh workshop",
        retrieved_at=datetime(2026, 11, 18, 3, 0, tzinfo=UTC),
        trust="A",
    )
    return passage_document(item, found)


def test_a_written_back_turn_is_a_quoted_process_fact_of_the_craft_naming_nobody() -> None:
    (found,) = unquoted_turns([hit(1, GRIND)], [], ROWS, limit=3)
    claim = turn_claim(found, document_for(found.hit), FILING)
    assert claim.text == f"An artisan who practises Kutch Ajrakh says: “{GRIND}”"
    assert "Asha" not in claim.text
    assert (claim.craft_slug, claim.field, claim.label, claim.evidence_level) == (
        "Kutch-Ajrakh",
        "PROCESS",
        "QUOTED",
        "PROVISIONAL",
    )
    assert (claim.subject.concept_type, claim.subject.concept_name) == ("ARTISAN_ACTION", "Kutch Ajrakh")
    assert (claim.found_by, claim.answer_id) == ("ANSWER", ANSWER)
    (citation,) = claim.citations
    assert (citation.quote.text if citation.quote else None, citation.quote_check, citation.relation) == (
        GRIND,
        "PASS",
        "DIRECT",
    )


def test_a_quote_carrying_a_phone_number_is_refused_as_a_fact() -> None:
    spoken = "Call me on 98765 43210 and I will tell you how the alum paste is made."
    (found,) = unquoted_turns([hit(1, GRIND)], [], ROWS, limit=3)
    phoned = UnquotedTurn(found.turn, hit(5, spoken), spoken)
    with pytest.raises(ValidationError):
        turn_claim(phoned, document_for(phoned.hit), FILING)


@pytest.mark.parametrize(
    ("field", "written"),
    [("PROCESS", True), ("MATERIALS", True), ("DESIGN", True), ("HISTORY", False), ("OVERVIEW", False)],
)
def test_a_field_interview_alone_is_written_back_only_for_the_speaker_s_own_practice(
    field: str, written: bool
) -> None:
    assert writes_turns_back(field) is written


def test_an_unnamed_artisan_is_attributed_without_a_name() -> None:
    heard = HeardQuote(uuid.uuid4(), GRIND, None, "Ajrakh Print of Kutch", "Kachchh")
    assert attributed(heard) == (
        f"In one account from an artisan who practises Ajrakh Print of Kutch in Kachchh district: “{GRIND}”"
    )
