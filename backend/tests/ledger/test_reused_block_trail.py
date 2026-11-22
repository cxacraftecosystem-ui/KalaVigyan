import uuid
from datetime import UTC, datetime
from typing import Any

from app.research.blocks import ReuseMarker
from app.research.explainer import ExplainerSection
from app.research.sections import SectionSpec
from app.services.explainer_events import ExplainerStream

from .indigo_answer import recorded_sections
from .indigo_claims import SOURCES

PIECE = uuid.UUID("3c1f6a52-8d0e-4f7b-9a21-5e6d7c8b9a01")
STORED_AT = datetime(2026, 11, 12, 8, 15, tzinfo=UTC)
TITLE = "Why alum fixes the red"


class Recorded:
    def __init__(self) -> None:
        self.events: list[tuple[str, Any]] = []

    async def __call__(self, name: str, data: Any) -> None:
        self.events.append((name, data))


def first_section() -> ExplainerSection:
    return ExplainerSection.model_validate(recorded_sections()[0])


async def test_a_stored_piece_a_builder_places_in_a_fresh_section_gets_its_trail_entry() -> None:
    section = first_section()
    reused = section.blocks[0].model_copy(update={"reuse": ReuseMarker(piece_id=PIECE, stored_at=STORED_AT)})
    recorded = Recorded()
    stream = ExplainerStream(recorded, language="en")
    spec = SectionSpec(id=section.id, discipline="CHEMISTRY", title=TITLE, order=1)
    await stream.section_started(spec, titles={}, state="RESEARCHING")
    sent = await stream.blocks(section.id, [reused], {ref["id"]: ref for ref in SOURCES})
    assert [block.id for block in sent] == [reused.id]
    names = [name for name, _ in recorded.events if name in {"trail", "block"}]
    assert names == ["trail", "block"]
    trail = next(data for name, data in recorded.events if name == "trail")
    assert (trail["key"], trail["stage"], trail["group"]) == (f"piece:{PIECE}", "FOUND", "STORED")
    assert (trail["title"], trail["storedAt"]) == (TITLE, STORED_AT)


async def test_a_block_built_afresh_adds_no_trail_entry() -> None:
    section = first_section()
    recorded = Recorded()
    stream = ExplainerStream(recorded, language="en")
    spec = SectionSpec(id=section.id, discipline="CHEMISTRY", title=TITLE, order=1)
    await stream.section_started(spec, titles={}, state="RESEARCHING")
    await stream.blocks(section.id, [section.blocks[0]], {ref["id"]: ref for ref in SOURCES})
    assert [name for name, _ in recorded.events if name == "trail"] == []
