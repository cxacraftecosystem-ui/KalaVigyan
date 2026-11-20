from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from app.research.component_proposals import ComponentProposalDraft
from app.research.component_specs_general_delivery import DeliveredComponent
from app.research.evidence import canonical_url
from app.research.knowledge_writes import ProposedSource
from app.research.monograph_page import CitedSource
from app.research.page_layout import PageLayout

from .component_proposals_spec import CheckedDelivery
from .knowledge_view import ClaimView
from .monograph_generated_parts import RegisteredComponent
from .page_preview_additions import PageAdditions
from .page_proposals_parts import BundleFacts

__all__ = ["PREVIEW_LEVEL", "PREVIEW_NAMESPACE", "PreviewDraft", "previewed_component"]

PREVIEW_NAMESPACE = uuid.UUID("5d1c2c5e-7a3f-4c1b-9a8e-0b6f3e2d7c41")
PREVIEW_LEVEL = "PROVISIONAL"
SUBJECT_PREFIXES = {"CRAFT": "craft", "CONCEPT": "concept", "COMPOUND": "compound", "PLACE": "place"}


@dataclass
class PreviewDraft:
    digest: str
    facts: BundleFacts = field(default_factory=BundleFacts)
    sentences: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    claims: dict[uuid.UUID, ClaimView] = field(default_factory=dict)
    sources: dict[str, CitedSource] = field(default_factory=dict)
    components: list[RegisteredComponent] = field(default_factory=list)
    layout: PageLayout | None = None

    def drafted(
        self, key: str, field_name: str, statement: str, sources: Sequence[ProposedSource]
    ) -> uuid.UUID:
        claim_id = uuid.uuid5(PREVIEW_NAMESPACE, f"{self.digest}:{key}")
        citations = [
            _citation(claim_id, self._source(source), quote.text, quote.locator)
            for source in sources
            for quote in source.quotes
        ]
        self.claims[claim_id] = ClaimView(
            id=claim_id,
            text=statement,
            level=PREVIEW_LEVEL,
            concept_type="",
            concept_id=None,
            citations=citations,
        )
        self.sentences.setdefault(field_name, []).append({"text": statement, "claimIds": [str(claim_id)]})
        return claim_id

    def additions(self) -> PageAdditions:
        return PageAdditions(
            sentences={name: tuple(sentences) for name, sentences in self.sentences.items()},
            claims=dict(self.claims),
            sources=dict(self.sources),
            delivered=tuple(self.components),
            layout=self.layout,
        )

    def _source(self, source: ProposedSource) -> uuid.UUID:
        source_id = uuid.uuid5(PREVIEW_NAMESPACE, canonical_url(source.url))
        self.sources[str(source_id)] = CitedSource(
            number=1,
            title=source.title,
            full_title=None,
            publisher=None,
            year=None,
            grade=None,
            url=source.url,
            extra=None,
            dossier_source_id=None,
        )
        return source_id


def previewed_component(draft: ComponentProposalDraft, delivery: CheckedDelivery) -> RegisteredComponent:
    return RegisteredComponent(
        label=draft.label,
        kind=draft.kind,
        title=draft.title,
        description=draft.description,
        field=draft.field,
        fields=tuple(draft.fields),
        subjects=tuple(f"{SUBJECT_PREFIXES[subject.kind]}:{subject.key}" for subject in draft.subjects),
        monograph=None,
        anchor=None,
        delivered=DeliveredComponent.model_validate({"spec": delivery.spec, "units": delivery.units}),
    )


def _citation(claim_id: uuid.UUID, source_id: uuid.UUID, quote: str, locator: str | None) -> dict[str, Any]:
    return {
        "id": str(uuid.uuid5(PREVIEW_NAMESPACE, f"{claim_id}:{source_id}:{quote}")),
        "claimId": str(claim_id),
        "sourceId": str(source_id),
        "quote": quote,
        "locator": locator,
        "context": None,
        "evidence": "QUOTED",
        "level": PREVIEW_LEVEL,
    }
