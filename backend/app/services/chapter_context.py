from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace

from app.geo.climate import ClimateTrends
from app.geo.rainfall import DistrictRainfall
from app.research.blocks import ExplainerSentence
from app.research.blocks_climate import ClimateSeries
from app.research.blocks_play import SimulationBlock
from app.research.citations import SourceRef
from app.research.craft_page import PageClaim
from app.research.datasets import DatasetRef
from app.research.vocabulary import FACT_LEVELS
from app.science.records import CompoundRecord, KnownClaim, MaterialRecord, ProcessRecords, StageRecord

from .craft_matter import CraftMatter, material_rows
from .craft_page_parts import Visible
from .craft_page_records import CraftPageRecords
from .curated_category_index import CuratedCategoryPage
from .region_story import RegionOffer

__all__ = [
    "ChapterContext",
    "ChapterRows",
    "FamilyScience",
    "PlacePoint",
    "StoredExplainer",
]


@dataclass(frozen=True)
class FamilyScience:
    slug: str
    label: str
    path: str
    index: CuratedCategoryPage | None
    claims: tuple[PageClaim, ...]
    sources: Mapping[str, SourceRef]


@dataclass(frozen=True)
class StoredExplainer:
    piece_id: uuid.UUID
    term_key: str
    block: SimulationBlock
    sources: Mapping[str, SourceRef] = field(default_factory=dict)


@dataclass(frozen=True)
class PlacePoint:
    wikidata_id: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class ChapterRows:
    compounds: Mapping[uuid.UUID, CompoundRecord] = field(default_factory=dict)
    material_compounds: Mapping[uuid.UUID, uuid.UUID] = field(default_factory=dict)
    record_sources: Mapping[str, SourceRef] = field(default_factory=dict)
    conformers: frozenset[int] = frozenset()
    family: FamilyScience | None = None
    region: RegionOffer | None = None
    climate: ClimateTrends = field(default_factory=ClimateTrends)
    series: tuple[ClimateSeries, ...] = ()
    rainfall: DistrictRainfall | None = None
    points: Mapping[str, PlacePoint] = field(default_factory=dict)
    explainers: tuple[StoredExplainer, ...] = ()
    datasets: Mapping[str, DatasetRef] = field(default_factory=dict)
    site: str = ""


@dataclass(frozen=True)
class ChapterContext:
    records: CraftPageRecords
    rows: ChapterRows
    claims: Mapping[uuid.UUID, PageClaim]
    visible: Visible
    own: frozenset[uuid.UUID] = frozenset()

    @property
    def craft_name(self) -> str:
        return self.records.craft.display_name

    def known(self, claim_id: uuid.UUID) -> KnownClaim | None:
        claim = self.claims.get(claim_id)
        if claim is None:
            return None
        return KnownClaim(claim.id, claim.text, claim.level, tuple(claim.citations))

    def sentence(self, claim_id: uuid.UUID, sentence_id: str) -> ExplainerSentence | None:
        claim = self.claims.get(claim_id)
        if claim is None:
            return None
        return ExplainerSentence(
            id=sentence_id, text=claim.text, level=claim.level, citations=list(claim.citations), terms=[]
        )

    def facts(self, claim_ids: Iterable[uuid.UUID], prefix: str) -> list[ExplainerSentence]:
        shown = [
            claim_id
            for claim_id in dict.fromkeys(claim_ids)
            if claim_id in self.claims and self.claims[claim_id].level in FACT_LEVELS
        ]
        found = []
        for n, claim_id in enumerate(shown, start=1):
            sentence = self.sentence(claim_id, f"{prefix}.{n}")
            if sentence is not None:
                found.append(sentence)
        return found

    def process(self) -> ProcessRecords:
        known = {claim_id: fact for claim_id in self.claims if (fact := self.known(claim_id)) is not None}
        stored = self.records.process
        sources = {**stored.sources, **self.records.sources, **self.rows.record_sources}
        uses = tuple(self._with_compound(use) for use in stored.materials)
        stages = tuple(self._with_listed(stage) for stage in stored.stages)
        return replace(stored, stages=stages, materials=uses, claims=known, sources=sources)

    def _with_listed(self, stage: StageRecord) -> StageRecord:
        curated = self.records.curated
        entry = next((e for e in curated.stages if e.stage_id == stage.id), None) if curated else None
        if entry is None or any(self._is_fact(claim_id) for claim_id in stage.claim_ids):
            return stage
        listed = [c for c in entry.claim_ids if c != entry.why_claim_id and self._is_fact(c)]
        return replace(stage, claim_ids=tuple(dict.fromkeys([*stage.claim_ids, *listed])))

    def _is_fact(self, claim_id: uuid.UUID) -> bool:
        claim = self.claims.get(claim_id)
        return claim is not None and claim.level in FACT_LEVELS

    def matter(self) -> CraftMatter:
        records = self.process()
        sources = {
            sid: ref.model_dump(mode="json", by_alias=True) for sid, ref in self.rows.record_sources.items()
        }
        return CraftMatter(
            records=records,
            materials=material_rows(records.materials, {}),
            compounds=dict(self.rows.compounds),
            record_sources=sources,
        )

    def _with_compound(self, use: MaterialRecord) -> MaterialRecord:
        if use.compound is not None or use.material_id is None:
            return use
        compound_id = self.rows.material_compounds.get(use.material_id)
        compound = self.rows.compounds.get(compound_id) if compound_id else None
        return replace(use, compound=compound) if compound is not None else use

    def ordered(self, claim_ids: Sequence[uuid.UUID]) -> list[uuid.UUID]:
        return self.visible.ranked(claim_ids)

    def dossier_ordered(self, claim_ids: Iterable[uuid.UUID]) -> list[uuid.UUID]:
        curated = self.records.curated
        order = {claim_id: n for n, claim_id in enumerate(curated.claim_order if curated else ())}
        page = self.visible.order
        known = [claim_id for claim_id in dict.fromkeys(claim_ids) if claim_id in self.claims]
        return sorted(known, key=lambda c: (order.get(c, len(order)), page.get(c, len(page)), str(c)))
