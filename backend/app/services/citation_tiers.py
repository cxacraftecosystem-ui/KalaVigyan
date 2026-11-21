from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import ColumnElement, case

from app.research.retrieval import (
    EVERY_CHUNK_ACLS,
    OPEN_CHUNK_ACLS,
    PUBLIC_CHUNK_ACL,
    RESEARCHER_CHUNK_ACL,
    SIGNED_IN_CHUNK_ACL,
    SIGNED_IN_CHUNK_ACLS,
)
from app.retrieval.citation_access import readable_citation

__all__ = ["READER_TIERS", "reading_acl"]

READER_TIERS: tuple[tuple[str, Sequence[str]], ...] = (
    (PUBLIC_CHUNK_ACL, OPEN_CHUNK_ACLS),
    (SIGNED_IN_CHUNK_ACL, SIGNED_IN_CHUNK_ACLS),
    (RESEARCHER_CHUNK_ACL, EVERY_CHUNK_ACLS),
)


def reading_acl() -> ColumnElement[str | None]:
    return case(*((readable_citation(acls), acl) for acl, acls in READER_TIERS), else_=None)
