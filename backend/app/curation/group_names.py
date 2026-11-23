from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.research.named_groups import NAMED_GROUP_KINDS, group_name_key
from app.research.structure_proposals import GroupNameItem
from app.research.structure_proposals_values import stated_check

from .dossier import Dossier
from .entities import Community
from .parts import CitedQuote, Source

__all__ = ["StatedGroupName", "stated_group_names"]


@dataclass(frozen=True)
class StatedGroupName:
    name: str
    kind: str
    source: Source
    quote: CitedQuote


def stated_group_names(dossier: Dossier) -> list[StatedGroupName]:
    sources = {source.id: source for source in dossier.sources}
    quotes = {claim.id: claim.quotes for claim in dossier.claims}
    found: dict[str, StatedGroupName] = {}
    for group in dossier.communities:
        if group.kind not in NAMED_GROUP_KINDS:
            continue
        for name in _names(group):
            stated = _stated(name, group, quotes, sources)
            if stated is not None:
                found.setdefault(group_name_key(name), stated)
    return list(found.values())


def _names(group: Community) -> list[str]:
    return list(dict.fromkeys(name.strip() for name in (group.name, *group.local_names) if name.strip()))


def _stated(
    name: str,
    group: Community,
    quotes: Mapping[str, Sequence[CitedQuote]],
    sources: Mapping[str, Source],
) -> StatedGroupName | None:
    item = GroupNameItem(name=name, group_kind=group.kind)
    cited = (quote for claim_id in group.claim_ids for quote in quotes.get(claim_id, ()))
    stating = next((quote for quote in cited if stated_check(item, [quote.quote]).passed), None)
    if stating is None or stating.source_id not in sources:
        return None
    return StatedGroupName(name, group.kind, sources[stating.source_id], stating)
