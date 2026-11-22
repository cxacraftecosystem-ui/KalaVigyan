from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0062_open_data_scope"
down_revision: str | Sequence[str] | None = "0061_embedding_recipe"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "OpenDataRelease"
SCOPE_CHARS = 160
SCOPE_RULE = '"scope" IS NULL OR "scope" <> \'\''
UNIQUE_BEFORE = ("target", "version")
UNIQUE_AFTER = ("target", "scope", "version")
INDEX_BEFORE = ("target", "state", "releasedOn")
INDEX_AFTER = ("target", "scope", "state", "releasedOn")


def _name(columns: Sequence[str], suffix: str) -> str:
    return f"{TABLE}_{'_'.join(columns)}_{suffix}"


def upgrade() -> None:
    op.add_column("OpenDataRelease", sa.Column("scope", sa.String(length=SCOPE_CHARS), nullable=True))
    op.create_check_constraint(op.f(f"{TABLE}_scope_check"), TABLE, SCOPE_RULE)
    op.drop_constraint(op.f(_name(UNIQUE_BEFORE, "key")), TABLE, type_="unique")
    op.create_unique_constraint(
        op.f(_name(UNIQUE_AFTER, "key")), TABLE, list(UNIQUE_AFTER), postgresql_nulls_not_distinct=True
    )
    op.drop_index(op.f(_name(INDEX_BEFORE, "idx")), table_name=TABLE)
    op.create_index(op.f(_name(INDEX_AFTER, "idx")), TABLE, list(INDEX_AFTER))


def downgrade() -> None:
    op.execute(f'DELETE FROM "{TABLE}" WHERE "scope" IS NOT NULL')
    op.drop_index(op.f(_name(INDEX_AFTER, "idx")), table_name=TABLE)
    op.create_index(op.f(_name(INDEX_BEFORE, "idx")), TABLE, list(INDEX_BEFORE))
    op.drop_constraint(op.f(_name(UNIQUE_AFTER, "key")), TABLE, type_="unique")
    op.create_unique_constraint(op.f(_name(UNIQUE_BEFORE, "key")), TABLE, list(UNIQUE_BEFORE))
    op.drop_constraint(op.f(f"{TABLE}_scope_check"), TABLE, type_="check")
    op.drop_column("OpenDataRelease", "scope")
