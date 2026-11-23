from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from app.research.blocks import BlockBase
from app.research.composition import HEADING_MAX_CHARS
from app.research.quotes import content_stems
from app.research.sections import SectionSpec, is_facet_label

from .answer_events import CitedClaims
from .answer_translation import AnswerTranslation, Segment, translate_segments
from .explainer_events import ExplainerStream
from .stated_names import unstated_names

__all__ = [
    "Headed",
    "HeadingClaim",
    "WrittenSection",
    "composed_heading",
    "headed_specs",
    "heading_supports",
    "shown_heading",
]

logger = logging.getLogger(__name__)

HeadingClaim = Callable[[str, str], bool]


class WrittenSection(Protocol):
    @property
    def blocks(self) -> Sequence[BlockBase]: ...

    @property
    def cited(self) -> CitedClaims: ...


@dataclass(frozen=True)
class Headed:
    spec: SectionSpec
    shown: str | None = None


def heading_supports(blocks: Sequence[BlockBase], cited: CitedClaims) -> list[str]:
    sentences = [sentence for block in blocks for sentence in block.cited_sentences()]
    claims = {citation.claim_id for sentence in sentences for citation in sentence.citations}
    return [
        *(sentence.original or sentence.text for sentence in sentences),
        *(view.text for claim_id, view in cited.views.items() if str(claim_id) in claims),
        *(citation.quote for sentence in sentences for citation in sentence.citations if citation.quote),
    ]


def shown_heading(heading: str | None, supports: Sequence[str]) -> str | None:
    if heading is None or not supports:
        return None
    problem = _heading_problem(heading, supports)
    if problem is not None:
        logger.warning("a composed heading %s; the section keeps its own", problem)
        return None
    return heading


async def headed_specs(
    proposed: Mapping[str, str],
    shown: Sequence[tuple[SectionSpec, Sequence[str]]],
    *,
    language: str,
    translation: AnswerTranslation,
    claim: HeadingClaim,
) -> list[Headed]:
    accepted = {
        spec.id: heading
        for spec, supports in shown
        if (heading := shown_heading(proposed.get(spec.id), supports)) is not None and claim(spec.id, heading)
    }
    segments = [Segment(f"heading:{section_id}", heading) for section_id, heading in accepted.items()]
    found = await translate_segments(
        segments, language=language, translation=translation, longest=HEADING_MAX_CHARS
    )
    return [_headed(spec, accepted.get(spec.id), found.get(f"heading:{spec.id}")) for spec, _ in shown]


async def composed_heading(
    spec: SectionSpec,
    written: WrittenSection,
    proposed: str | None,
    stream: ExplainerStream,
    translation: AnswerTranslation,
) -> Headed:
    if proposed is None or not written.blocks:
        return Headed(spec)
    supports = heading_supports(written.blocks, written.cited)
    proposals = {spec.id: proposed}
    (headed,) = await headed_specs(
        proposals,
        [(spec, supports)],
        language=stream.language,
        translation=translation,
        claim=stream.claim_heading,
    )
    if headed.shown is not None:
        original = headed.spec.title if headed.shown != headed.spec.title else None
        await stream.section_heading(spec.id, title=headed.shown, original=original)
    return headed


def _headed(spec: SectionSpec, heading: str | None, shown: str | None) -> Headed:
    if heading is None:
        return Headed(spec)
    return Headed(spec.model_copy(update={"title": heading}), shown or heading)


def _heading_problem(heading: str, supports: Sequence[str]) -> str | None:
    if is_facet_label(heading):
        return "names a field"
    unstated = unstated_names(heading, supports)
    if unstated:
        return f"names {', '.join(unstated)}, which its section does not state"
    if not content_stems(heading) & {stem for support in supports for stem in content_stems(support)}:
        return "shares no word with its section"
    return None
