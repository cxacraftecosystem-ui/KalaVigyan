from app.services.answer_events import cited_claims

from .fakes import ALUM_CLAIM_ID, SOURCES, VIEWS, FakeEnrichment, FakeStore, enriched, pipeline, streamed
from .test_answer_flow import detailed, events
from .test_section_enrichment import block_events, spans_of


def stored_only_store() -> FakeStore:
    return FakeStore(stored=cited_claims([VIEWS[0], VIEWS[3]], SOURCES))


async def test_a_spent_budget_answer_marks_its_terms_and_shows_a_picture_of_its_claim() -> None:
    enrichment = enriched()
    found = events(
        await streamed(detailed(), pipeline(store=stored_only_store(), spent=True, enrichment=enrichment))
    )
    names = [(name, payload.get("block", {}).get("kind")) for name, payload in found]
    assert (
        names.index(("block", "prose"))
        < names.index(("block", "images"))
        < names.index(("section_done", None))
    )
    prose, images = block_events(found)
    assert spans_of(prose) == [[("Alum", "alum"), ("alizarin", "alizarin"), ("cotton", "cotton")]]
    assert (images["id"], [item["media"]["title"] for item in images["items"]]) == (
        "s1.b2",
        ["Alum mordant bath for alizarin dyeing"],
    )
    assert [item["claimIds"] for item in images["items"]] == [[str(ALUM_CLAIM_ID)]]
    (ask,) = enrichment.asks
    assert (ask.block_id, ask.craft_name, ask.claim_ids) == ("s1.b2", "Kutch Ajrakh", (ALUM_CLAIM_ID,))
    assert enrichment.crafts == ["Kutch-Ajrakh"]


async def test_a_spent_budget_answer_without_a_relevant_picture_streams_its_prose_alone() -> None:
    found = events(
        await streamed(
            detailed(), pipeline(store=stored_only_store(), spent=True, enrichment=FakeEnrichment())
        )
    )
    assert [payload["kind"] for payload in block_events(found)] == ["prose"]
