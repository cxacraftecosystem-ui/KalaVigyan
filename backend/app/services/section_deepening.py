from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from app.research.block_identity import block_keys, repeats_shown
from app.research.blocks import BlockBase
from app.research.explainer import BLOCK_PHASES, BUILT_BLOCK_KINDS
from app.research.explainer_versions import IMAGES_KIND

from .section_blocks import KeptSentence

__all__ = ["LADDER_KIND", "NEW_SECTION", "ONCE_PER_DEEPENING", "Deepening", "shown_deepening"]

LADDER_KIND = "process_ladder"
COMPOSED_PHASE = "A"
ONCE_PER_DEEPENING = frozenset(
    {IMAGES_KIND, LADDER_KIND, *(kind for kind in BUILT_BLOCK_KINDS if BLOCK_PHASES[kind] != COMPOSED_PHASE)}
)


@dataclass(frozen=True)
class Deepening:
    first_block: int = 1
    kinds: frozenset[str] = frozenset()
    claims: frozenset[uuid.UUID] = frozenset()
    keys: frozenset[str] = frozenset()

    def number(self, ordinal: int) -> int:
        return self.first_block + ordinal - 1

    def shows(self, kind: str) -> bool:
        return kind in self.kinds

    @property
    def adds_pictures(self) -> bool:
        return not self.shows(IMAGES_KIND)

    def repeats(self, block: BlockBase) -> bool:
        if block_keys(block) is not None:
            return repeats_shown(block, self.keys)
        return block.kind in ONCE_PER_DEEPENING and self.shows(block.kind)

    def unshown(self, sentences: Sequence[KeptSentence]) -> list[KeptSentence]:
        return [sentence for sentence in sentences if not self._shown(sentence)]

    def _shown(self, sentence: KeptSentence) -> bool:
        claims = set(sentence.claim_ids)
        return not sentence.open_question and bool(claims) and claims <= self.claims


def shown_deepening(
    blocks: Iterable[BlockBase], *, first_block: int, claims: frozenset[uuid.UUID]
) -> Deepening:
    kinds: set[str] = set()
    keys: set[str] = set()
    for block in blocks:
        found = block_keys(block)
        if found is None:
            kinds.add(block.kind)
        else:
            keys.update(found)
    return Deepening(first_block=first_block, kinds=frozenset(kinds), claims=claims, keys=frozenset(keys))


NEW_SECTION = Deepening()
