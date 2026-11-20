from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import Any

from pydantic import ValidationError

from app.curation.entities import After, Reaction as DossierReaction, Species
from app.curation.limits import SENTENCE_MAX_CHARS
from app.curation.parts import LANGUAGE_PATTERN, Conflict, OpenQuestion
from app.curation.records import GiRecord, NativeName, Term
from app.curation.vocabulary import WHY_DISCIPLINES
from app.research.structure_proposals import (
    CONFLICT,
    GI_RECORD,
    GLOSSARY_TERM,
    NATIVE_NAME,
    OPEN_QUESTION,
    REACTION,
    STAGE_AFTER,
    STAGE_WHY,
    ConflictItem,
    GiRecordItem,
    GlossaryTermItem,
    NativeNameItem,
    OpenQuestionItem,
    ReactionItem,
    StageAfterItem,
    StructureProposal,
)

__all__ = ["PLACEHOLDER_CLAIM", "dossier_problem"]

PLACEHOLDER_CLAIM = "C001"
OTHER_CLAIM = "C002"
PLACEHOLDER_ENTRY = {REACTION: "R01", GLOSSARY_TERM: "W01", OPEN_QUESTION: "O01"}


def dossier_problem(proposal: StructureProposal) -> str | None:
    problem = _statement_problem(proposal) or _source_problem(proposal)
    if problem is not None:
        return problem
    build = _PARTS.get(proposal.item.kind)
    if build is None:
        return None
    try:
        build(proposal.item)
    except ValidationError as error:
        first = error.errors()[0]
        return f"the {proposal.item.kind.lower().replace('_', ' ')} does not fit its dossier: {first['msg']}"
    return None


def _statement_problem(proposal: StructureProposal) -> str | None:
    if proposal.statement is not None and len(proposal.statement) > SENTENCE_MAX_CHARS:
        return f"the statement becomes a sentence of the dossier, so it is at most {SENTENCE_MAX_CHARS} characters"
    if proposal.item.kind == STAGE_WHY and proposal.field not in WHY_DISCIPLINES:
        return f"a stage's why is filed under one of {', '.join(WHY_DISCIPLINES)}"
    return None


def _source_problem(proposal: StructureProposal) -> str | None:
    for source in proposal.sources:
        if not re.fullmatch(LANGUAGE_PATTERN, source.language):
            return f"{source.language} is not a language tag such as en, hi or gu-Gujr"
    return None


def _after(item: StageAfterItem) -> object:
    return After(text=item.text, colours=list(item.colours), claim_id=PLACEHOLDER_CLAIM)


def _native_name(item: NativeNameItem) -> object:
    return NativeName(text=item.text, language=item.language, script=item.script, claim_id=PLACEHOLDER_CLAIM)


def _reaction(item: ReactionItem) -> object:
    return DossierReaction(
        id=PLACEHOLDER_ENTRY[REACTION],
        kind=item.reaction_kind,
        stage_id=item.stage_key,
        reactants=[Species(name=s.name, formula=s.formula) for s in item.reactants],
        products=[Species(name=s.name, formula=s.formula) for s in item.products],
        claim_ids=[PLACEHOLDER_CLAIM],
    )


def _term(item: GlossaryTermItem) -> object:
    return Term(
        id=PLACEHOLDER_ENTRY[GLOSSARY_TERM],
        term=item.term,
        meaning=item.meaning,
        language=item.language,
        script=item.script,
        claim_ids=[PLACEHOLDER_CLAIM],
    )


def _conflict(item: ConflictItem) -> object:
    return Conflict(claim_ids=[PLACEHOLDER_CLAIM, OTHER_CLAIM], about=item.about)


def _question(item: OpenQuestionItem) -> object:
    return OpenQuestion(
        id=PLACEHOLDER_ENTRY[OPEN_QUESTION],
        question=item.question,
        settled_by=item.settled_by,
        claim_ids=[PLACEHOLDER_CLAIM],
    )


def _gi(item: GiRecordItem) -> object:
    fields = item.model_dump(exclude={"kind"})
    return GiRecord.model_validate({**fields, "claimIds": [PLACEHOLDER_CLAIM]})


_PARTS: Mapping[str, Callable[[Any], object]] = MappingProxyType(
    {
        STAGE_AFTER: _after,
        NATIVE_NAME: _native_name,
        REACTION: _reaction,
        GLOSSARY_TERM: _term,
        CONFLICT: _conflict,
        OPEN_QUESTION: _question,
        GI_RECORD: _gi,
    }
)
