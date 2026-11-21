from __future__ import annotations

import itertools
import re
import uuid
from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Annotated, Literal

from pydantic import Field

from app.models.enums import DISCIPLINES

from .base import ContractModel
from .composition import HEADING_MAX_CHARS, StageOption
from .depth import depth_policy
from .explainer import SECTION_ID_PATTERN
from .planning import PlanRequest, RetrievalPlan
from .question_cues import HOW_IT_WORKS_FILLERS, HOW_IT_WORKS_SUBJECTS, HOW_IT_WORKS_VERBS, QUESTION_CUES
from .quotes import content_stem, content_stems
from .vocabulary import Discipline

__all__ = [
    "ANSWER_PLANS_SCHEMA_VERSION",
    "ANY_CRAFT_NAME",
    "DISCIPLINE_FIELDS",
    "DISCIPLINE_TITLES",
    "FACET_LABELS",
    "FALLBACK_DISCIPLINE",
    "FALLBACK_HEADINGS",
    "GENERIC_STAGE_WORDS",
    "LADDER_DISCIPLINE",
    "AnswerPlans",
    "SectionPlan",
    "SectionSpec",
    "answer_fields",
    "asked_disciplines",
    "block_id",
    "fallback_heading",
    "is_facet_label",
    "named_stage_ids",
    "question_fields",
    "question_order",
    "section_specs",
]

ANSWER_PLANS_SCHEMA_VERSION = 1
FALLBACK_DISCIPLINE = "OVERVIEW"
LADDER_DISCIPLINE = "PROCESS"
ANY_CRAFT_NAME = "the craft"
DISCIPLINE_TITLES: Mapping[str, str] = MappingProxyType(
    {
        "OVERVIEW": "What it is",
        "PROCESS": "How it is made",
        "CHEMISTRY": "The chemistry",
        "PHYSICS": "The physics",
        "MATERIALS": "Materials",
        "GEOGRAPHY": "Geography and water",
        "GEOLOGY": "Geology and soil",
        "CLIMATE": "Climate",
        "ECOLOGY": "Ecology",
        "BOTANY": "Dye and fibre plants",
        "HISTORY": "History",
        "ECONOMICS": "Economics",
        "DESIGN": "Design",
        "HEALTH": "Health and safety",
        "SOCIETY": "Communities and livelihoods",
        "POLICY": "GI, law and schemes",
    }
)
DISCIPLINE_FIELDS: Mapping[str, str] = MappingProxyType(
    {
        "OVERVIEW": "what the craft is, where and by whom it is practised",
        "PROCESS": "how the craft is made, stage by stage",
        "CHEMISTRY": "chemistry",
        "PHYSICS": "physics",
        "MATERIALS": "materials science",
        "GEOGRAPHY": "geography and water",
        "GEOLOGY": "geology and soil",
        "CLIMATE": "climate",
        "ECOLOGY": "ecology",
        "BOTANY": "botany of dye and fibre plants",
        "HISTORY": "history",
        "ECONOMICS": "economics and markets",
        "DESIGN": "design and art history",
        "HEALTH": "health, toxicology and safe handling",
        "SOCIETY": "the communities, families and livelihoods of the craft",
        "POLICY": "Geographical Indication, law and public schemes",
    }
)
FALLBACK_HEADINGS: Mapping[str, str] = MappingProxyType(
    {
        "OVERVIEW": "What {craft} is",
        "PROCESS": "How {craft} is made",
        "CHEMISTRY": "The chemistry behind {craft}",
        "PHYSICS": "The physics behind {craft}",
        "MATERIALS": "What {craft} is made from",
        "GEOGRAPHY": "The land and water behind {craft}",
        "GEOLOGY": "The soil and stone behind {craft}",
        "CLIMATE": "The weather {craft} works with",
        "ECOLOGY": "Where {craft} meets its surroundings",
        "BOTANY": "The plants behind {craft}",
        "HISTORY": "Where {craft} comes from",
        "ECONOMICS": "Who makes a living from {craft}",
        "DESIGN": "The patterns of {craft}",
        "HEALTH": "Working safely in {craft}",
        "SOCIETY": "The people who keep {craft} alive",
        "POLICY": "How the law protects {craft}",
    }
)
LABEL_WORD = re.compile(r"[^\W_]+")
FACET_LABELS = frozenset(
    " ".join(LABEL_WORD.findall(label.casefold()))
    for label in (
        *DISCIPLINE_TITLES.values(),
        *DISCIPLINE_FIELDS.values(),
        *(discipline.replace("_", " ") for discipline in DISCIPLINES),
        *(f"the {discipline}" for discipline in DISCIPLINES),
        "botany",
        "health",
        "process",
        "overview",
    )
)
QUESTION_WORD = re.compile(r"[^\s\"'“”‘’.,;:!?()\[\]{}।॥/\\-]+")

STAGE_SPAN = re.compile(r"\bfrom\b.+\b(to|till|until|through|into)\b", re.IGNORECASE)
GENERIC_STAGE_WORDS = (
    "make",
    "made",
    "makes",
    "making",
    "stage",
    "stages",
    "step",
    "steps",
    "process",
    "processes",
    "technique",
    "techniques",
    "craft",
    "work",
    "working",
    "first",
    "last",
    "final",
)

SectionId = Annotated[str, Field(pattern=SECTION_ID_PATTERN)]


class SectionSpec(ContractModel):
    id: SectionId
    discipline: Discipline
    title: str = Field(min_length=1, max_length=HEADING_MAX_CHARS)
    order: int = Field(ge=1)


class SectionPlan(ContractModel):
    section_id: SectionId
    discipline: Discipline
    plan: RetrievalPlan


class AnswerPlans(ContractModel):
    schema_version: Literal[1] = ANSWER_PLANS_SCHEMA_VERSION
    sections: list[SectionPlan]


def section_specs(
    disciplines: Sequence[str], depth: str, *, question: str = "", craft_name: str | None = None
) -> list[SectionSpec]:
    known = [d for d in dict.fromkeys(disciplines) if d in DISCIPLINES]
    asked = asked_disciplines(known, question, craft_name)
    kept = [*asked, *(d for d in known if d not in asked)][: depth_policy(depth).max_sections]
    ordered = question_order([d for d in known if d in kept] or [FALLBACK_DISCIPLINE], question, craft_name)
    return [
        SectionSpec(
            id=f"s{order}", discipline=discipline, title=fallback_heading(discipline, craft_name), order=order
        )
        for order, discipline in enumerate(ordered, start=1)
    ]


def answer_fields(asked: Sequence[str], depth: str, held: Sequence[str] = ()) -> list[str]:
    fields = [discipline for discipline in dict.fromkeys(asked) if discipline in DISCIPLINES]
    floor = depth_policy(depth).min_sections
    for discipline in held:
        if len(fields) >= floor:
            break
        if discipline in DISCIPLINES and discipline not in fields:
            fields.append(discipline)
    return fields or [FALLBACK_DISCIPLINE]


def question_fields(question: str, craft_name: str | None = None) -> list[str]:
    return asked_disciplines(DISCIPLINES, question, craft_name)


def question_order(disciplines: Sequence[str], question: str, craft_name: str | None = None) -> list[str]:
    asked = asked_disciplines(disciplines, question, craft_name)
    ordered = [*asked, *(discipline for discipline in disciplines if discipline not in asked)]
    if LADDER_DISCIPLINE in asked or LADDER_DISCIPLINE not in ordered:
        return ordered
    return [*(discipline for discipline in ordered if discipline != LADDER_DISCIPLINE), LADDER_DISCIPLINE]


def asked_disciplines(disciplines: Sequence[str], question: str, craft_name: str | None = None) -> list[str]:
    words = _words(question) - _words(craft_name or "")
    works = _asks_how_it_works(question, craft_name)
    return [
        discipline
        for discipline in disciplines
        if _cued(QUESTION_CUES.get(discipline, ()), words) or (works and discipline == LADDER_DISCIPLINE)
    ]


def fallback_heading(discipline: str, craft_name: str | None) -> str:
    heading = FALLBACK_HEADINGS[discipline].format(craft=craft_name or ANY_CRAFT_NAME)
    if len(heading) > HEADING_MAX_CHARS:
        heading = FALLBACK_HEADINGS[discipline].format(craft=ANY_CRAFT_NAME)
    return heading[0].upper() + heading[1:]


def named_stage_ids(
    request: PlanRequest, stages: Sequence[StageOption], chosen: Sequence[uuid.UUID] = ()
) -> list[uuid.UUID]:
    asked = request.english_question or request.question
    craft_name = request.craft.name if request.craft else ""
    process = LADDER_DISCIPLINE in asked_disciplines([LADDER_DISCIPLINE], asked, craft_name)
    named = _named_positions(asked, stages, craft_name) if process else []
    if len(named) > 1 and STAGE_SPAN.search(asked):
        named = list(range(named[0], named[-1] + 1))
    wanted = {*chosen, *(stages[n].id for n in named)}
    ordered = [stage.id for stage in stages if stage.id in wanted]
    return [*ordered, *(stage_id for stage_id in dict.fromkeys(chosen) if stage_id not in ordered)]


def is_facet_label(heading: str) -> bool:
    return " ".join(LABEL_WORD.findall(heading.casefold())) in FACET_LABELS


def block_id(section_id: str, ordinal: int) -> str:
    return f"{section_id}.b{ordinal}"


def _named_positions(asked: str, stages: Sequence[StageOption], craft_name: str) -> list[int]:
    ignored = content_stems(craft_name) | {content_stem(word) for word in GENERIC_STAGE_WORDS}
    words = content_stems(asked) - ignored
    return [n for n, stage in enumerate(stages) if (content_stems(stage.name) - ignored) & words]


def _words(text: str) -> set[str]:
    return set(QUESTION_WORD.findall(text.casefold()))


def _asks_how_it_works(question: str, craft_name: str | None) -> bool:
    words = QUESTION_WORD.findall(question.casefold())
    named = HOW_IT_WORKS_SUBJECTS | HOW_IT_WORKS_FILLERS | _words(craft_name or "")
    for start in (n for n, word in enumerate(words) if word == "how"):
        subject = list(itertools.takewhile(named.__contains__, words[start + 1 :]))
        rest = words[start + 1 + len(subject) :]
        if rest and rest[0] in HOW_IT_WORKS_VERBS and set(subject) - HOW_IT_WORKS_FILLERS:
            return True
    return False


def _cued(cues: Sequence[str], words: set[str]) -> bool:
    for cue in cues:
        if cue.endswith("*"):
            if any(word.startswith(cue[:-1]) for word in words):
                return True
        elif cue in words:
            return True
    return False
