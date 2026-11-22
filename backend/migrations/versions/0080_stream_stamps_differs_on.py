from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0080_stream_stamps_differs_on"
down_revision: str | Sequence[str] | None = "0075_mcp_call_name_filled"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STREAMS = "FieldVoiceStream"
CHANGE_ID_CHARS = 64
DIFFERS_ON_CHARS = 300
LAST_BOTH_OR_NEITHER = 'num_nonnulls("lastAt", "lastId") <> 1'
GONE_LAST_BOTH_OR_NEITHER = 'num_nonnulls("goneLastAt", "goneLastId") <> 1'


def upgrade() -> None:
    op.add_column("FieldVoiceStream", sa.Column("lastAt", sa.DateTime(timezone=True), nullable=True))
    op.add_column("FieldVoiceStream", sa.Column("lastId", sa.String(length=CHANGE_ID_CHARS), nullable=True))
    op.add_column("FieldVoiceStream", sa.Column("goneLastAt", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "FieldVoiceStream", sa.Column("goneLastId", sa.String(length=CHANGE_ID_CHARS), nullable=True)
    )
    op.create_check_constraint(op.f(f"{STREAMS}_last_check"), STREAMS, LAST_BOTH_OR_NEITHER)
    op.create_check_constraint(op.f(f"{STREAMS}_gone_last_check"), STREAMS, GONE_LAST_BOTH_OR_NEITHER)
    op.add_column("Claim", sa.Column("differsOn", sa.String(length=DIFFERS_ON_CHARS), nullable=True))


def downgrade() -> None:
    op.drop_column("Claim", "differsOn")
    op.drop_constraint(op.f(f"{STREAMS}_gone_last_check"), STREAMS, type_="check")
    op.drop_constraint(op.f(f"{STREAMS}_last_check"), STREAMS, type_="check")
    op.drop_column("FieldVoiceStream", "goneLastId")
    op.drop_column("FieldVoiceStream", "goneLastAt")
    op.drop_column("FieldVoiceStream", "lastId")
    op.drop_column("FieldVoiceStream", "lastAt")
