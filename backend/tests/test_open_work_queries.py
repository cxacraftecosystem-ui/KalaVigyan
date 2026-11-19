import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.dialects import postgresql

from app.research.open_work import Viewer, WorkFilters
from app.services.coverage import subject_holdings
from app.services.open_work import list_open_work
from app.services.open_work_components import craft_component_kinds
from app.services.open_work_counts import Owners, subject_counts
from app.services.open_work_pages import monograph_layouts

NOW = datetime(2026, 11, 19, 12, 0, tzinfo=UTC)
CRAFT = uuid.UUID("0f000000-0000-4000-8000-000000000001")
CATEGORY = uuid.UUID("0f000000-0000-4000-8000-000000000002")


class NoRows:
    def all(self) -> list[Any]:
        return []

    def first(self) -> None:
        return None

    def one(self) -> tuple[int, None]:
        return (0, None)


class RecordingSession:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def _record(self, statement: Any) -> None:
        self.statements.append(str(statement.compile(dialect=postgresql.dialect())))

    async def execute(self, statement: Any) -> NoRows:
        self._record(statement)
        return NoRows()

    async def scalars(self, statement: Any) -> NoRows:
        self._record(statement)
        return NoRows()

    async def scalar(self, statement: Any) -> None:
        self._record(statement)


async def test_every_open_work_query_compiles_for_postgres_and_an_empty_catalogue_has_no_work() -> None:
    session = RecordingSession()
    work = await list_open_work(
        session,  # type: ignore[arg-type]
        WorkFilters(),
        Viewer(review_role="ADMIN"),
        site="https://kv.example",
        now=NOW,
    )
    assert (work.total, work.tasks, work.reservation_minutes) == (0, [], 120)
    joined = "\n".join(session.statements)
    for table in (
        '"Craft"',
        '"CraftCategory"',
        '"TaskReservation"',
        '"ComponentProposal"',
        '"ImageContribution"',
    ):
        assert table in joined


async def test_the_counts_keep_twenty_ids_in_order_per_field() -> None:
    session = RecordingSession()
    counts = await subject_counts(session, Owners(crafts=(CRAFT,), categories=(CATEGORY,)))  # type: ignore[arg-type]
    assert counts.one_source == {} and counts.links == {}
    joined = "\n".join(session.statements)
    assert (
        "array_agg(per_fact.claim ORDER BY per_fact.claim))[%(param_1)s::INTEGER:%(param_2)s::INTEGER]"
        in joined
    )
    assert '"CuratedCategoryClaim"' in joined


async def test_the_coverage_reads_claims_structure_sections_and_figures_of_crafts_and_categories() -> None:
    session = RecordingSession()
    held = await subject_holdings(session, Owners(crafts=(CRAFT,), categories=(CATEGORY,)))  # type: ignore[arg-type]
    assert held == {}
    joined = "\n".join(session.statements)
    for table in (
        '"CraftGiRecord"',
        '"CuratedCraft"',
        '"CuratedCategory"',
        '"ArticleSection"',
        '"KnowledgePiece"',
    ):
        assert table in joined
    assert "jsonb_array_length" in joined
    assert '"Source".sensitivity != ' in joined
    assert "= ANY (" in joined


async def test_component_kinds_reach_a_craft_through_every_key_the_library_uses() -> None:
    session = RecordingSession()
    assert await craft_component_kinds(session, [CRAFT]) == {}  # type: ignore[arg-type]
    [union] = session.statements
    for joined in ('"Concept"', '"ProcessStage"', '"Material"', '"StageMaterial"', '"CraftLocation"'):
        assert joined in union
    assert await craft_component_kinds(RecordingSession(), []) == {}  # type: ignore[arg-type]


def test_only_kutch_ajrakh_is_in_the_monograph_form_and_it_has_a_layout() -> None:
    assert dict(monograph_layouts()) == {"Kutch-Ajrakh": True}
