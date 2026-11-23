import dataclasses
import json
import logging
import uuid
from typing import Any

import pytest

from app.models import Source
from app.research.planning import PlanRequest
from app.services.answer_catalogue import NO_CATALOGUE, CatalogueEntry, SectionCatalogue, catalogue_lookup
from app.services.block_builders import BlockBuilders
from app.services.knowledge_view import source_ref
from app.services.piece_store import storable

from ..composer.fixtures import QUESTION, quote, section_reply, sentence
from ..research.fixtures import AJRAKH
from .fakes import BOOK, BOOK_ID, GUESS_CLAIM_ID, FakeStore, pipeline, streamed
from .piece_fakes import MemoryPieces
from .test_answer_flow import REPLY, detailed, events
from .test_block_builders import FakeBuilder, entry

MADDER_ID = uuid.UUID("1a2b3c4d-0000-4000-8000-000000000009")
MADDER = Source(
    id=MADDER_ID,
    kind="PAPER",
    title="Alizarin and purpurin in madder root",
    authors=["B. Author"],
    year=2013,
    doi="10.1000/madder",
    url="https://doi.org/10.1000/madder",
    publisher="Dyes and Pigments",
    licence=None,
    attribution=None,
    reliability="A",
)
PLAYER = CatalogueEntry(
    label="kutch-ajrakh/chemistry/red-alum-madder-player",
    kind="reaction_player",
    title="Red develops only where alum was printed",
    description="A player of the alum and madder red.",
    craft=AJRAKH,
    anchor="#rp-red",
    sources={str(BOOK_ID): source_ref(BOOK)},
)
MOLECULES = CatalogueEntry(
    label="shared/chemistry/alizarin-purpurin-3d",
    kind="molecule_3d",
    title="Madder's red is more than alizarin",
    description="Alizarin and purpurin in three dimensions.",
    craft=AJRAKH,
    anchor='[class="mols mol-two"]',
    sources={str(MADDER_ID): source_ref(MADDER)},
)
PLATE = dataclasses.replace(PLAYER, label="shared/materials/madder-roots-photo", kind="picture_plate")


@dataclasses.dataclass
class FakeCatalogue:
    entries: tuple[CatalogueEntry, ...]
    asked: list[tuple[PlanRequest, str]] = dataclasses.field(default_factory=list)

    async def __call__(self, request: PlanRequest, field: str) -> SectionCatalogue:
        self.asked.append((request, field))
        return SectionCatalogue(self.entries) if field == "CHEMISTRY" else NO_CATALOGUE


def chose(*labels: str, reply: str = REPLY) -> str:
    return json.dumps({**json.loads(reply), "components": list(labels)})


def blocks(found: list[tuple[str, dict[str, Any]]]) -> list[dict[str, Any]]:
    return [payload["block"] for name, payload in found if name == "block"]


async def test_a_chosen_component_is_placed_after_the_prose_with_its_page_and_sources() -> None:
    catalogue = FakeCatalogue((PLAYER, MOLECULES))
    store, pieces = FakeStore(), MemoryPieces()
    reply = chose(MOLECULES.label, "kutch-ajrakh/chemistry/invented", PLAYER.label)
    answer = dataclasses.replace(pipeline(replies=[reply], store=store, pieces=pieces), catalogue=catalogue)
    found = events(await streamed(detailed(), answer))
    shown = blocks(found)
    assert [(block["id"], block["kind"]) for block in shown] == [
        ("s1.b1", "prose"),
        ("s1.b2", "component"),
        ("s1.b3", "component"),
    ]
    assert shown[1] == {
        "id": "s1.b2",
        "kind": "component",
        "version": 1,
        "reuse": None,
        "label": "shared/chemistry/alizarin-purpurin-3d",
        "componentKind": "molecule_3d",
        "title": "Madder's red is more than alizarin",
        "craft": {"slug": "Kutch-Ajrakh", "name": "Kutch Ajrakh", "path": "/crafts/Kutch-Ajrakh"},
        "href": "/crafts/Kutch-Ajrakh",
        "sources": [{"sourceId": str(MADDER_ID)}],
    }
    assert (shown[2]["label"], shown[2]["href"]) == (PLAYER.label, "/crafts/Kutch-Ajrakh#rp-red")
    assert str(MADDER_ID) in [payload["id"] for name, payload in found if name == "source"]
    (finished,) = store.finished
    explainer = finished["explainer"]
    assert [block.kind for block in explainer.sections[0].blocks] == ["prose", "component", "component"]
    assert str(MADDER_ID) in [source.id for source in explainer.sources]
    ((_, _, sections),) = pieces.kept
    assert [[storable(block) for block in section.blocks] for section in sections] == [[True, False, False]]


async def test_the_catalogue_is_asked_for_the_section_craft_field_and_question() -> None:
    catalogue = FakeCatalogue((PLAYER,))
    answer = dataclasses.replace(pipeline(replies=[chose(PLAYER.label)]), catalogue=catalogue)
    await streamed(detailed(), answer)
    ((request, field),) = catalogue.asked
    assert (request.craft, request.question, field) == (AJRAKH, QUESTION, "CHEMISTRY")


async def test_a_section_without_prose_places_no_component() -> None:
    guess = section_reply(
        sentence(
            "Lime in the wash water may brighten the red.",
            quote(GUESS_CLAIM_ID, "Lime in the wash water may brighten the red"),
        )
    )
    store = FakeStore()
    answer = dataclasses.replace(
        pipeline(replies=[chose(PLAYER.label, reply=guess)], store=store), catalogue=FakeCatalogue((PLAYER,))
    )
    found = events(await streamed(detailed(), answer))
    ((_, _, composed),) = store.kept
    assert (composed.sections, composed.component_labels) == ([], [PLAYER.label])
    assert [block["kind"] for block in blocks(found)] == []


async def test_a_placed_component_stands_for_the_builder_of_its_purpose_and_no_other() -> None:
    player, cards = FakeBuilder(blocks=()), FakeBuilder()
    builders = BlockBuilders([(entry(kind="reaction_player"), player), (entry(), cards)])
    answer = dataclasses.replace(
        pipeline(replies=[chose(PLAYER.label)]), catalogue=FakeCatalogue((PLAYER,)), builders=builders
    )
    found = events(await streamed(detailed(), answer))
    assert player.asks == []
    assert len(cards.asks) == 1
    assert [block["kind"] for block in blocks(found)] == ["prose", "component", "material_card"]


@dataclasses.dataclass
class AwaySession:
    opened: list[str] = dataclasses.field(default_factory=list)
    error: Exception = dataclasses.field(
        default_factory=lambda: ConnectionRefusedError("the database is away")
    )

    def __call__(self) -> AwaySession:
        return self

    async def __aenter__(self) -> None:
        self.opened.append("session")
        raise self.error

    async def __aexit__(self, *exc_info: object) -> bool:
        return False


async def test_a_failing_catalogue_offers_nothing_and_a_question_without_a_craft_asks_nothing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    sessions = AwaySession()
    lookup = catalogue_lookup(sessions)
    asked = PlanRequest(question=QUESTION, mode="HYBRID", craft=AJRAKH)
    with caplog.at_level(logging.WARNING, logger="app.services.answer_catalogue"):
        assert await lookup(asked, "CHEMISTRY") is NO_CATALOGUE
    assert "the component catalogue of Kutch-Ajrakh for CHEMISTRY failed" in caplog.text
    assert await lookup(asked.model_copy(update={"craft": None}), "CHEMISTRY") is NO_CATALOGUE
    assert sessions.opened == ["session"]


async def test_a_fault_in_the_catalogue_s_own_code_is_not_hidden_as_an_unavailable_database() -> None:
    lookup = catalogue_lookup(AwaySession(error=KeyError("label")))
    with pytest.raises(KeyError):
        await lookup(PlanRequest(question=QUESTION, mode="HYBRID", craft=AJRAKH), "CHEMISTRY")


async def test_a_component_of_another_purpose_leaves_every_builder_to_run() -> None:
    player = FakeBuilder(blocks=())
    builders = BlockBuilders([(entry(kind="reaction_player"), player)])
    answer = dataclasses.replace(
        pipeline(replies=[chose(PLATE.label)]), catalogue=FakeCatalogue((PLATE,)), builders=builders
    )
    await streamed(detailed(), answer)
    (asked,) = player.asks
    assert [block.kind for block in asked.blocks] == ["prose", "component"]
