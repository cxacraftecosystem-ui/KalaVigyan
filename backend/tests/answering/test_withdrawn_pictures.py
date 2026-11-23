import dataclasses
import uuid
from typing import Any

from app.research.blocks import ImagesBlock
from app.research.blocks_matter import MaterialCardBlock
from app.research.explainer import Understood
from app.research.sections import SectionSpec
from app.services.answer_events import cited_claims
from app.services.block_builders import BlockBuilders, BuilderEntry
from app.services.builder_interface import BuildAsk, Built
from app.services.explainer_document import explainer_document
from app.services.section_context import SectionOutcome

from ..ledger.indigo_blocks import VAT_PHOTO, ZAVERI
from .fakes import (
    ALUM_CLAIM_ID,
    BOOK,
    SOURCES,
    VIEWS,
    FakeEnrichment,
    FakeStore,
    pipeline,
    stored_view,
    streamed,
)
from .piece_fakes import MemoryPieces
from .test_answer_flow import REPLY, detailed, events
from .test_section_enrichment import prose

INDIGO_CLAIM_ID = uuid.UUID("5e6f7a8b-9c0d-4e1f-8a2b-3c4d5e6f7a8b")
INDIGO_COMPOUND_ID = "6f7a8b9c-0d1e-4f2a-9b3c-4d5e6f7a8b9c"
PUBCHEM_ID = "1a2b3c4d-0000-4000-8000-000000000009"
INDIGO = stored_view(
    INDIGO_CLAIM_ID,
    "Indigo is reduced to soluble leucoindigo in the vat.",
    "REVIEWED",
    (5, BOOK, "Indigo is reduced to soluble leucoindigo", "p. 44"),
)
PUBCHEM_RECORD = {
    "id": PUBCHEM_ID,
    "kind": "COMPOUND_RECORD",
    "title": "Indigo (PubChem CID 10215)",
    "authors": [],
    "year": None,
    "doi": None,
    "url": "https://pubchem.ncbi.nlm.nih.gov/compound/10215",
    "publisher": "PubChem",
    "licence": None,
    "attribution": None,
    "reliability": "A",
}


def indigo_card() -> MaterialCardBlock:
    fact = {
        "id": "s1.card.1",
        "text": INDIGO.text,
        "level": "REVIEWED",
        "citations": INDIGO.citations,
        "terms": [],
    }
    return MaterialCardBlock.model_validate(
        {
            "id": "s1.card",
            "kind": "material_card",
            "version": 1,
            "reuse": None,
            "materialId": None,
            "compoundId": INDIGO_COMPOUND_ID,
            "termKey": None,
            "name": "Indigo",
            "materialKind": None,
            "role": None,
            "formula": "C16H10N2O2",
            "pubchemCid": 10215,
            "wikidataId": None,
            "localNames": [],
            "facts": [fact],
            "handling": [],
            "sourceId": PUBCHEM_ID,
        }
    )


def pictures(block_id: str, *shown: tuple[dict[str, Any], tuple[uuid.UUID, ...]]) -> ImagesBlock:
    items = [
        {"media": media, "claimIds": [str(claim) for claim in claims], "relevance": "TEXT"}
        for media, claims in shown
    ]
    return ImagesBlock.model_validate(
        {"id": block_id, "kind": "images", "version": 1, "reuse": None, "items": items}
    )


@dataclasses.dataclass
class Builds:
    blocks: tuple[Any, ...]
    sources: dict[str, Any] = dataclasses.field(default_factory=dict)
    asks: list[BuildAsk] = dataclasses.field(default_factory=list)

    async def build(self, ask: BuildAsk) -> Built:
        self.asks.append(ask)
        return Built(self.blocks, self.sources)


def with_builder(answer: Any, kind: str, builder: Builds, *, adds_pictures: bool = False) -> Any:
    entry = BuilderEntry(
        kind, frozenset({"CHEMISTRY"}), lambda tools: builder, 1.0, adds_pictures=adds_pictures
    )
    return dataclasses.replace(answer, builders=BlockBuilders([(entry, builder)]))


def shown_kinds(found: list[tuple[str, dict]]) -> list[str]:
    return [payload["block"]["kind"] for name, payload in found if name == "block"]


async def test_a_reused_card_left_out_for_its_record_source_lends_no_claim_to_a_picture_chosen_from_it() -> (
    None
):
    pieces = MemoryPieces(views=[*VIEWS, INDIGO], sources=dict(SOURCES))
    cards = Builds((indigo_card(),), {PUBCHEM_ID: PUBCHEM_RECORD})
    first = events(
        await streamed(
            detailed(), with_builder(pipeline(replies=[REPLY], pieces=pieces), "material_card", cards)
        )
    )
    assert shown_kinds(first) == ["prose", "material_card"]
    concept = Builds((pictures("s1.concept", (VAT_PHOTO, (INDIGO_CLAIM_ID,))),))
    store = FakeStore()
    answer = with_builder(
        pipeline(store=store, pieces=pieces, enrichment=FakeEnrichment()),
        "simulation",
        concept,
        adds_pictures=True,
    )
    found = events(await streamed(detailed(), answer))
    (asked,) = concept.asks
    assert sorted(block.kind for block in asked.blocks) == ["material_card", "prose"]
    assert "error" not in dict(found)
    assert shown_kinds(found) == ["prose"]
    (finished,) = store.finished
    assert [block.kind for block in finished["explainer"].sections[0].blocks] == ["prose"]


def assembled(shown: ImagesBlock) -> Any:
    alum = prose("Alum is the mordant that binds alizarin to cotton in Ajrakh.")
    spec = SectionSpec(id="s1", discipline="CHEMISTRY", title="The chemistry", order=1)
    outcome = SectionOutcome(spec, blocks=(alum, shown), sources=cited_claims([VIEWS[0]], SOURCES).sources)
    return explainer_document(
        answer_id=uuid.uuid4(),
        question="Why is alum used in Kutch Ajrakh?",
        understood=Understood(crafts=[], candidates=[], depth="DETAILED", language="en"),
        outcomes=[outcome],
        titles={},
        follow_ups=[],
    )


def test_assembly_keeps_a_section_s_pictures_only_for_the_claims_its_blocks_cite() -> None:
    document = assembled(
        pictures("s1.b2", (VAT_PHOTO, (INDIGO_CLAIM_ID,)), (ZAVERI, (INDIGO_CLAIM_ID, ALUM_CLAIM_ID)))
    )
    assert document is not None
    (section,) = document.sections
    assert (section.state, [block.kind for block in section.blocks]) == ("READY", ["prose", "images"])
    picture = section.blocks[1]
    assert isinstance(picture, ImagesBlock)
    assert [(item.media.id, item.claim_ids) for item in picture.items] == [
        (uuid.UUID(ZAVERI["id"]), [ALUM_CLAIM_ID])
    ]


def test_a_section_whose_only_picture_illustrates_nothing_it_cites_is_assembled_without_it() -> None:
    document = assembled(pictures("s1.b2", (VAT_PHOTO, (INDIGO_CLAIM_ID,))))
    assert document is not None
    assert [block.kind for block in document.sections[0].blocks] == ["prose"]
