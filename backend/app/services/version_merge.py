from __future__ import annotations

import itertools
import logging
import re
from collections.abc import Mapping, Sequence

from pydantic import TypeAdapter, ValidationError

from app.core.errors import InvalidInput
from app.research.blocks import BlockBase
from app.research.citations import SourceRef
from app.research.explainer import (
    EXPLAINER_SCHEMA_VERSION,
    Block,
    Explainer,
    ExplainerSection,
    with_payload_sentences,
)
from app.research.explainer_versions import (
    IMAGES_KIND,
    ExplainerVersionDocument,
    SectionChange,
    VersionMark,
    block_number,
    version_problems,
)
from app.research.sections import block_id

from .explainer_payload import version_document
from .section_deepening import shown_deepening

__all__ = ["last_section_number", "merged_version", "remerged_version"]

logger = logging.getLogger(__name__)

READY = "READY"
SECTION_NUMBER = re.compile(r"^s(?P<number>\d+)$")
BLOCKS = TypeAdapter(Block)


def merged_version(base: ExplainerVersionDocument, follow_up: Explainer) -> ExplainerVersionDocument:
    explainer = base.explainer
    offered = {section.id: section for section in follow_up.sections if section.blocks}
    known = {section.id for section in explainer.sections}
    kept = [_deepened(section, offered.get(section.id)) for section in explainer.sections]
    added = [section for section in follow_up.sections if section.id not in known and section.blocks]
    sections = [*kept, *(_placed(section, len(kept) + n) for n, section in enumerate(added, 1))]
    shown = [
        *([follow_up.lede] if follow_up.lede else []),
        *(b for section in sections for b in section.blocks),
    ]
    merged = Explainer(
        schema_version=EXPLAINER_SCHEMA_VERSION,
        answer_id=follow_up.answer_id,
        question=follow_up.question,
        understood=explainer.understood,
        lede=follow_up.lede,
        sections=sections,
        sources=_cited_sources(shown, [*follow_up.sources, *explainer.sources]),
        follow_ups=list(follow_up.follow_ups or explainer.follow_ups),
        created_at=follow_up.created_at,
    )
    changes = _changes(explainer, offered, added)
    mark = VersionMark(
        explainer_id=base.mark.explainer_id,
        version=base.mark.version + 1,
        answer_id=follow_up.answer_id,
        based_on=base.mark.version,
        question=follow_up.question,
        changes=changes,
        created_at=follow_up.created_at,
    )
    problems = version_problems(explainer, merged, changes)
    if problems:
        raise InvalidInput(
            f"follow-up {follow_up.answer_id} would break version {mark.version} of explainer "
            f"{mark.explainer_id}: {'; '.join(problems)}"
        )
    return version_document(mark, merged)


def remerged_version(
    newer: ExplainerVersionDocument, follow_up: Explainer
) -> ExplainerVersionDocument | None:
    try:
        moved = _moved_onto(newer.explainer, follow_up)
        return None if moved is None else merged_version(newer, moved)
    except (InvalidInput, ValidationError) as refused:
        logger.info(
            "follow-up %s does not fit version %s of explainer %s: %s",
            follow_up.answer_id,
            newer.mark.version,
            newer.mark.explainer_id,
            refused,
        )
        return None


def last_section_number(sections: Sequence[ExplainerSection]) -> int:
    found = (SECTION_NUMBER.match(section.id) for section in sections)
    return max((int(match.group("number")) for match in found if match), default=0)


def _moved_onto(newer: Explainer, follow_up: Explainer) -> Explainer | None:
    by_field = {section.discipline: section for section in newer.sections}
    numbers = itertools.count(last_section_number(newer.sections) + 1)
    moved: list[ExplainerSection] = []
    for section in (section for section in follow_up.sections if section.blocks):
        held = by_field.get(section.discipline)
        placed = _deepening_of(held, section) if held is not None else _added_as(section, f"s{next(numbers)}")
        if placed is not None:
            moved.append(placed)
    if not moved:
        return None
    sections = [_placed(section, order) for order, section in enumerate(moved, 1)]
    shown = [
        *([follow_up.lede] if follow_up.lede else []),
        *(b for section in sections for b in section.blocks),
    ]
    sources = _cited_sources(shown, follow_up.sources)
    return Explainer(**{**dict(follow_up), "sections": sections, "sources": sources})


def _deepening_of(held: ExplainerSection, section: ExplainerSection) -> ExplainerSection | None:
    last = max((block_number(block.id, held.id) for block in held.blocks), default=0)
    shown = shown_deepening(held.blocks, first_block=last + 1, claims=frozenset())
    blocks = [block for block in section.blocks if not shown.repeats(block)]
    if not blocks:
        return None
    placed = [_renumbered(block, block_id(held.id, shown.number(n))) for n, block in enumerate(blocks, 1)]
    return ExplainerSection(**{**dict(held), "state": READY, "searched": None, "blocks": placed})


def _added_as(section: ExplainerSection, section_id: str) -> ExplainerSection:
    placed = [_renumbered(block, block_id(section_id, n)) for n, block in enumerate(section.blocks, 1)]
    return ExplainerSection(**{**dict(section), "id": section_id, "blocks": placed})


def _renumbered(block: Block, new_id: str) -> Block:
    prefix = f"{block.id}."
    payload = with_payload_sentences(
        block.model_dump(mode="json", by_alias=True),
        lambda sentence: {**sentence, "id": _moved_id(sentence["id"], prefix, f"{new_id}.")},
    )
    return BLOCKS.validate_python({**payload, "id": new_id})


def _moved_id(value: str, prefix: str, new_prefix: str) -> str:
    return f"{new_prefix}{value.removeprefix(prefix)}" if value.startswith(prefix) else value


def _deepened(section: ExplainerSection, offered: ExplainerSection | None) -> ExplainerSection:
    if offered is None:
        return section
    own = [block for block in section.blocks if block.kind != IMAGES_KIND]
    pictures = [block for block in section.blocks if block.kind == IMAGES_KIND]
    blocks = [*own, *offered.blocks, *pictures]
    return ExplainerSection(**{**dict(section), "state": READY, "searched": None, "blocks": blocks})


def _placed(section: ExplainerSection, order: int) -> ExplainerSection:
    return ExplainerSection(**{**dict(section), "order": order})


def _cited_sources(blocks: Sequence[BlockBase], known: Sequence[SourceRef]) -> list[SourceRef]:
    by_id = {source.id: source for source in known}
    cited = dict.fromkeys(source_id for block in blocks for source_id in block.cited_source_ids())
    unknown = [source_id for source_id in cited if source_id not in by_id]
    if unknown:
        raise InvalidInput(f"a follow-up cites sources neither version lists: {', '.join(unknown)}")
    return [by_id[source_id] for source_id in cited]


def _changes(
    explainer: Explainer, offered: Mapping[str, ExplainerSection], added: Sequence[ExplainerSection]
) -> list[SectionChange]:
    deepened = [
        SectionChange(
            section_id=section.id,
            change="DEEPENED",
            block_ids=[block.id for block in offered[section.id].blocks],
        )
        for section in explainer.sections
        if section.id in offered
    ]
    return deepened + [
        SectionChange(section_id=section.id, change="ADDED", block_ids=[block.id for block in section.blocks])
        for section in added
    ]
