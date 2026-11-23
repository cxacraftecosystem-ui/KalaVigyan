from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import (
    ColumnElement,
    CompoundSelect,
    Float,
    Select,
    String,
    and_,
    case,
    cast,
    exists,
    func,
    literal,
    or_,
    select,
    union_all,
)
from sqlalchemy.orm import aliased

from app.models import (
    Chunk,
    Claim,
    ClaimSource,
    Concept,
    ConceptEdge,
    CraftCategory,
    CuratedCategoryClaim,
    FieldRecording,
    Source,
    Term,
    TermConcept,
)
from app.research.retrieval import (
    MODE_CLAIM_LEVELS,
    MODE_CLAIM_STATUSES,
    RESTRICTED_SENSITIVITY,
    VISIBLE_SENSITIVITY,
)
from app.research.vocabulary import CONCEPT_TYPE_DISCIPLINES

from .citation_access import HELD_LEFT_OUT, HeldFacts, reader_fact
from .field_scope import field_interview_sources, withheld_field_sources
from .glossary_words import TEXT_SEARCH_CONFIG, any_slot, named_by, slot_query, text_query
from .nearest import ANY_CRAFT, vector_ranking
from .text import tsquery_terms

__all__ = [
    "ANY_CRAFT",
    "ENTITY_NAME_MIN_CHARS",
    "EVERY_CRAFT",
    "LEXICAL_CANDIDATES",
    "NAME_GLOSS",
    "NAME_GLOSS_OPEN",
    "RANKING_DEPTH",
    "TEXT_SEARCH_CONFIG",
    "CraftScope",
    "chunk_conditions",
    "chunk_lexical_ranking",
    "chunk_vector_ranking",
    "cited_from_kinds",
    "claim_conditions",
    "claim_entity_ranking",
    "claim_lexical_ranking",
    "claim_vector_ranking",
    "facet_disciplines",
    "field_condition",
    "field_passages",
    "filed_under",
    "lexical_rank",
    "scope_claims",
    "scope_concepts",
    "text_query",
]

RANKING_DEPTH = 60
LEXICAL_CANDIDATES = 400
ENTITY_NAME_MIN_CHARS = 4
NAME_GLOSS_OPEN = " ("
NAME_GLOSS = r"\(([^)]*)\)"
WORD_BEFORE = r"(?<!\w)"
WORD_AFTER = r"(?:e?s)?(?!\w)"
REGEX_SPECIALS = r"([.^$*+?(){}|\\\[\]])"
REGEX_ESCAPED = r"\\\1"
CONCEPT_SUBJECT = "CONCEPT"


@dataclass(frozen=True)
class CraftScope:
    craft_id: uuid.UUID | None
    sub_category_id: uuid.UUID | None
    category_id: uuid.UUID | None = None
    merged_ids: tuple[uuid.UUID, ...] = ()
    linked_ids: tuple[uuid.UUID, ...] = ()


EVERY_CRAFT = CraftScope(craft_id=None, sub_category_id=None)


def scope_concepts(scope: CraftScope, *, facets: Sequence[str] = ()) -> Select[tuple[uuid.UUID]]:
    visible = Concept.sensitivity == VISIBLE_SENSITIVITY
    owned = [or_(*_owners(scope))] if scope.craft_id is not None else []
    statement = select(Concept.id).where(*owned, visible)
    if facets:
        statement = statement.where(Concept.type.in_(list(facets)))
    return statement


def _owners(scope: CraftScope) -> list[ColumnElement[bool]]:
    owners: list[ColumnElement[bool]] = [Concept.craftId == scope.craft_id]
    if scope.merged_ids:
        owners.append(Concept.craftId.in_(list(scope.merged_ids)))
    if scope.sub_category_id is not None:
        owners.append(and_(Concept.craftId.is_(None), Concept.subCategoryId == scope.sub_category_id))
    if scope.category_id is not None:
        owners.append(_family_science(scope.category_id))
    if scope.linked_ids:
        owners.append(Concept.id.in_(list(scope.linked_ids)))
    return owners


def _family_science(category_id: uuid.UUID) -> ColumnElement[bool]:
    marked = aliased(Claim, name="family_claim")
    curated = (
        select(marked.subjectId)
        .join(CuratedCategoryClaim, CuratedCategoryClaim.claimId == marked.id)
        .where(CuratedCategoryClaim.categoryId == category_id, marked.subjectType == CONCEPT_SUBJECT)
    )
    named = select(func.lower(CraftCategory.name)).where(CraftCategory.id == category_id).scalar_subquery()
    shared = and_(
        Concept.craftId.is_(None), Concept.subCategoryId.is_(None), func.lower(Concept.name) == named
    )
    return or_(Concept.id.in_(curated), shared)


def scope_claims(scope: CraftScope, *, facets: Sequence[str] = ()) -> ColumnElement[bool]:
    concepts = scope_concepts(scope, facets=facets)
    edges = select(ConceptEdge.id).where(
        or_(ConceptEdge.srcId.in_(concepts), ConceptEdge.dstId.in_(concepts))
    )
    typed = or_(
        and_(Claim.subjectType == CONCEPT_SUBJECT, Claim.subjectId.in_(concepts)),
        and_(Claim.subjectType == "EDGE", Claim.subjectId.in_(edges)),
    )
    disciplines = facet_disciplines(facets)
    if not disciplines:
        return typed
    owned = scope_concepts(scope)
    filed = and_(Claim.subjectType == CONCEPT_SUBJECT, Claim.subjectId.in_(owned), filed_under(disciplines))
    return or_(typed, filed)


def facet_disciplines(facets: Sequence[str]) -> list[str]:
    return sorted({CONCEPT_TYPE_DISCIPLINES[facet] for facet in facets if facet in CONCEPT_TYPE_DISCIPLINES})


def field_condition(fields: Sequence[str]) -> ColumnElement[bool]:
    return or_(Claim.field.is_(None), filed_under(fields))


def claim_conditions(
    scope: CraftScope,
    *,
    mode: str,
    facets: Sequence[str] = (),
    fields: Sequence[str] = (),
    held: HeldFacts = HELD_LEFT_OUT,
) -> list[ColumnElement[bool]]:
    conditions = [
        scope_claims(scope, facets=facets),
        Claim.evidenceLevel.in_(MODE_CLAIM_LEVELS[mode]),
        *reader_fact(held, statuses=MODE_CLAIM_STATUSES[mode]),
        *_every_craft(scope),
    ]
    return [*conditions, field_condition(fields)] if fields else conditions


def _every_craft(scope: CraftScope) -> list[ColumnElement[bool]]:
    return [ANY_CRAFT] if scope.craft_id is None else []


def chunk_conditions(
    scope: CraftScope,
    *,
    mode: str,
    facets: Sequence[str] = (),
    fields: Sequence[str] = (),
    acls: Sequence[str],
    kinds: Sequence[str],
) -> list[ColumnElement[bool]]:
    claims = select(Claim.id).where(*claim_conditions(scope, mode=mode, facets=facets, fields=fields))
    sources = select(Source.id).where(
        Source.id.in_(select(ClaimSource.sourceId).where(ClaimSource.claimId.in_(claims))),
        Source.sensitivity != RESTRICTED_SENSITIVITY,
    )
    return [
        or_(Chunk.sourceId.in_(sources), Chunk.sourceId.in_(field_interview_sources(scope.craft_id))),
        Chunk.sourceId.not_in(withheld_field_sources()),
        Chunk.acl.in_(list(acls)),
        Chunk.kind.in_(list(kinds)),
        Chunk.sensitivity != RESTRICTED_SENSITIVITY,
        *_every_craft(scope),
    ]


def field_passages() -> ColumnElement[bool]:
    return Chunk.sourceId.in_(select(FieldRecording.sourceId))


def filed_under(fields: Sequence[str]) -> ColumnElement[bool]:
    wanted = list(fields)
    return or_(Claim.field.in_(wanted), Claim.fields.overlap(wanted))


def cited_from_kinds(kinds: Sequence[str]) -> ColumnElement[bool]:
    return exists().where(
        ClaimSource.claimId == Claim.id,
        ClaimSource.sourceId == Source.id,
        Source.kind.in_(list(kinds)),
        Source.sensitivity != RESTRICTED_SENSITIVITY,
        Source.id.not_in(withheld_field_sources()),
    )


def claim_lexical_ranking(
    conditions: Sequence[ColumnElement[bool]], tsquery: str, *, depth: int = RANKING_DEPTH
) -> Select[tuple[uuid.UUID]]:
    return _lexical(Claim.id, Claim.tsv, conditions, tsquery, depth)


def chunk_lexical_ranking(
    conditions: Sequence[ColumnElement[bool]], tsquery: str, *, depth: int = RANKING_DEPTH
) -> Select[tuple[uuid.UUID]]:
    return _lexical(Chunk.id, Chunk.tsv, conditions, tsquery, depth)


def claim_entity_ranking(
    conditions: Sequence[ColumnElement[bool]],
    scope: CraftScope,
    question: str,
    *,
    depth: int = RANKING_DEPTH,
) -> Select[tuple[uuid.UUID]]:
    named = _named_concepts(scope, question)
    edges = select(ConceptEdge.id.label("id"), named.c.weight).join(
        named, or_(ConceptEdge.srcId == named.c.id, ConceptEdge.dstId == named.c.id)
    )
    subjects = select(named.c.id, named.c.weight).union_all(edges).subquery("subjects")
    weight = func.max(subjects.c.weight).label("weight")
    return (
        select(Claim.id)
        .join(subjects, Claim.subjectId == subjects.c.id)
        .where(*conditions)
        .group_by(Claim.id)
        .order_by(weight.desc(), Claim.id)
        .limit(depth)
    )


def _named_concepts(scope: CraftScope, question: str) -> Any:
    names = _concept_names().subquery("names")
    name = func.lower(func.trim(names.c.name))
    asked = func.lower(literal(question))
    return (
        select(names.c.id.label("id"), func.max(func.length(name)).label("weight"))
        .where(
            names.c.id.in_(scope_concepts(scope)),
            func.length(name) >= ENTITY_NAME_MIN_CHARS,
            func.strpos(asked, name) > 0,
            asked.op("~", is_comparison=True)(_whole_word(name)),
        )
        .group_by(names.c.id)
        .cte("named")
    )


def _whole_word(name: ColumnElement[str]) -> ColumnElement[str]:
    escaped = func.regexp_replace(name, REGEX_SPECIALS, REGEX_ESCAPED, "g", type_=String)
    return func.concat(WORD_BEFORE, escaped, WORD_AFTER)


def _concept_names() -> CompoundSelect[Any]:
    listed = (
        select(TermConcept.conceptId.label("concept"), Term.label, Term.aliases, Term.localNames)
        .join(Term, Term.id == TermConcept.termId)
        .subquery("termed")
    )
    return union_all(
        select(Concept.id.label("id"), Concept.name.label("name")),
        select(Concept.id, func.split_part(Concept.name, NAME_GLOSS_OPEN, 1)),
        select(Concept.id, func.substring(Concept.name, NAME_GLOSS)),
        select(listed.c.concept, listed.c.label),
        select(listed.c.concept, func.unnest(listed.c.aliases)),
        select(listed.c.concept, func.unnest(listed.c.localNames)),
    )


def claim_vector_ranking(
    conditions: Sequence[ColumnElement[bool]], vector: Sequence[float], *, depth: int = RANKING_DEPTH
) -> Select[tuple[uuid.UUID]]:
    return vector_ranking(Claim, conditions, vector, depth)


def chunk_vector_ranking(
    conditions: Sequence[ColumnElement[bool]], vector: Sequence[float], *, depth: int = RANKING_DEPTH
) -> Select[tuple[uuid.UUID]]:
    return vector_ranking(Chunk, conditions, vector, depth)


def lexical_rank(tsv: Any, query: ColumnElement[Any]) -> ColumnElement[float]:
    return func.ts_rank_cd(tsv, query)


def _lexical(
    key: ColumnElement[uuid.UUID],
    tsv: Any,
    conditions: Sequence[ColumnElement[bool]],
    tsquery: str,
    depth: int,
) -> Select[tuple[uuid.UUID]]:
    terms = tsquery_terms(tsquery)
    asked = _asked(terms)
    slots = [select(asked.c[f"slot_{index}"]).scalar_subquery() for index in range(len(terms))]
    query = select(any_slot([asked.c[f"slot_{index}"] for index in range(len(terms))])).scalar_subquery()
    density = lexical_rank(tsv, query)
    matched = [tsv.op("@@")(slot).label(f"term_{index}") for index, slot in enumerate(slots)]
    candidates = (
        select(key.label("id"), density.label("density"), *matched)
        .where(*conditions, tsv.op("@@")(query))
        .order_by(density.desc(), key)
        .limit(LEXICAL_CANDIDATES)
        .cte("lexical")
        .prefix_with("MATERIALIZED")
    )
    found = select(func.count()).select_from(candidates).scalar_subquery()
    score: ColumnElement[float] = literal(0.0)
    for index in range(len(terms)):
        score = score + _rarity(candidates, candidates.c[f"term_{index}"], found)
    return (
        select(candidates.c.id)
        .order_by(score.desc(), candidates.c.density.desc(), candidates.c.id)
        .limit(depth)
    )


def _asked(terms: Sequence[str]) -> Any:
    named = named_by(terms).cte("glossary")
    slots = [slot_query(term, named).label(f"slot_{index}") for index, term in enumerate(terms)]
    return select(*slots).cte("asked")


def _rarity(candidates: Any, matched: ColumnElement[bool], found: ColumnElement[int]) -> ColumnElement[float]:
    holding = select(func.count()).select_from(candidates).where(matched).scalar_subquery()
    weight = func.ln(1.0 + cast(found, Float) / func.greatest(holding, 1))
    return case((matched, weight), else_=0.0)
