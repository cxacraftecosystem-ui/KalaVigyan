from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping
from typing import Literal

from pydantic import Field

from app.models.enums import DISCIPLINES

from .base import ContractModel
from .coverage_chapters import field_chapter
from .page_report_rules import (
    DENSE_SENTENCES,
    FAIL,
    JUDGE,
    PASS,
    VERDICTS,
    ReadPage,
    ReportInput,
    checked_rules,
)
from .supplied_sources import cite_key
from .vocabulary import Discipline

__all__ = [
    "CHECKLIST_RULES",
    "LICENCE_CLASSES",
    "PAGE_REPORT_SCHEMA_VERSION",
    "STANDINGS",
    "FieldLine",
    "FigureLine",
    "PageReport",
    "PictureLine",
    "ReportInput",
    "RuleCheck",
    "page_report",
    "picture_licence",
]

PAGE_REPORT_SCHEMA_VERSION = 1
CHECKLIST_RULES = 26
DENSE, THIN, ABSENT = STANDINGS = ("DENSE", "THIN", "ABSENT")
UNGRADED = "UNGRADED"
CONTRIBUTED, AI_ILLUSTRATION, NAMED_IN_CREDIT = LICENCE_CLASSES = (
    "CONTRIBUTED",
    "AI_ILLUSTRATION",
    "NAMED_IN_CREDIT",
)
LICENCE = re.compile(
    r"\b(CC0|CC[ -]BY(?:[ -](?:SA|NC|ND))*(?:[ -]\d\.\d)?|public domain(?: mark)?|PDDL)\b", re.IGNORECASE
)
CONTRIBUTED_CREDIT = "contributed to kalavigyan"
AI_CREDIT = "illustration, made with"
READY = (
    "{passed} rules pass, {failed} fail and {judged} are yours to judge on the private link; fix each failure "
    "and preview again."
)


class RuleCheck(ContractModel):
    rule: int = Field(ge=1, le=CHECKLIST_RULES)
    title: str
    verdict: Literal[*VERDICTS]
    evidence: list[str]


class FieldLine(ContractModel):
    field: Discipline
    chapter: str
    sentences: int = Field(ge=0)
    figures: int = Field(ge=0)
    held: int = Field(ge=0)
    standing: Literal[*STANDINGS]


class FigureLine(ContractModel):
    number: int = Field(ge=1)
    label: str
    kind: str
    title: str
    field: Discipline
    chapter: str
    cited: bool


class PictureLine(ContractModel):
    label: str
    chapter: str
    caption: str
    credit: str
    licence: str


class PageReport(ContractModel):
    schema_version: Literal[1] = PAGE_REPORT_SCHEMA_VERSION
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    judged: int = Field(ge=0)
    rules: list[RuleCheck]
    sentences: int = Field(ge=0)
    lede_sentences: int = Field(ge=0)
    fields: list[FieldLine]
    figures: list[FigureLine]
    figure_kinds: dict[str, int]
    sources: int = Field(ge=0)
    sources_by_grade: dict[str, int]
    supplied_sources: int = Field(ge=0)
    pictures: list[PictureLine]
    pictures_by_licence: dict[str, int]
    message: str


def page_report(given: ReportInput, titles: Mapping[int, str]) -> PageReport:
    page = ReadPage.of(given.document)
    rules = [
        RuleCheck(rule=number, title=titles.get(number, f"Rule {number}"), verdict=verdict, evidence=evidence)
        for number, (verdict, evidence) in checked_rules(given).items()
    ]
    counted = Counter(rule.verdict for rule in rules)
    figures = _figures(page)
    pictures = _pictures(page)
    sources_by_grade, supplied = _sources(given)
    return PageReport(
        passed=counted[PASS],
        failed=counted[FAIL],
        judged=counted[JUDGE],
        rules=rules,
        sentences=len(page.sentences),
        lede_sentences=len(page.lede()),
        fields=_fields(page, given),
        figures=figures,
        figure_kinds=dict(Counter(figure.kind for figure in figures)),
        sources=len(given.document.content.sources),
        sources_by_grade=sources_by_grade,
        supplied_sources=supplied,
        pictures=pictures,
        pictures_by_licence=dict(Counter(picture.licence for picture in pictures)),
        message=READY.format(passed=counted[PASS], failed=counted[FAIL], judged=counted[JUDGE]),
    )


def picture_licence(credit: str) -> str:
    folded = credit.casefold()
    if folded.startswith(AI_CREDIT):
        return AI_ILLUSTRATION
    if CONTRIBUTED_CREDIT in folded:
        return CONTRIBUTED
    found = LICENCE.search(credit)
    if found is None:
        return NAMED_IN_CREDIT
    name = " ".join(found.group(1).split()).upper().replace("CC-BY", "CC BY")
    return "Public domain" if name.startswith("PUBLIC DOMAIN") else name


def _fields(page: ReadPage, given: ReportInput) -> list[FieldLine]:
    shown = page.by_field()
    drawn = Counter(figure.field for figure in page.figures)
    coverage = given.document.coverage
    return [
        FieldLine(
            field=name,
            chapter=field_chapter(name),
            sentences=shown.get(name, 0),
            figures=drawn.get(name, 0),
            held=coverage.count(name).claims if coverage is not None else 0,
            standing=_standing(shown.get(name, 0)),
        )
        for name in DISCIPLINES
    ]


def _standing(sentences: int) -> str:
    if sentences >= DENSE_SENTENCES:
        return DENSE
    return THIN if sentences else ABSENT


def _figures(page: ReadPage) -> list[FigureLine]:
    return [
        FigureLine(
            number=number,
            label=figure.label,
            kind=figure.kind,
            title=figure.title,
            field=figure.field,
            chapter=figure.chapter,
            cited=page.cited(figure.label),
        )
        for number, figure in enumerate(page.figures, start=1)
    ]


def _pictures(page: ReadPage) -> list[PictureLine]:
    lines = []
    for picture in page.pictures:
        _, caption, credit = page.plate(picture.label)
        lines.append(
            PictureLine(
                label=picture.label,
                chapter=picture.chapter,
                caption=caption,
                credit=credit,
                licence=picture_licence(credit),
            )
        )
    return lines


def _sources(given: ReportInput) -> tuple[dict[str, int], int]:
    supplied = {cite_key(url): grade for url, grade in given.supplied.items()}
    grades: Counter[str] = Counter()
    count = 0
    for source in given.document.content.sources.values():
        url = cite_key(source.url) if source.url else None
        held = supplied.get(url) if url is not None else None
        count += int(held is not None)
        grades[source.grade or held or UNGRADED] += 1
    return dict(sorted(grades.items())), count
