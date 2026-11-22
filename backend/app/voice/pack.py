from __future__ import annotations

import time
import uuid
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field

from app.research.crafts import CraftRef
from app.research.quotes import content_stems
from app.research.retrieval import KnowledgeHits
from app.research.vocabulary import LEVEL_ORDER
from app.services.answer_events import CitedClaims
from app.services.knowledge_view import ClaimView

__all__ = [
    "PACKS_HELD",
    "PACK_CANDIDATES",
    "PACK_TTL_SECONDS",
    "VoicePack",
    "VoicePackStore",
    "ranked_claims",
    "searched_claims",
]

PACK_CANDIDATES = 12
PACK_TTL_SECONDS = 600.0
PACKS_HELD = 64
REQUEST_WORDS = "tell explain describe know please something anything more give talk craft crafts"
REQUEST_STEMS = frozenset(content_stems(REQUEST_WORDS))

PackLoader = Callable[[CraftRef, str], Awaitable["VoicePack"]]


@dataclass(frozen=True)
class VoicePack:
    craft: CraftRef
    mode: str
    cited: CitedClaims
    stage_of: Mapping[uuid.UUID, uuid.UUID] = field(default_factory=dict)


def ranked_claims(pack: VoicePack, question: str, *, limit: int = PACK_CANDIDATES) -> list[ClaimView]:
    named = content_stems(f"{pack.craft.name} {pack.craft.slug.replace('-', ' ')}")
    asked = content_stems(question) - named - REQUEST_STEMS
    views = list(pack.cited.views.values())
    if not asked:
        return sorted(views, key=lambda v: (LEVEL_ORDER.get(v.level, 9), v.text))[:limit]
    scored = [(len(asked & content_stems(view.text)) / len(asked), view) for view in views]
    matching = [(score, view) for score, view in scored if score > 0]
    matching.sort(key=lambda pair: (-pair[0], LEVEL_ORDER.get(pair[1].level, 9), pair[1].text))
    return [view for _, view in matching[:limit]]


def searched_claims(
    pack: VoicePack,
    found: KnowledgeHits | None,
    by_words: Sequence[ClaimView],
    *,
    limit: int = PACK_CANDIDATES,
) -> list[ClaimView]:
    searched = [hit.claim_id for hit in found.claims if hit.claim_id in pack.cited.views] if found else []
    ordered = dict.fromkeys([*searched, *(view.id for view in by_words)])
    return [pack.cited.views[claim_id] for claim_id in ordered][:limit]


class VoicePackStore:
    def __init__(self, *, ttl_seconds: float = PACK_TTL_SECONDS, held: int = PACKS_HELD) -> None:
        self._ttl = ttl_seconds
        self._held = held
        self._packs: OrderedDict[tuple[str, str], tuple[float, VoicePack]] = OrderedDict()

    async def get(self, craft: CraftRef, mode: str, load: PackLoader) -> VoicePack:
        key = (craft.slug, mode)
        found = self._packs.get(key)
        now = time.monotonic()
        if found is not None and now - found[0] < self._ttl:
            self._packs.move_to_end(key)
            return found[1]
        pack = await load(craft, mode)
        self._packs[key] = (now, pack)
        self._packs.move_to_end(key)
        while len(self._packs) > self._held:
            self._packs.popitem(last=False)
        return pack
