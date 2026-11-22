from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from app.research.blocks_lede import LedeBlock
from app.research.citations import SourceRef
from app.research.explainer import EXPLAINER_SCHEMA_VERSION, Explainer, ExplainerSection, Understood

from .explainer_events import shown_title
from .ledgered_explainer import ledgered_explainer
from .section_context import SectionOutcome

__all__ = ["explainer_document"]


def explainer_document(
    *,
    answer_id: uuid.UUID,
    question: str,
    understood: Understood,
    outcomes: Sequence[SectionOutcome],
    titles: Mapping[str, str],
    follow_ups: Sequence[str],
    lede: LedeBlock | None = None,
    lede_sources: Mapping[str, Mapping[str, Any]] | None = None,
) -> Explainer | None:
    if not any(outcome.blocks for outcome in outcomes):
        return None
    ordered = sorted(outcomes, key=lambda o: o.spec.order)
    sections = [_section(outcome, titles, order) for order, outcome in enumerate(ordered, start=1)]
    known = {
        **(lede_sources or {}),
        **{sid: ref for outcome in outcomes for sid, ref in outcome.sources.items()},
    }
    blocks = [
        *([lede] if lede is not None else []),
        *(block for section in sections for block in section.blocks),
    ]
    cited = dict.fromkeys(sid for block in blocks for sid in block.cited_source_ids())
    document = Explainer(
        schema_version=EXPLAINER_SCHEMA_VERSION,
        answer_id=answer_id,
        question=question,
        understood=understood,
        lede=lede,
        sections=sections,
        sources=[SourceRef.model_validate(known[source_id]) for source_id in cited],
        follow_ups=list(follow_ups),
        created_at=datetime.now(UTC),
    )
    return ledgered_explainer(document, known)


def _section(outcome: SectionOutcome, titles: Mapping[str, str], order: int) -> ExplainerSection:
    spec = outcome.spec
    return ExplainerSection.model_validate(
        {
            "id": spec.id,
            "discipline": spec.discipline,
            **shown_title(spec, titles),
            "order": order,
            "state": "READY" if outcome.blocks else "EMPTY",
            "blocks": [block.model_dump(mode="json", by_alias=True) for block in outcome.blocks],
            "searched": None if outcome.blocks else outcome.searched,
        }
    )
