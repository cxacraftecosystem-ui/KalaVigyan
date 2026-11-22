import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy.dialects import postgresql

from app.models import AuditLog, User
from app.services import access_roster, reader_profiles, share_links, share_owners

TOKEN = "k7Qm2vX9pL4sT8wB1nR6yC3dF5gH0jZa"
ASKER = User(id=uuid.UUID(int=21), name="Meera Iyer", email="meera@example.org", role="RESEARCHER")
PROFESSOR = User(id=uuid.UUID(int=22), name="Asha Mehta", email="asha@example.org", role="PROFESSOR")


class NoRow:
    def __init__(self) -> None:
        self.statements: list[Any] = []

    async def execute(self, statement: Any) -> SimpleNamespace:
        self.statements.append(statement)
        return SimpleNamespace(first=lambda: None)


class SharedRows:
    def __init__(self, shared: dict[str, int], owners: tuple[uuid.UUID, ...] = ()) -> None:
        self.shared = shared
        self.owners = owners
        self.statements: list[str] = []
        self.added: list[Any] = []

    async def execute(self, statement: Any) -> SimpleNamespace:
        self.statements.append(sql_of(statement))
        table = getattr(statement, "table", None)
        rows = [(uuid.uuid4(),)] * self.shared.get(getattr(table, "name", ""), 0)
        owners = SimpleNamespace(all=lambda: list(self.owners))
        return SimpleNamespace(all=lambda: rows, scalars=lambda: owners, rowcount=len(self.owners))

    def add(self, row: Any) -> None:
        self.added.append(row)


def sql_of(statement: Any) -> str:
    return str(statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))


@pytest.mark.parametrize("read", [share_links.shared_answer, share_links.shared_lesson])
async def test_a_link_opens_only_while_its_owner_is_neither_deleted_nor_barred(read: Any) -> None:
    session = NoRow()
    assert await read(session, TOKEN) is None
    (statement,) = session.statements
    where = sql_of(statement)
    assert f"\"shareToken\" = '{TOKEN}'" in where
    assert '"User"."deletedAt" IS NULL' in where
    assert "AND NOT (EXISTS (SELECT *" in where
    assert "\"AccessRoster\".status IN ('REJECTED', 'SUSPENDED')" in where


async def test_withdrawing_an_owner_s_links_clears_both_kinds_and_records_why() -> None:
    session = SharedRows({"Answer": 2, "LessonPack": 1})
    withdrawn = await share_owners.withdraw_shares(
        session, ASKER.id, actor=PROFESSOR, cause="users.deleted", objects=None
    )
    assert withdrawn == share_owners.WithdrawnShares(answers=2, lessons=1)
    owner = f"\"userId\" = '{ASKER.id}'"
    assert [statement.split(" SET ")[0] for statement in session.statements] == [
        'UPDATE "Answer"',
        'UPDATE "LessonPack"',
    ]
    assert all(
        owner in statement and '"shareToken"=NULL, "sharedAt"=NULL' in statement
        for statement in session.statements
    )
    (record,) = session.added
    assert isinstance(record, AuditLog)
    assert (record.action, record.actorId, record.targetType, record.targetId) == (
        "shares.withdrawn",
        PROFESSOR.id,
        "User",
        str(ASKER.id),
    )
    assert record.detail == {"cause": "users.deleted", "answers": 2, "lessons": 1}


async def test_an_owner_with_nothing_shared_leaves_no_audit_record() -> None:
    session = SharedRows({})
    assert await share_owners.withdraw_shares(
        session, ASKER.id, actor=None, cause="users.suspended", objects=None
    ) == (share_owners.WithdrawnShares(answers=0, lessons=0))
    assert session.added == []


@pytest.mark.parametrize(
    ("before", "after", "lessons_withdrawn"),
    [
        ("PROFESSOR", "RESEARCHER", True),
        ("ADMIN", "STUDENT", True),
        ("PROFESSOR", "ADMIN", False),
        ("RESEARCHER", "STUDENT", False),
    ],
)
async def test_a_role_that_can_no_longer_build_lessons_stops_sharing_them(
    before: str, after: str, lessons_withdrawn: bool
) -> None:
    session = SharedRows({"LessonPack": 1})
    owner = SimpleNamespace(id=PROFESSOR.id, role=before)
    await reader_profiles.apply_role_change(session, owner, after, objects=None)
    lesson_updates = [
        statement for statement in session.statements if statement.startswith('UPDATE "LessonPack"')
    ]
    assert bool(lesson_updates) is lessons_withdrawn
    assert not [statement for statement in session.statements if statement.startswith('UPDATE "Answer"')]
    assert [record.detail["cause"] for record in session.added] == (
        ["users.role_changed"] if lessons_withdrawn else []
    )


async def test_barring_an_address_ends_its_sessions_and_withdraws_every_link_of_its_account() -> None:
    session = SharedRows({"Answer": 1}, owners=(ASKER.id,))
    await access_roster.bar_account(
        session, " Meera@Example.org ", actor=PROFESSOR, cause="access.suspended", objects=None
    )
    ended, owners, *withdrawals = session.statements
    assert ended.startswith('UPDATE "User" SET') and '"tokenVersion"=("User"."tokenVersion" + 1)' in ended
    assert ended.endswith("WHERE lower(\"User\".email) = 'meera@example.org'")
    assert owners.endswith("WHERE lower(\"User\".email) = 'meera@example.org'")
    assert [statement.split(" SET ")[0] for statement in withdrawals] == [
        'UPDATE "Answer"',
        'UPDATE "LessonPack"',
    ]
    assert [record.detail for record in session.added] == [
        {"cause": "access.suspended", "answers": 1, "lessons": 0}
    ]
