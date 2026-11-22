import uuid
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import Select

from app.models import Claim
from app.research.retrieval import SHOWN_CLAIM_STATUSES
from app.retrieval.citation_access import HELD_KEPT, READABLE, reader_citations, reader_fact

FACT = uuid.uuid5(uuid.NAMESPACE_URL, "test-citation-access/fact")


def compiled(statement: Select[Any]) -> tuple[str, dict[str, Any]]:
    result = statement.compile(dialect=postgresql.dialect())
    return " ".join(result.string.split()), dict(result.params)


def params_with(params: dict[str, Any], prefix: str) -> list[Any]:
    return [value for name, value in sorted(params.items()) if name.startswith(prefix)]


def test_every_citation_of_a_source_readers_may_see_is_read_with_whether_its_words_are_readable() -> None:
    sql, params = compiled(reader_citations([FACT], acls=("PUBLIC",)))
    assert sql.startswith('SELECT "ClaimSource".id') and f" AS {READABLE} FROM " in sql
    assert 'FROM "ClaimSource" JOIN "Source" ON "Source".id = "ClaimSource"."sourceId"' in sql
    assert '"Chunk".id = "ClaimSource"."chunkId" AND "Chunk".acl IN' in sql
    assert '"ClaimSource"."chunkId" IS NULL AND ("ClaimSource".quote IS NULL OR ' in sql
    assert '"Chunk"."sourceId" = "ClaimSource"."sourceId" AND (' in sql and '"Chunk".acl NOT IN' in sql
    assert 'FROM "Chunk", "ClaimSource"' not in sql and 'FROM "Source", "ClaimSource"' not in sql
    where = sql.split(f" AS {READABLE} FROM ", 1)[1]
    assert (
        '"Source".sensitivity != ' in where
        and '"Source".id NOT IN (SELECT "FieldRecording"."sourceId"' in where
    )
    assert "acl" not in where
    assert params_with(params, "acl_") == [["PUBLIC"], ["PUBLIC"]]
    assert params_with(params, "sensitivity_") == ["RESTRICTED"] * 4
    assert params_with(params, "claimId_") == [[FACT]]


def test_a_fact_a_reader_sees_is_shown_open_filed_where_readers_look_cited_by_a_source_they_see_and_not_held() -> (
    None
):
    sql, params = compiled(select(Claim.id).where(*reader_fact()))
    assert params_with(params, "status_") == [list(SHOWN_CLAIM_STATUSES)]
    assert params_with(params, "sensitivity_") == ["OPEN", "OPEN", "OPEN", "RESTRICTED"]
    assert 'reader_concept.id = "Claim"."subjectId" AND reader_concept.sensitivity = ' in sql
    assert 'reader_concept.id = reader_edge."srcId" OR reader_concept.id = reader_edge."dstId"' in sql
    assert 'reader_cite."claimId" = "Claim".id AND reader_source.sensitivity != ' in sql
    assert 'reader_source.id NOT IN (SELECT "FieldRecording"."sourceId"' in sql
    assert '"ClaimSource"."quoteCheck" != ' in sql and params_with(params, "quoteCheck_") == ["FAIL"]
    assert "acl" not in sql


def test_a_contributor_s_reading_keeps_a_held_fact_and_a_mode_narrows_the_statuses() -> None:
    sql, params = compiled(select(Claim.id).where(*reader_fact(HELD_KEPT, statuses=("APPROVED",))))
    assert "quoteCheck" not in sql
    assert params_with(params, "status_") == [["APPROVED"]]


def test_a_reader_is_never_shown_a_hidden_status() -> None:
    with pytest.raises(ValueError, match="RETRACTED"):
        reader_fact(statuses=("APPROVED", "RETRACTED"))
