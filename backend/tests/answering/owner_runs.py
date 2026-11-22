import dataclasses
import json
from collections import Counter
from typing import Any

import pytest

from app.research.explainer import Explainer
from app.science.records import ProcessRecords
from app.services import craft_matter as craft_matter_module
from app.services.answering import AnswerAsk, AnswerPipeline
from app.services.block_builders import BLOCK_BUILDERS, BlockBuilders
from app.services.builder_interface import BuilderTools
from app.services.craft_matter import CraftMatter
from app.services.matter_builders import ReactionPlayerBuilder
from app.services.stored_fields import fields_held

from ..planner.fakes import FakeModel
from ..science.golden_process import golden_records
from .fakes import GLOSSARY, SOURCES, VIEWS, FakeEnrichment, FakeStore, pipeline, streamed
from .owner_fixtures import (
    OWNER_QUESTION,
    OWNER_UNDERSTOOD,
    AlwaysReply,
    GoldenBuilder,
    curated_ajrakh,
    golden_builders,
)
from .piece_fakes import MemoryPieces
from .test_answer_flow import REPLY, events

__all__ = ["Owner", "answered", "asked", "kinds", "owner", "owner_pieces", "seeded_matter"]


@dataclasses.dataclass
class Owner:
    pipeline: AnswerPipeline
    store: FakeStore
    pieces: MemoryPieces
    builders: dict[str, GoldenBuilder]


def seeded_matter(monkeypatch: pytest.MonkeyPatch, records: ProcessRecords | None = None) -> None:
    async def load(sessions: Any, craft: Any) -> CraftMatter:
        return CraftMatter(records=records or golden_records())

    monkeypatch.setattr(craft_matter_module, "craft_matter", load)


def owner_pieces() -> MemoryPieces:
    curated = curated_ajrakh()
    return MemoryPieces(
        views=(*curated.views, *VIEWS),
        sources={**curated.sources, **SOURCES},
        pieces=list(curated.pieces),
        held_fields=fields_held(curated.claim_disciplines),
    )


def owner(pieces: MemoryPieces | None = None, *, golden: bool = True) -> Owner:
    curated = curated_ajrakh()
    _, made = golden_builders() if golden else (None, {})
    tools = BuilderTools(sessions=None, live=None, plan_model=None, compose_model=None)
    played = {"reaction_player": ReactionPlayerBuilder(tools)}
    pairs = [(e, played.get(e.kind) or made[e.kind]) for e in BLOCK_BUILDERS if e.kind in {*made, *played}]
    store = FakeStore(records=curated.process)
    held = pieces or owner_pieces()
    built = pipeline(
        understand_model=FakeModel([json.dumps(OWNER_UNDERSTOOD)]),
        compose_model=AlwaysReply(REPLY),
        store=store,
        pieces=held,
        enrichment=FakeEnrichment(entries=(*curated.glossary, *GLOSSARY)),
    )
    return Owner(dataclasses.replace(built, builders=BlockBuilders(pairs)), store, held, made)


def asked(depth: str = "EXPERT") -> AnswerAsk:
    return AnswerAsk(question=OWNER_QUESTION, depth=depth, role="MASTER_ADMIN")


async def answered(run: Owner, depth: str = "EXPERT") -> Explainer:
    found = events(await streamed(asked(depth), run.pipeline))
    assert [name for name, _ in found][-1] == "done"
    assert not [data for name, data in found if name == "error"]
    return run.store.finished[-1]["explainer"]


def kinds(explainer: Explainer) -> Counter[str]:
    return Counter(block.kind for section in explainer.sections for block in section.blocks)
