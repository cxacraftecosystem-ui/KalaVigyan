from __future__ import annotations

import re
import unicodedata

__all__ = [
    "DOCUMENT_TEMPLATE",
    "GLOSSARY_WORD_MIN_CHARS",
    "QUERY_PREFIX",
    "TITLE_SEPARATOR",
    "TSQUERY_MAX_TERMS",
    "TSQUERY_MIN_TERM_CHARS",
    "TSQUERY_SHORT_TERMS",
    "context_title",
    "document_text",
    "is_short_term",
    "or_tsquery",
    "query_terms",
    "query_text",
    "short_terms",
    "tsquery_terms",
]

QUERY_PREFIX = "task: search result | query: "
DOCUMENT_TEMPLATE = "title: {title} | text: {text}"
NO_TITLE = "none"
TITLE_SEPARATOR = " · "
TSQUERY_MAX_TERMS = 40
TSQUERY_MIN_TERM_CHARS = 3
TSQUERY_SHORT_TERMS = 8
GLOSSARY_WORD_MIN_CHARS = 2
TERM = re.compile(r"[a-z0-9]+")
OR = " | "


def query_text(text: str) -> str:
    return QUERY_PREFIX + " ".join(text.split())


def document_text(text: str, *, title: str | None = None) -> str:
    label = " ".join((title or "").split()) or NO_TITLE
    return DOCUMENT_TEMPLATE.format(title=label, text=" ".join(text.split()))


def context_title(owner: str | None, concept: str | None, field: str | None) -> str | None:
    parts = [" ".join(part.split()) for part in (owner, concept, (field or "").capitalize()) if part]
    kept = [part for part in dict.fromkeys(parts) if part]
    return TITLE_SEPARATOR.join(kept) or None


def or_tsquery(text: str) -> str | None:
    terms = query_terms(text)
    return OR.join([*terms, *short_terms(text)]) if terms else None


def query_terms(text: str) -> list[str]:
    terms = [term for term in _words(text) if len(term) >= TSQUERY_MIN_TERM_CHARS]
    return terms[:TSQUERY_MAX_TERMS]


def short_terms(text: str) -> list[str]:
    terms = [term for term in _words(text) if GLOSSARY_WORD_MIN_CHARS <= len(term) < TSQUERY_MIN_TERM_CHARS]
    return terms[:TSQUERY_SHORT_TERMS]


def is_short_term(term: str) -> bool:
    return len(term) < TSQUERY_MIN_TERM_CHARS


def tsquery_terms(tsquery: str) -> list[str]:
    return [term for term in dict.fromkeys(part.strip() for part in tsquery.split("|")) if term]


def _words(text: str) -> list[str]:
    return list(dict.fromkeys(TERM.findall(unicodedata.normalize("NFKC", text).casefold())))
