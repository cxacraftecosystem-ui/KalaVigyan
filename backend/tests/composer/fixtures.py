import json
import uuid
from collections.abc import Sequence
from typing import Any

from app.research.evidence import EvidenceItem, Quote
from app.research.evidence_pack import EvidencePack, PackedEvidence, ResearchFailure
from app.research.planning import FacetCoverage, RetrievalPlan
from app.research.retrieval import ChunkHit, ClaimHit, KnowledgeHits
from app.sources.adapter import build_document

from ..research.fixtures import AJRAKH, evidence_item

QUESTION = "Why does alum keep Ajrakh red?"
ALUM_CLAIM_ID = uuid.UUID("3f2a1b0c-9d8e-4f7a-8b6c-5d4e3f2a1b0c")
GUESS_CLAIM_ID = uuid.UUID("7a6b5c4d-3e2f-4a1b-9c8d-7e6f5a4b3c2d")
ALUM_CLAIM_TEXT = "Alum is the mordant that binds alizarin to cotton in Ajrakh."
GUESS_CLAIM_TEXT = "Lime in the wash water may brighten the red."
ABSTRACT = (
    "Alizarin forms an insoluble red lake with aluminium ions. "
    "Mordanting baths of 8 g/L alum were heated to 60 °C before dyeing."
)
LONG_QUOTES = ("the lake withstood 20 washes", "fastness rose with mordant strength")
LONG_TEXT = (
    ("Background on resist printing. " * 140)
    + "In tests the lake withstood 20 washes. "
    + ("Results show fastness rose with mordant strength. " * 2)
).strip()
UNQUOTED_LONG_TEXT = ("Kutch block printing workshops. " * 150).strip()

PLAN = RetrievalPlan.model_validate(
    {
        "mode": "HYBRID",
        "craft": AJRAKH,
        "intent": "SCIENCE",
        "language": "en",
        "needsRegion": False,
        "facets": [{"type": "MATERIAL", "target": "alum"}],
        "tiers": ["T0", "T1", "T2", "T3", "T4"],
        "queries": [
            {"tier": "T3", "facetIndex": 0, "query": {"text": "Kutch Ajrakh alum mordant"}},
            {"tier": "T4", "facetIndex": 0, "query": {"text": "Kutch Ajrakh alizarin lake"}},
        ],
        "maxFetches": 10,
    }
)


def claim_hit(claim_id: uuid.UUID, text: str, level: str) -> ClaimHit:
    return ClaimHit(
        claim_id=claim_id,
        text=text,
        level=level,
        subject_type="CONCEPT",
        subject_id=uuid.uuid5(uuid.NAMESPACE_DNS, text),
        score=0.03,
    )


ABSTRACT_ITEM = evidence_item(
    id="crossref:10.1000/lake",
    adapter="crossref",
    title="Alizarin lakes on cotton",
    publisher="Journal of Dye Chemistry",
    published="2019-07",
    doi="10.1000/lake",
    url="https://doi.org/10.1000/lake",
    quotes=[],
)
LONG_ITEM = evidence_item(
    id="searxng:https://crafts.example.org/ajrakh",
    adapter="searxng",
    tier="T4",
    sourceType="WEB_PAGE",
    url="https://crafts.example.org/ajrakh",
    title="Ajrakh fastness notes",
    published=None,
    doi=None,
    publisher=None,
    trust="C",
    quotes=[Quote(text=text) for text in LONG_QUOTES],
)
UNQUOTED_ITEM = evidence_item(
    id="searxng:https://crafts.example.org/workshops",
    adapter="searxng",
    tier="T4",
    sourceType="WEB_PAGE",
    url="https://crafts.example.org/workshops",
    title="Workshops",
    doi=None,
    trust="C",
    quotes=[],
)
UNREAD_ITEM = evidence_item(
    id="openalex:W9", url="https://works.example.org/W9", doi=None, quotes=[Quote(text="never read")]
)


def packed(item: EvidenceItem, *found_by: str) -> PackedEvidence:
    return PackedEvidence(item=item, facet_indexes=(0,), found_by=found_by, hits=1, best_rank=1)


STORED = KnowledgeHits(
    craft_slug=AJRAKH.slug,
    claims=(
        claim_hit(ALUM_CLAIM_ID, ALUM_CLAIM_TEXT, "REVIEWED"),
        claim_hit(GUESS_CLAIM_ID, GUESS_CLAIM_TEXT, "HYPOTHESIS"),
    ),
    chunks=(
        ChunkHit(
            chunk_id=uuid.UUID(int=11),
            source_id=uuid.UUID(int=12),
            ordinal=0,
            text="stored passage",
            score=0.02,
        ),
    ),
)
RATE_LIMITED = ResearchFailure(
    stage="SEARCH",
    service="semantic_scholar",
    target="Kutch Ajrakh alum mordant",
    kind="rate_limit",
    message="429",
)


def pack(**changes: Any) -> EvidencePack:
    fields: dict[str, Any] = {
        "plan": PLAN,
        "degraded": False,
        "stored": STORED,
        "coverage": (FacetCoverage(facet_index=0),),
        "evidence": (
            packed(ABSTRACT_ITEM, "crossref"),
            packed(LONG_ITEM, "web"),
            packed(UNQUOTED_ITEM, "web"),
            packed(UNREAD_ITEM, "openalex"),
        ),
        "documents": (
            build_document(ABSTRACT_ITEM, ABSTRACT, "ABSTRACT"),
            build_document(LONG_ITEM, LONG_TEXT, "FULL_TEXT"),
            build_document(UNQUOTED_ITEM, UNQUOTED_LONG_TEXT, "FULL_TEXT"),
        ),
        "failures": (RATE_LIMITED,),
    }
    fields.update(changes)
    return EvidencePack(**fields)


def quote(source: object, text: str) -> dict[str, str]:
    return {"source": str(source), "quote": text}


def sentence(text: str, *quotes: dict[str, str]) -> dict[str, Any]:
    return {"text": text, "quotes": list(quotes)}


def lede_sentences(*items: dict[str, Any], answer: int = 0) -> list[dict[str, Any]]:
    return [{**item, "answer": n == answer} for n, item in enumerate(items)]


def answer(*sections: tuple[str, Sequence[dict[str, Any]]], follow_ups: Sequence[str] = ()) -> str:
    return json.dumps(
        {
            "sections": [{"heading": heading, "sentences": list(items)} for heading, items in sections],
            "followUps": list(follow_ups),
        }
    )


def replacements(*items: tuple[int, dict[str, Any]]) -> str:
    return json.dumps({"sentences": [{"index": index, **item} for index, item in items]})


def section_reply(
    *items: dict[str, Any], stages: Sequence[object] | None = None, follow_ups: Sequence[str] = ()
) -> str:
    reply: dict[str, Any] = {"sentences": list(items), "followUps": list(follow_ups)}
    if stages is not None:
        reply["stages"] = [str(stage) for stage in stages]
    return json.dumps(reply)
