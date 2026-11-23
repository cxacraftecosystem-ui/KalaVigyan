import asyncio
import dataclasses
from typing import Any

import pytest

from app.services import craft_matter as craft_matter_module
from app.services.block_builders import BlockBuilders, BuilderEntry
from app.services.builder_interface import BuildAsk, Built
from app.services.craft_matter import CraftMatter, MatterReads

from ..research.fixtures import AJRAKH, BAGRU
from ..science.golden_process import golden_records
from .fixtures import chemistry_ask


@dataclasses.dataclass
class MatterReader:
    seen: list[CraftMatter | None] = dataclasses.field(default_factory=list)

    async def build(self, ask: BuildAsk) -> Built:
        assert ask.request.craft is not None
        self.seen.append(await ask.matter.read(None, ask.request.craft))
        return Built()


@pytest.fixture
def reads(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    asked: list[str] = []

    async def load(sessions: Any, craft: Any) -> CraftMatter:
        asked.append(craft.slug)
        await asyncio.sleep(0)
        return CraftMatter(records=golden_records())

    monkeypatch.setattr(craft_matter_module, "craft_matter", load)
    return asked


def matter_entries() -> list[tuple[BuilderEntry, MatterReader]]:
    fields = (
        frozenset({"CHEMISTRY"}),
        frozenset({"CHEMISTRY", "MATERIALS"}),
        frozenset({"CHEMISTRY", "MATERIALS"}),
    )
    kinds = ("reaction_player", "material_card", "molecule_3d")
    return [
        (BuilderEntry(kind, field, lambda tools: MatterReader()), MatterReader())
        for kind, field in zip(kinds, fields, strict=True)
    ]


async def test_a_chemistry_section_s_three_matter_builders_read_the_craft_s_matter_once(
    reads: list[str],
) -> None:
    pairs = matter_entries()
    await BlockBuilders(pairs).added(chemistry_ask())
    assert reads == ["Kutch-Ajrakh"]
    seen = [reader.seen for _, reader in pairs]
    assert all(len(one) == 1 for one in seen)
    assert seen[0][0] is seen[1][0] is seen[2][0]


async def test_an_answer_s_chemistry_and_materials_sections_share_one_read(reads: list[str]) -> None:
    builders = BlockBuilders(matter_entries()).for_answer()
    await builders.added(chemistry_ask())
    await builders.without(set()).added(chemistry_ask(discipline="MATERIALS"))
    assert reads == ["Kutch-Ajrakh"]


async def test_each_answer_reads_the_matter_afresh(reads: list[str]) -> None:
    registry = BlockBuilders(matter_entries())
    await registry.for_answer().added(chemistry_ask())
    await registry.for_answer().added(chemistry_ask())
    assert reads == ["Kutch-Ajrakh", "Kutch-Ajrakh"]


async def test_one_answer_reads_each_craft_it_asks_about_once(reads: list[str]) -> None:
    matter = MatterReads()
    together = await asyncio.gather(
        matter.read(None, AJRAKH), matter.read(None, AJRAKH), matter.read(None, BAGRU)
    )
    assert sorted(reads) == ["Bagru-Print", "Kutch-Ajrakh"]
    assert together[0] is together[1] is not together[2]


async def test_a_read_cut_off_by_its_builder_s_wait_is_read_again_by_the_next(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started: list[str] = []
    release = asyncio.Event()

    async def load(sessions: Any, craft: Any) -> CraftMatter:
        started.append(craft.slug)
        if len(started) == 1:
            await release.wait()
        return CraftMatter(records=golden_records())

    monkeypatch.setattr(craft_matter_module, "craft_matter", load)
    matter = MatterReads()
    first = asyncio.create_task(matter.read(None, AJRAKH))
    await asyncio.sleep(0)
    first.cancel()
    await asyncio.gather(first, return_exceptions=True)
    found = await matter.read(None, AJRAKH)
    assert started == ["Kutch-Ajrakh", "Kutch-Ajrakh"]
    assert found is not None
