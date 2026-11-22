import json
import uuid
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from functools import cache
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from app.curation.checks import default_context
from app.curation.files import CURATION_DIR, checked_dossier
from app.data.district_register import load_district_codes
from app.models import Source
from app.research.blocks_insight import MarketGiBlock
from app.research.blocks_people import ExpertViewBlock
from app.research.citations import Citation, SourceRef
from app.research.expert_panel import speaking_seats
from app.research.explainer import Block, BlockEvent, with_payload_sentences
from app.research.knowledge_pieces import KnowledgePiece
from app.research.structured import StructuredReply
from app.research.term_marking import GlossaryEntry
from app.science.records import KnownClaim, ProcessRecords
from app.services.answer_events import cited_claims
from app.services.block_builders import BLOCK_BUILDERS, BlockBuilders
from app.services.builder_interface import BuildAsk, Built
from app.services.curation_overview import curated_glossary, overview_pieces
from app.services.curation_plan import curation_plan
from app.services.curation_preview import dossier_records, master_craft, plan_views
from app.services.curation_rows import CraftTarget
from app.services.knowledge_view import ClaimView, source_ref

from .piece_fakes import CRAFT_ID

__all__ = [
    "GOLDEN_KINDS",
    "OWNER_QUESTION",
    "OWNER_SEATS",
    "OWNER_UNDERSTOOD",
    "AlwaysReply",
    "CuratedAjrakh",
    "GoldenBuilder",
    "curated_ajrakh",
    "golden_builders",
]

SLUG = "Kutch-Ajrakh"
SEATS_KIND = "expert_view"
BLOCKS = TypeAdapter(Block)
SHARED = Path(__file__).resolve().parents[3] / "shared"
OWNER_QUESTION = (
    "explain how Ajrakh works in the most complete comprehensive exhaustive detailed description manual "
    "from all the angles of how the craft evolved the history in the geography the politics the chemistry "
    "and everything"
)
OWNER_SEATS = ["ARTISAN", "HISTORIAN", "CHEMIST", "ECONOMIST", "ANTHROPOLOGIST", "MATERIALS_SCIENTIST"]
OWNER_UNDERSTOOD = {
    "craft": "",
    "craftNames": [],
    "disciplines": ["OVERVIEW", "PROCESS", "CHEMISTRY", "HISTORY", "GEOGRAPHY", "ECONOMICS", "DESIGN"],
    "seats": OWNER_SEATS,
}
GOLDEN_FILES = (
    "explainer.phase-b.golden.json",
    "explainer.phase-c.golden.json",
    "explainer.phase-d.golden.json",
)
GOLDEN_KINDS = (
    "molecule_3d",
    "region_story",
    "map_layer",
    "seasons",
    "supply_map",
    "climate_risk",
    "market_gi",
    "material_card",
    "what_if",
    "simulation",
    "zoom_story",
    "timeline_map",
    "concept_graph",
)


@dataclass(frozen=True)
class CuratedAjrakh:
    views: tuple[ClaimView, ...]
    sources: Mapping[uuid.UUID, Source]
    pieces: tuple[KnowledgePiece, ...]
    process: ProcessRecords
    glossary: tuple[GlossaryEntry, ...]
    claim_disciplines: Mapping[str, int]
    curated_at: Any


@cache
def curated_ajrakh() -> CuratedAjrakh:
    path = CURATION_DIR / f"{SLUG}.json"
    result = checked_dossier(path, default_context())
    assert result.dossier is not None and result.check is not None
    craft, _ = master_craft(SLUG)
    target = CraftTarget(id=craft.id, slug=craft.slug, name=craft.name)
    plan = curation_plan(result.dossier, result.check, target, load_district_codes())
    views, sources = plan_views(plan)
    cited = cited_claims(list(views.values()), sources)
    overview = overview_pieces(result.dossier, cited, craft_id=CRAFT_ID, districts=())
    counts = Counter(claim["discipline"] for claim in json.loads(path.read_text(encoding="utf-8"))["claims"])
    return CuratedAjrakh(
        views=tuple(views.values()),
        sources=sources,
        pieces=overview.pieces,
        process=_with_claims(dossier_records(SLUG).process, views.values(), sources),
        glossary=tuple(curated_glossary(result.dossier)),
        claim_disciplines=dict(counts),
        curated_at=result.dossier.curated_at,
    )


def _with_claims(
    process: ProcessRecords, views: Sequence[ClaimView] | Any, sources: Mapping[uuid.UUID, Source]
) -> ProcessRecords:
    claims = {
        view.id: KnownClaim(
            view.id, view.text, view.level, tuple(Citation.model_validate(c) for c in view.citations)
        )
        for view in views
    }
    refs = {str(key): SourceRef.model_validate(source_ref(row)) for key, row in sources.items()}
    return replace(process, claims=claims, sources=refs)


@dataclass
class AlwaysReply:
    reply: str
    calls: list[str] = field(default_factory=list)

    async def __call__(self, *, system: str, user: str, schema: Mapping[str, Any]) -> StructuredReply:
        self.calls.append(user)
        staged = "stages" in schema.get("properties", {})
        reply = {**json.loads(self.reply), "stages": []} if staged else json.loads(self.reply)
        return StructuredReply(text=json.dumps(reply), degraded=False)


@dataclass
class GoldenBuilder:
    blocks: tuple[Block, ...]
    sources: Mapping[str, Mapping[str, Any]]
    asked: list[tuple[str, int]] = field(default_factory=list)

    async def build(self, ask: BuildAsk) -> Built:
        self.asked.append((ask.section.discipline, len(ask.blocks)))
        served = [block for block in self.blocks if _serves(block, ask)]
        return Built(
            tuple(_told_in(ask.section.id, n, block) for n, block in enumerate(served, 1)), self.sources
        )


def golden_builders(kinds: Sequence[str] = GOLDEN_KINDS) -> tuple[BlockBuilders, dict[str, GoldenBuilder]]:
    blocks, sources = _golden_blocks()
    made = {kind: GoldenBuilder(tuple(blocks[kind]), sources) for kind in (*kinds, SEATS_KIND)}
    pairs = [(entry, made[entry.kind]) for entry in BLOCK_BUILDERS if entry.kind in made]
    return BlockBuilders(pairs), made


def _serves(block: Block, ask: BuildAsk) -> bool:
    if isinstance(block, MarketGiBlock):
        asked = [craft.slug for craft in (ask.request.craft, *ask.request.compared) if craft is not None]
        return block.craft.slug in asked
    if isinstance(block, ExpertViewBlock):
        return block.seat in speaking_seats(
            ask.section.discipline, ask.request.seats, depth=ask.request.depth
        )
    return True


def _told_in(section_id: str, number: int, block: Block) -> Block:
    def told(sentence: dict[str, Any]) -> dict[str, Any]:
        return {**sentence, "text": f"{sentence['text']} As told in {section_id}."}

    payload = block.model_dump(mode="json", by_alias=True) | {"id": f"{section_id}.golden{number}"}
    return BLOCKS.validate_python(with_payload_sentences(payload, told))


@cache
def _golden_blocks() -> tuple[dict[str, list[Block]], dict[str, dict[str, Any]]]:
    blocks: dict[str, list[Block]] = {}
    sources: dict[str, dict[str, Any]] = {}
    for name in GOLDEN_FILES:
        golden = json.loads((SHARED / name).read_text(encoding="utf-8"))
        sources.update({ref["id"]: ref for ref in golden["sources"]})
        for section in golden["sections"]:
            for payload in section["blocks"]:
                if payload["kind"] == "quiz":
                    continue
                event = {"sectionId": section["id"], "block": {**payload, "reuse": None}}
                blocks.setdefault(payload["kind"], []).append(BlockEvent.model_validate(event).block)
    return blocks, sources
