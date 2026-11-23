from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0089_piece_embedding_stamps"
down_revision: str | Sequence[str] | None = "0091_craft_page_archive_dropped"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MODEL_CHARS = 120


def upgrade() -> None:
    op.add_column("KnowledgePiece", sa.Column("embeddingModel", sa.String(length=MODEL_CHARS), nullable=True))
    op.execute(
        'UPDATE "KnowledgePiece" SET "embeddingModel" = kv_embedding_model() WHERE "embedding" IS NOT NULL'
    )


def downgrade() -> None:
    op.drop_column("KnowledgePiece", "embeddingModel")
