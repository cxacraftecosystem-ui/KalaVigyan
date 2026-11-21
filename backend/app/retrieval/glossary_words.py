from __future__ import annotations

from collections.abc import Sequence
from functools import reduce
from typing import Any

from sqlalchemy import ColumnElement, FromClause, Select, Subquery, func, literal, null, select, union_all

from app.models import Term

from .text import is_short_term, tsquery_terms

__all__ = [
    "OR_WORD",
    "PHRASE_QUOTE",
    "TEXT_SEARCH_CONFIG",
    "any_slot",
    "glossary_names",
    "named_by",
    "slot_query",
    "text_query",
]

TEXT_SEARCH_CONFIG = "english"
OR_WORD = " or "
PHRASE_QUOTE = '"'
SPACE = " "


def text_query(tsquery: str) -> ColumnElement[Any]:
    words = tsquery_terms(tsquery)
    if not words:
        return func.to_tsquery(TEXT_SEARCH_CONFIG, tsquery)
    named = named_by(words).subquery("glossary")
    return any_slot([slot_query(word, named) for word in words])


def any_slot(slots: Sequence[ColumnElement[Any]]) -> ColumnElement[Any]:
    return reduce(lambda first, second: first.op("||")(second), slots)


def slot_query(word: str, named: FromClause) -> ColumnElement[Any]:
    names = (
        select(func.string_agg(_phrase(named.c.name), OR_WORD)).where(named.c.word == word).scalar_subquery()
    )
    own: ColumnElement[Any] = null() if is_short_term(word) else literal(_quoted(word))
    return func.websearch_to_tsquery(TEXT_SEARCH_CONFIG, func.concat_ws(OR_WORD, own, names))


def named_by(words: Sequence[str]) -> Select[Any]:
    asked, other = glossary_names("asked_names"), glossary_names("other_names")
    folded = func.lower(func.btrim(asked.c.name))
    return (
        select(folded.label("word"), other.c.name.label("name"))
        .select_from(asked)
        .join(other, other.c.term == asked.c.term)
        .where(folded.in_(list(words)))
    )


def glossary_names(name: str) -> Subquery:
    return union_all(
        select(Term.id.label("term"), Term.label.label("name")),
        select(Term.id, func.unnest(Term.aliases)),
        select(Term.id, func.unnest(Term.localNames)),
    ).subquery(name)


def _phrase(name: Any) -> ColumnElement[str]:
    return func.concat(PHRASE_QUOTE, func.replace(name, PHRASE_QUOTE, SPACE), PHRASE_QUOTE)


def _quoted(word: str) -> str:
    return f"{PHRASE_QUOTE}{word}{PHRASE_QUOTE}"
