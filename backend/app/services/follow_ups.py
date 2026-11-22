from __future__ import annotations

import itertools
import re
import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType

from app.composer.candidates import research_summary
from app.research.composition import FOLLOW_UPS_MAX
from app.research.explainer import Explainer, ExplainerSection, Understood, explainer_blocks
from app.research.explainer_versions import (
    BuildsOnEvent,
    ExplainerVersionDocument,
    SectionPlace,
    VersionMark,
    block_number,
)
from app.research.research_summary import not_enough_evidence_message
from app.research.sections import SectionSpec, fallback_heading, section_specs
from app.research.understanding import Understanding

from .answer_lede import Opening
from .answer_translation import AnswerTranslation, Segment, translate_segments
from .explainer_events import ExplainerStream
from .section_context import SectionOutcome
from .section_deepening import Deepening
from .version_merge import merged_version

__all__ = [
    "LEFT_OPEN_QUESTIONS",
    "AnswerLayout",
    "FollowUp",
    "StoredAnswer",
    "answer_layout",
    "closed_answer",
    "left_open",
    "left_open_follow_ups",
    "understood_for",
]

SECTION_NUMBER = re.compile(r"^s(?P<number>\d+)$")
QUESTION_KEY = re.compile(r"[^\W_]+")
LEFT_OPEN_QUESTIONS: Mapping[str, str] = MappingProxyType(
    {
        "OVERVIEW": "Who practises {craft} today, and where?",
        "PROCESS": "What happens at each stage of {craft}?",
        "CHEMISTRY": "What chemistry is at work in {craft}?",
        "PHYSICS": "What physics is at work in {craft}?",
        "MATERIALS": "Which materials does {craft} depend on?",
        "GEOGRAPHY": "How do land and water shape {craft}?",
        "GEOLOGY": "How do soil and stone shape {craft}?",
        "CLIMATE": "How does the weather shape {craft}?",
        "ECOLOGY": "What does {craft} take from its surroundings?",
        "BOTANY": "Which plants does {craft} depend on?",
        "HISTORY": "Where does {craft} come from?",
        "ECONOMICS": "Who makes a living from {craft}, and how?",
        "DESIGN": "What do the patterns of {craft} mean?",
        "HEALTH": "How do artisans of {craft} work safely?",
        "SOCIETY": "Which communities practise {craft}, and how does it support them?",
        "POLICY": "Which laws, schemes and GI rules protect {craft}?",
    }
)


@dataclass(frozen=True)
class FollowUp:
    base: ExplainerVersionDocument
    facets: tuple[str, ...] = ()

    @property
    def explainer(self) -> Explainer:
        return self.base.explainer

    @property
    def understood(self) -> Understood:
        return self.base.explainer.understood

    @property
    def craft_slug(self) -> str | None:
        crafts = self.understood.crafts
        return crafts[0].slug if crafts else None

    def event(self) -> BuildsOnEvent:
        return BuildsOnEvent(
            explainer_id=self.base.mark.explainer_id,
            version=self.base.mark.version,
            sections=[
                SectionPlace(id=section.id, order=section.order) for section in self.explainer.sections
            ],
        )


@dataclass(frozen=True)
class StoredAnswer:
    explainer: Explainer | None
    claim_ids: tuple[uuid.UUID, ...]
    version: VersionMark | None = None


@dataclass(frozen=True)
class AnswerLayout:
    specs: tuple[SectionSpec, ...]
    titles: Mapping[str, str] = field(default_factory=dict)
    deepening: Mapping[str, Deepening] = field(default_factory=dict)
    follow_up: FollowUp | None = None

    @property
    def untitled(self) -> list[SectionSpec]:
        return [spec for spec in self.specs if spec.id not in self.titles]

    @property
    def reusable(self) -> list[SectionSpec]:
        return [spec for spec in self.specs if spec.id not in self.deepening]

    def keeps_pieces_of(self, spec: SectionSpec) -> bool:
        return spec.id not in self.deepening

    def understood(self, understanding: Understanding) -> Understood:
        return understood_for(understanding, self.follow_up)

    def asked(self, understanding: Understanding) -> tuple[str, ...]:
        if self.follow_up is not None and self.follow_up.facets:
            return self.follow_up.facets
        return tuple(understanding.asked)

    def stored(self, document: Explainer | None, claim_ids: Iterable[uuid.UUID]) -> StoredAnswer:
        if self.follow_up is None or document is None:
            return StoredAnswer(document, tuple(claim_ids))
        version = merged_version(self.follow_up.base, document)
        cited = [uuid.UUID(c.claim_id) for b in explainer_blocks(version.explainer) for c in b.citations()]
        return StoredAnswer(version.explainer, tuple(dict.fromkeys([*cited, *claim_ids])), version.mark)


def understood_for(understanding: Understanding, follow_up: FollowUp | None) -> Understood:
    return understanding.understood() if follow_up is None else follow_up.understood


def answer_layout(
    understanding: Understanding, follow_up: FollowUp | None, *, question: str = ""
) -> AnswerLayout:
    asked = follow_up.facets if follow_up is not None and follow_up.facets else understanding.disciplines
    craft = understanding.craft.name if understanding.craft else None
    specs = section_specs(asked, understanding.depth, question=question, craft_name=craft)
    if follow_up is None:
        return AnswerLayout(specs=tuple(specs))
    return _follow_up_layout(follow_up, [spec.discipline for spec in specs], craft)


def left_open(
    question: str, understanding: Understanding, outcomes: Sequence[SectionOutcome], opened: Opening
) -> list[str]:
    shown = {outcome.spec.discipline for outcome in outcomes if outcome.blocks}
    unshown = [discipline for discipline in understanding.disciplines if discipline not in shown]
    offered = [*opened.follow_ups, *(item for outcome in outcomes for item in outcome.follow_ups)]
    craft = understanding.craft.name if understanding.craft else None
    return left_open_follow_ups(opened.asked(question), offered, unshown, craft)


def left_open_follow_ups(
    asked: tuple[str, ...], offered: Sequence[str], unshown: Sequence[str], craft_name: str | None
) -> list[str]:
    facets = [LEFT_OPEN_QUESTIONS[d].format(craft=craft_name) for d in unshown if craft_name is not None]
    questions = {_question_key(form) for form in asked}
    chosen: dict[str, str] = {}
    for item in [*offered, *facets]:
        key = _question_key(item)
        if key and key not in questions and key not in chosen:
            chosen[key] = item
    return list(chosen.values())[:FOLLOW_UPS_MAX]


async def closed_answer(
    outcomes: Sequence[SectionOutcome],
    offered: Sequence[str],
    stream: ExplainerStream,
    translation: AnswerTranslation,
) -> list[str]:
    if any(outcome.blocks for outcome in outcomes):
        english = list(offered)[:FOLLOW_UPS_MAX]
        segments = [Segment(f"follow-up:{n}", item) for n, item in enumerate(english)]
        found = await translate_segments(segments, language=stream.language, translation=translation)
        follow_ups = [found.get(f"follow-up:{n}", item) for n, item in enumerate(english)]
        await stream.emit("follow_ups", {"items": follow_ups})
        return follow_ups
    failures = [outcome.failure for outcome in outcomes if outcome.failure is not None]
    if len(failures) == len(outcomes):
        raise failures[0]
    packs = [pack for outcome in outcomes for pack in outcome.packs]
    message = not_enough_evidence_message(research_summary(*packs))
    await stream.emit("not_enough_evidence", {"message": message})
    return []


def _question_key(text: str) -> str:
    return " ".join(QUESTION_KEY.findall(text.casefold()))


def _follow_up_layout(follow_up: FollowUp, disciplines: Sequence[str], craft: str | None) -> AnswerLayout:
    explainer = follow_up.explainer
    by_field = {section.discipline: section for section in explainer.sections}
    shown = frozenset(uuid.UUID(c.claim_id) for b in explainer_blocks(explainer) for c in b.citations())
    numbers = itertools.count(_last_section_number(explainer.sections) + 1)
    orders = itertools.count(len(explainer.sections) + 1)
    specs: list[SectionSpec] = []
    titles: dict[str, str] = {}
    deepening: dict[str, Deepening] = {}
    for discipline in disciplines:
        section = by_field.get(discipline)
        if section is None:
            title = fallback_heading(discipline, craft)
            specs.append(
                SectionSpec(id=f"s{next(numbers)}", discipline=discipline, title=title, order=next(orders))
            )
            continue
        specs.append(_deepened_spec(section))
        titles[section.id] = section.title
        deepening[section.id] = _deepening(section, shown)
    ordered = tuple(sorted(specs, key=lambda spec: spec.order))
    return AnswerLayout(specs=ordered, titles=titles, deepening=deepening, follow_up=follow_up)


def _deepened_spec(section: ExplainerSection) -> SectionSpec:
    return SectionSpec(
        id=section.id,
        discipline=section.discipline,
        title=section.original or section.title,
        order=section.order,
    )


def _deepening(section: ExplainerSection, shown: frozenset[uuid.UUID]) -> Deepening:
    last = max((block_number(block.id, section.id) for block in section.blocks), default=0)
    return Deepening(
        first_block=last + 1, kinds=frozenset(block.kind for block in section.blocks), claims=shown
    )


def _last_section_number(sections: Sequence[ExplainerSection]) -> int:
    found = (SECTION_NUMBER.match(section.id) for section in sections)
    return max((int(match.group("number")) for match in found if match), default=0)
