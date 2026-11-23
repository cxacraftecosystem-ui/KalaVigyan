from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from typing import Any

from app.research.blocks import ExplainerSentence, ProseBlock
from app.research.citations import Citation, SourceRef
from app.research.crafts import CraftRef
from app.research.gi_registry import GiFields
from app.research.planning import PlanRequest
from app.research.sections import SectionSpec
from app.science.records import KnownClaim
from app.services.answer_events import CitedClaims
from app.services.builder_interface import BuildAsk
from app.services.curation_keys import curated_id
from app.services.curation_preview import master_craft, preview_records
from app.services.knowledge_view import ClaimView
from app.services.market_store import GiRecordOffer, MarketOffers, PriceOffer

from ..curation.import_support import plan_of
from ..research.fixtures import AJRAKH

__all__ = [
    "AJRAKH",
    "claim_view",
    "curated_offers",
    "insight_ask",
    "source",
    "written",
]

NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "test-insight")


def source(source_id: str, kind: str = "GI_JOURNAL") -> SourceRef:
    return SourceRef(
        id=source_id,
        kind=kind,
        title=f"{kind} {source_id}",
        authors=[],
        year=None,
        doi=None,
        url=None,
        publisher=None,
        licence=None,
        attribution=None,
        reliability="A",
    )


def written(key: str, text: str, quote: str | None = None, source_id: str = "s-gi") -> KnownClaim:
    claim_id = uuid.uuid5(NAMESPACE, f"claim/{key}")
    citation = Citation(
        id=str(uuid.uuid5(NAMESPACE, f"citation/{key}")),
        claim_id=str(claim_id),
        source_id=source_id,
        quote=quote or text,
        locator="p. 1",
        context=None,
        evidence="QUOTED",
        level="PROVISIONAL",
    )
    return KnownClaim(claim_id, text, "PROVISIONAL", (citation,))


def claim_view(claim: KnownClaim) -> ClaimView:
    return ClaimView(
        id=claim.id,
        text=claim.text,
        level=claim.level,
        concept_type="TRADITION",
        concept_id=None,
        citations=[citation.model_dump(mode="json", by_alias=True) for citation in claim.citations],
    )


def insight_ask(
    claims: Sequence[KnownClaim],
    sources: Mapping[str, SourceRef],
    *,
    discipline: str = "GEOGRAPHY",
    compared: tuple[CraftRef, ...] = (),
    shown: Sequence[Any] = (),
) -> BuildAsk:
    sentences = [
        ExplainerSentence(id=f"s4.b1.{n}", text=c.text, level=c.level, citations=list(c.citations), terms=[])
        for n, c in enumerate(claims, start=1)
    ]
    blocks = (
        [ProseBlock(id="s4.b1", kind="prose", version=1, reuse=None, sentences=sentences)] if claims else []
    )
    cited = CitedClaims(
        views={c.id: claim_view(c) for c in claims},
        sources={
            sid: sources[sid].model_dump(mode="json", by_alias=True)
            for block in blocks
            for sid in block.cited_source_ids()
        },
    )
    request = PlanRequest(
        question="How is Kutch Ajrakh sold?", mode="HYBRID", craft=AJRAKH, compared=compared
    )
    spec = SectionSpec(id="s4", discipline=discipline, title="Market", order=4)
    return BuildAsk(uuid.UUID(int=4), spec, request, (*blocks, *shown), cited)


def curated_offers(slug: str, *, candidates: Sequence[str] = ()) -> MarketOffers:
    plan = plan_of(slug)
    craft, names = master_craft(slug)
    records = preview_records(plan, craft, names)
    gi_rows = plan.part("giRecords")
    record = None
    if gi_rows:
        row = gi_rows[0]
        record = GiRecordOffer(
            fields=GiFields(
                application_number=row["applicationNumber"],
                certificate_number=row["certificateNumber"],
                filed_on=row["filedOn"],
                registered_on=row["registeredOn"],
                journal_issue=row["journalIssue"],
                proprietors=tuple(row["proprietors"]),
                authorised_user_count=row["authorisedUserCount"],
            ),
            claim_ids=tuple(row["claimIds"]),
            imitation=tuple(row["imitationClaimIds"]),
        )
    prices = tuple(
        PriceOffer(row["claimId"], row["pricedOn"], row["placeName"], row["districtLgd"])
        for row in plan.part("prices")
    )
    return MarketOffers(
        craft=CraftRef(slug=craft.slug, name=craft.name, path=f"/crafts/{craft.slug}"),
        record=record,
        prices=prices,
        candidates=tuple(curated_id(slug, key) for key in candidates),
        views={view.id: view for view in records.views},
        sources=records.sources,
    )
