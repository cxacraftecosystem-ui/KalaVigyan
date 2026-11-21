from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0060_reranking"
down_revision: str | Sequence[str] | None = "0059_page_translations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ENUM_ADDITIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("AiProvider", ("VOYAGE",)),
    ("AiTask", ("RERANK",)),
)
ENUM_COLUMNS: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    ("AiProvider", (("Provider", "name"), ("UsageEvent", "provider"))),
    ("AiTask", (("RoutePolicy", "task"), ("UsageEvent", "task"))),
)

VOYAGE = {
    "name": "VOYAGE",
    "preset": "voyage",
    "kind": "voyage",
    "baseUrl": "https://api.voyageai.com/v1",
    "apiKeySecretKey": "VOYAGE_API_KEY",
    "dataClass": "ANY",
    "maxConcurrency": 8,
}
RERANK_ROUTE = {"task": "RERANK", "ordinal": 1, "model": "rerank-3", "provider": "VOYAGE"}

INSERT_PROVIDER = (
    'INSERT INTO "Provider" (name, preset, kind, "baseUrl", "apiKeySecretKey", "dataClass", "maxConcurrency") '
    'VALUES (CAST(:name AS "AiProvider"), :preset, :kind, :baseUrl, :apiKeySecretKey, '
    'CAST(:dataClass AS "ProviderDataClass"), :maxConcurrency) ON CONFLICT (name) DO NOTHING'
)
INSERT_ROUTE = (
    'INSERT INTO "RoutePolicy" (task, ordinal, "providerId", model) '
    'SELECT CAST(:task AS "AiTask"), :ordinal, p.id, :model FROM "Provider" p '
    'WHERE p.name = CAST(:provider AS "AiProvider") '
    "ON CONFLICT (task, ordinal) DO NOTHING"
)
DELETE_ROUTES = (
    'DELETE FROM "RoutePolicy" WHERE task::text = :task OR "providerId" IN '
    '(SELECT id FROM "Provider" WHERE name::text = :provider)'
)
DELETE_USAGE = 'DELETE FROM "UsageEvent" WHERE task::text = :task OR provider::text = :provider'
DELETE_PROVIDER = 'DELETE FROM "Provider" WHERE name::text = :provider'


def _listed(values: Sequence[str]) -> str:
    return ", ".join(f"'{value}'" for value in values)


def upgrade() -> None:
    with op.get_context().autocommit_block():
        for enum_name, values in ENUM_ADDITIONS:
            for value in values:
                op.execute(f"ALTER TYPE \"{enum_name}\" ADD VALUE IF NOT EXISTS '{value}'")
    op.execute(sa.text(INSERT_PROVIDER).bindparams(**VOYAGE))
    op.execute(sa.text(INSERT_ROUTE).bindparams(**RERANK_ROUTE))


def downgrade() -> None:
    named = {"task": RERANK_ROUTE["task"], "provider": VOYAGE["name"]}
    op.execute(sa.text(DELETE_ROUTES).bindparams(**named))
    op.execute(sa.text(DELETE_USAGE).bindparams(**named))
    op.execute(sa.text(DELETE_PROVIDER).bindparams(provider=VOYAGE["name"]))
    for enum_name, columns in ENUM_COLUMNS:
        _recreate_enum(enum_name, columns)


def _recreate_enum(enum_name: str, columns: Sequence[tuple[str, str]]) -> None:
    query = sa.text(f'SELECT unnest(enum_range(NULL::"{enum_name}"))::text')
    added = dict(ENUM_ADDITIONS)[enum_name]
    before = [value for (value,) in op.get_bind().execute(query) if value not in added]
    op.execute(f'ALTER TYPE "{enum_name}" RENAME TO "{enum_name}_before_0060"')
    op.execute(f'CREATE TYPE "{enum_name}" AS ENUM ({_listed(before)})')
    for table, column in columns:
        op.execute(
            f'ALTER TABLE "{table}" ALTER COLUMN "{column}" TYPE "{enum_name}" USING "{column}"::text::"{enum_name}"'
        )
    op.execute(f'DROP TYPE "{enum_name}_before_0060"')
