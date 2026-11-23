from __future__ import annotations

from collections.abc import Iterable, Sequence

from .blocks import BlockBase, ImageItem, ImagesBlock

__all__ = ["cited_claims", "illustrates_uncited", "pictures_of_cited"]


def cited_claims(blocks: Iterable[BlockBase]) -> set[str]:
    return set().union(*(block.cited_claim_ids() for block in blocks))


def illustrates_uncited(blocks: Sequence[BlockBase]) -> bool:
    cited = cited_claims(blocks)
    return any(not block.illustrated_claim_ids() <= cited for block in blocks)


def pictures_of_cited(blocks: Sequence[BlockBase]) -> list[BlockBase]:
    cited = cited_claims(blocks)
    kept: list[BlockBase] = []
    for block in blocks:
        shown = _pictured(block, cited) if isinstance(block, ImagesBlock) else block
        if shown is not None:
            kept.append(shown)
    return kept


def _pictured(block: ImagesBlock, cited: set[str]) -> ImagesBlock | None:
    items = [item for item in (_illustrating(item, cited) for item in block.items) if item is not None]
    if not items:
        return None
    return block if items == block.items else block.model_copy(update={"items": items})


def _illustrating(item: ImageItem, cited: set[str]) -> ImageItem | None:
    claims = [claim for claim in item.claim_ids if str(claim) in cited]
    if not claims:
        return None
    return item if claims == item.claim_ids else item.model_copy(update={"claim_ids": claims})
