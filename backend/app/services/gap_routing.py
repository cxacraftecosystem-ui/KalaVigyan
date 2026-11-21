from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from app.research.blocks import ProseBlock
from app.research.explainer import BLOCK_MODELS, Block
from app.research.gap_admissions import admits_gap

from .claim_ledger import LADDER_KIND, RESTATING_KINDS
from .ledger_payloads import Payload, kept_sentences, leveled_stages

__all__ = ["OPEN_QUESTION_FIELDS", "RoutedGaps", "gap_block", "open_question", "routed_gaps"]

logger = logging.getLogger(__name__)

OPEN_QUESTION_FIELDS = ("id", "text", "level", "citations", "translated", "original")
GAP_BLOCK_SUFFIX = "gaps"


@dataclass(frozen=True)
class RoutedGaps:
    blocks: tuple[Block, ...] = ()
    gaps: tuple[Payload, ...] = ()


def routed_gaps(blocks: Sequence[Block]) -> RoutedGaps:
    kept: list[Block] = []
    gaps: list[Payload] = []
    for block in blocks:
        found: list[Payload] = []
        stated = _without_gaps(block, found)
        gaps += found
        if stated is not None:
            kept.append(stated)
    return RoutedGaps(tuple(kept), tuple(gaps))


def gap_block(section_id: str, gaps: Sequence[Payload]) -> ProseBlock | None:
    block_id = f"{section_id}.{GAP_BLOCK_SUFFIX}"
    sentences = [
        {**open_question(gap), "id": f"{block_id}.{n}", "terms": gap.get("terms", [])}
        for n, gap in enumerate(gaps, start=1)
    ]
    try:
        return ProseBlock.model_validate(
            {"id": block_id, "kind": "prose", "version": 1, "reuse": None, "sentences": sentences}
        )
    except ValidationError as refused:
        logger.warning(
            "the gaps of %s cannot be translated as one block: %s", section_id, refused.error_count()
        )
        return None


def open_question(sentence: Mapping[str, Any]) -> Payload:
    return {name: sentence[name] for name in OPEN_QUESTION_FIELDS if name in sentence}


def _without_gaps(block: Block, found: list[Payload]) -> Block | None:
    if not any(admits_gap(sentence.original or sentence.text) for sentence in block.cited_sentences()):
        return block
    spec = RESTATING_KINDS.get(block.kind, BLOCK_MODELS[block.kind].SENTENCES)
    payload = block.model_dump(mode="json", by_alias=True, exclude_unset=True)

    def gap(sentence: Mapping[str, Any]) -> bool:
        if not admits_gap(sentence.get("original") or sentence["text"]):
            return False
        found.append(dict(sentence))
        return True

    kept = kept_sentences(payload, spec, gap)
    if kept is None:
        return None
    if block.kind == LADDER_KIND:
        kept = leveled_stages(kept)
    try:
        return BLOCK_MODELS[block.kind].model_validate(kept)
    except ValidationError as refused:
        logger.warning(
            "block %s is left out once its gap sentences go to the open questions: %s",
            block.id,
            refused.error_count(),
        )
        return None
