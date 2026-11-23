import uuid
from typing import Any

from sqlalchemy.dialects import postgresql

from app.services.answer_events import CitedClaims
from app.services.citation_contexts import CONTEXT_ACLS, with_contexts
from app.services.knowledge_view import ClaimView

QUOTED = uuid.UUID(int=1)
INFERRED = uuid.UUID(int=2)
UNLINKED = uuid.UUID(int=3)
PASSAGE = "Printers boil the cloth with alum. Alum binds alizarin to cotton as a red lake. The lake is fast."


class Rows:
    def __init__(self, rows: list[tuple[uuid.UUID, str]]) -> None:
        self.rows = rows
        self.statements: list[Any] = []

    async def execute(self, statement: Any) -> list[tuple[uuid.UUID, str]]:
        self.statements.append(statement)
        return self.rows


def cite(cite_id: uuid.UUID, quote: str | None) -> dict[str, Any]:
    return {
        "id": str(cite_id),
        "quote": quote,
        "context": None,
        "evidence": "QUOTED" if quote else "INFERRED",
    }


def claims() -> CitedClaims:
    view = ClaimView(
        uuid.UUID(int=9),
        "Alum binds alizarin to cotton.",
        "PROVISIONAL",
        "MECHANISM",
        None,
        citations=[
            cite(QUOTED, "Alum binds alizarin to cotton"),
            cite(INFERRED, None),
            cite(UNLINKED, "a lake"),
        ],
    )
    return CitedClaims(views={view.id: view}, sources={})


async def test_a_quoted_citation_carries_the_public_passage_around_its_quote() -> None:
    session: Any = Rows([(QUOTED, PASSAGE), (INFERRED, "an inferred citation shows no passage")])
    found = await with_contexts(session, claims())
    (view,) = found.views.values()
    assert [citation["context"] for citation in view.citations] == [PASSAGE, None, None]
    assert CONTEXT_ACLS == ("PUBLIC", "SIGNED_IN") and "RESEARCHER" not in CONTEXT_ACLS


async def test_a_context_is_a_passage_and_never_a_transcript_window() -> None:
    session: Any = Rows([(QUOTED, PASSAGE)])
    await with_contexts(session, claims())
    compiled = session.statements[0].compile(dialect=postgresql.dialect())
    assert '"Chunk".kind = %(kind_1)s' in str(compiled)
    assert compiled.params["kind_1"] == "PASSAGE"


async def test_citations_without_a_quote_ask_nothing() -> None:
    session: Any = Rows([])
    view = ClaimView(
        uuid.UUID(int=9), "A guess.", "HYPOTHESIS", "MECHANISM", None, citations=[cite(INFERRED, None)]
    )
    unchanged = CitedClaims(views={view.id: view}, sources={})
    assert await with_contexts(session, unchanged) is unchanged
    assert session.statements == []
