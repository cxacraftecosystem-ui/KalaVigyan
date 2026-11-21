from __future__ import annotations

import re
import unicodedata

__all__ = [
    "DOCUMENT_TEMPLATE",
    "QUERY_PREFIX",
    "TSQUERY_MAX_TERMS",
    "TSQUERY_MIN_TERM_CHARS",
    "document_text",
    "or_tsquery",
    "query_terms",
    "query_text",
    "tsquery_terms",
]

QUERY_PREFIX = "task: search result | query: "
DOCUMENT_TEMPLATE = "title: {title} | text: {text}"
NO_TITLE = "none"
TSQUERY_MAX_TERMS = 40
TSQUERY_MIN_TERM_CHARS = 3
TERM = re.compile(r"[a-z0-9]+")
OR = " | "


def query_text(text: str) -> str:
    return QUERY_PREFIX + " ".join(text.split())


def document_text(text: str, *, title: str | None = None) -> str:
    label = " ".join((title or "").split()) or NO_TITLE
    return DOCUMENT_TEMPLATE.format(title=label, text=" ".join(text.split()))


def or_tsquery(text: str) -> str | None:
    return OR.join(query_terms(text)) or None


def query_terms(text: str) -> list[str]:
    folded = unicodedata.normalize("NFKC", text).casefold()
    terms = [term for term in dict.fromkeys(TERM.findall(folded)) if len(term) >= TSQUERY_MIN_TERM_CHARS]
    return terms[:TSQUERY_MAX_TERMS]


def tsquery_terms(tsquery: str) -> list[str]:
    return [term for term in dict.fromkeys(part.strip() for part in tsquery.split("|")) if term]
