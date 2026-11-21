from collections.abc import Sequence

from alembic import op

revision: str = "0061_embedding_recipe"
down_revision: str | Sequence[str] | None = "0060_reranking"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RECIPE_MARK = "#"
EMBEDDING_RECIPE = "ctx1"

ROUTE_MODEL = """
    SELECT r.model{suffix}
    FROM "RoutePolicy" r
    JOIN "Provider" p ON p.id = r."providerId"
    WHERE r.task = 'EMBED' AND r.enabled AND p.enabled
    ORDER BY r.ordinal
    LIMIT 1
"""

CURRENT_MODEL_FUNCTION = """
CREATE OR REPLACE FUNCTION kv_embedding_model() RETURNS text
LANGUAGE sql STABLE AS $fn$
{body}
$fn$
"""

STAMP_FUNCTION = """
CREATE OR REPLACE FUNCTION kv_stamp_embedding() RETURNS trigger
LANGUAGE plpgsql AS $fn$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF NEW."text" IS DISTINCT FROM OLD."text" AND NEW."embedding" IS NOT DISTINCT FROM OLD."embedding" THEN
            NEW."embedding" := NULL;
        END IF;
        IF NEW."embedding" IS NOT NULL AND NEW."embedding" IS DISTINCT FROM OLD."embedding"
            AND NEW."embeddingModel" IS NOT DISTINCT FROM OLD."embeddingModel" THEN
            NEW."embeddingModel" := {stamp};
        END IF;
    ELSIF NEW."embedding" IS NOT NULL AND NEW."embeddingModel" IS NULL THEN
        NEW."embeddingModel" := {stamp};
    END IF;
    IF NEW."embedding" IS NULL THEN
        NEW."embeddingModel" := NULL;
    END IF;
    RETURN NEW;
END;
$fn$
"""

MODEL_ONLY = f"split_part(kv_embedding_model(), '{RECIPE_MARK}', 1)"
FULL_STAMP = "kv_embedding_model()"


def _current_model(recipe: str) -> str:
    suffix = f" || '{RECIPE_MARK}{recipe}'" if recipe else ""
    return CURRENT_MODEL_FUNCTION.format(body=ROUTE_MODEL.format(suffix=suffix))


def upgrade() -> None:
    op.execute(_current_model(EMBEDDING_RECIPE))
    op.execute(STAMP_FUNCTION.format(stamp=MODEL_ONLY))


def downgrade() -> None:
    op.execute(_current_model(""))
    op.execute(STAMP_FUNCTION.format(stamp=FULL_STAMP))
