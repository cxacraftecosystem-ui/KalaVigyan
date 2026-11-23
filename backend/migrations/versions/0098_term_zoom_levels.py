from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0098_term_zoom_levels"
down_revision: str | Sequence[str] | None = "0095_candidate_check_differs_on"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ZOOM_LEVEL_CHARS = 16
ZOOM_LEVEL_CHECK = "Term_zoomLevel_check"
ZOOM_LEVELS = ("WORKSHOP", "CLOTH", "FIBRE", "MOLECULE")


def upgrade() -> None:
    op.add_column("Term", sa.Column("zoomLevel", sa.String(length=ZOOM_LEVEL_CHARS), nullable=True))
    listed = ", ".join(f"'{level}'" for level in ZOOM_LEVELS)
    op.create_check_constraint(op.f(ZOOM_LEVEL_CHECK), "Term", f'"zoomLevel" IN ({listed})')


def downgrade() -> None:
    op.drop_constraint(op.f(ZOOM_LEVEL_CHECK), "Term", type_="check")
    op.drop_column("Term", "zoomLevel")
