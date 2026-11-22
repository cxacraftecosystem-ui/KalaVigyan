from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0080_stream_stamps_differs_on"
down_revision: str | Sequence[str] | None = "0074_mcp_activity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STREAMS = "FieldVoiceStream"
CLAIMS = "Claim"
CHANGE_ID_CHARS = 64
DIFFERS_ON_CHARS = 300
STAMPS = {"last": ("lastAt", "lastId"), "gone_last": ("goneLastAt", "goneLastId")}


def upgrade() -> None:
    for name, (stamp, change) in STAMPS.items():
        op.add_column(STREAMS, sa.Column(stamp, sa.DateTime(timezone=True), nullable=True))
        op.add_column(STREAMS, sa.Column(change, sa.String(length=CHANGE_ID_CHARS), nullable=True))
        op.create_check_constraint(
            op.f(f"{STREAMS}_{name}_check"), STREAMS, f'num_nonnulls("{stamp}", "{change}") <> 1'
        )
    op.add_column(CLAIMS, sa.Column("differsOn", sa.String(length=DIFFERS_ON_CHARS), nullable=True))


def downgrade() -> None:
    op.drop_column(CLAIMS, "differsOn")
    for name, (stamp, change) in STAMPS.items():
        op.drop_constraint(op.f(f"{STREAMS}_{name}_check"), STREAMS, type_="check")
        op.drop_column(STREAMS, change)
        op.drop_column(STREAMS, stamp)
