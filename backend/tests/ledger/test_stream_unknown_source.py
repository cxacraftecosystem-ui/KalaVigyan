from typing import Any

import pytest

from app.research.blocks import ProseBlock
from app.research.explainer import ExplainerSection
from app.services.claim_ledger import admission_batches
from app.services.explainer_events import ExplainerStream

from .indigo_answer import recorded_sections
from .indigo_blocks import prose
from .indigo_claims import GI_COPY, IJTK, NAAND, SOURCES, Claim

ORDER = ("s1", "s2", "s3", "s4", "s5")


class Recorded:
    def __init__(self) -> None:
        self.events: list[tuple[str, Any]] = []

    async def __call__(self, name: str, data: Any) -> None:
        self.events.append((name, data))

    def blocks(self) -> list[Any]:
        return [data["block"] for name, data in self.events if name == "block"]

    def source_ids(self) -> set[str]:
        return {data["id"] for name, data in self.events if name == "source"}


def _sections() -> dict[str, ExplainerSection]:
    return {payload["id"]: ExplainerSection.model_validate(payload) for payload in recorded_sections()}


def _first_cited_source(sections: dict[str, ExplainerSection]) -> str:
    for section_id in ORDER:
        for block in sections[section_id].blocks:
            if block.cited_source_ids():
                return block.cited_source_ids()[0]
    raise AssertionError("the recorded answer cites no source")


async def _streamed(
    stream: ExplainerStream, sections: dict[str, ExplainerSection], refs: dict[str, Any]
) -> list[Any]:
    returned: list[Any] = []
    for section_id in ORDER:
        for batch in admission_batches(sections[section_id].blocks):
            returned += await stream.blocks(section_id, batch, refs)
    return returned


async def test_an_answer_whose_source_is_withheld_goes_on_and_shows_no_citation_without_its_source() -> None:
    sections = _sections()
    withheld = _first_cited_source(sections)
    refs = {ref["id"]: ref for ref in SOURCES if ref["id"] != withheld}
    recorded = Recorded()
    returned = await _streamed(ExplainerStream(recorded, language="en"), sections, refs)
    shown = recorded.blocks()
    assert shown
    assert [block.id for block in returned] == [block.id for block in shown]
    assert not any(withheld in block.cited_source_ids() for block in shown)
    assert {source for block in shown for source in block.cited_source_ids()} <= recorded.source_ids()
    assert withheld not in recorded.source_ids()


async def test_a_block_admitted_with_a_citation_to_a_source_not_sent_is_left_out_whole(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sections = _sections()
    withheld = _first_cited_source(sections)
    citing = {
        block.id
        for section in sections.values()
        for block in section.blocks
        if withheld in block.cited_source_ids()
    }
    every = {block.id for section in sections.values() for block in section.blocks}
    refs = {ref["id"]: ref for ref in SOURCES if ref["id"] != withheld}
    recorded = Recorded()
    stream = ExplainerStream(recorded, language="en")
    monkeypatch.setattr(stream.ledger, "admit", lambda section_id, blocks, sources: list(blocks))
    returned = await _streamed(stream, sections, refs)
    assert citing
    assert {block.id for block in returned} == every - citing
    assert {block.id for block in recorded.blocks()} == every - citing
    assert withheld not in recorded.source_ids()


async def test_a_block_left_out_for_a_source_not_sent_marks_nothing_it_says_as_shown() -> None:
    unsendable = Claim(NAAND.key, NAAND.text, (IJTK,))
    sendable = Claim(NAAND.key, NAAND.text, (GI_COPY,))
    refs = {ref["id"]: ref for ref in SOURCES if ref["id"] != IJTK["id"]}
    recorded = Recorded()
    stream = ExplainerStream(recorded, language="en")
    first = ProseBlock.model_validate(prose("s1.b1", (NAAND.text, (unsendable,))))
    later = ProseBlock.model_validate(prose("s1.b2", (NAAND.text, (sendable,))))
    assert await stream.blocks("s1", [first], refs) == []
    assert [block.id for block in await stream.blocks("s1", [later], refs)] == ["s1.b2"]
    assert [block.id for block in recorded.blocks()] == ["s1.b2"]
