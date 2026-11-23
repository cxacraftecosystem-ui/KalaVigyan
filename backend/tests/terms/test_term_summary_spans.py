import json
from datetime import UTC, datetime

from app.composer.term_summary import TermBrief, summarise_term
from app.research.evidence import EvidenceItem, SourceDocument
from app.sources.adapter import build_document

from ..planner.fakes import FakeModel

MORDANT = "Alum is the mordant that fixes madder red on cotton."
CITY = "Bhuj is the largest town of Kachchh district."
BRIEF = TermBrief(label="Alum", meaning="a mordant salt", crafts=("Kutch Ajrakh",))


def page(name: str, text: str) -> SourceDocument:
    url = f"https://crafts.example.org/{name}"
    item = EvidenceItem(
        id=f"searxng:{url}",
        adapter="searxng",
        tier="T4",
        source_type="WEB_PAGE",
        url=url,
        title=name.title(),
        retrieved_at=datetime(2026, 11, 23, 10, 0, tzinfo=UTC),
        trust="C",
    )
    return build_document(item, text, "FULL_TEXT")


def reply(*quotes: tuple[SourceDocument, str]) -> FakeModel:
    cited = [{"source": document.item.id, "quote": quote} for document, quote in quotes]
    return FakeModel([json.dumps({"sentences": [{"text": MORDANT, "quotes": cited}]})])


async def test_a_sentence_keeps_the_source_that_backs_it_when_another_it_cites_does_not() -> None:
    mordant, city = page("mordants", MORDANT), page("bhuj", CITY)
    (kept,) = await summarise_term(reply((mordant, MORDANT), (city, CITY)), BRIEF, [mordant, city])
    assert (kept.text, [span.ref for span in kept.spans]) == (MORDANT, [mordant.item.id])
    assert kept.evidence_ids == [mordant.item.id]


async def test_a_sentence_no_source_backs_is_still_dropped() -> None:
    city, town = page("bhuj", CITY), page("town", CITY)
    assert await summarise_term(reply((city, CITY), (town, CITY)), BRIEF, [city, town]) == []
