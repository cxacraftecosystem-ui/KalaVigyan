import hashlib
import re
import unicodedata
from collections.abc import Mapping, Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0083_piece_districts_and_places"
down_revision: str | Sequence[str] | None = "0077_state_and_reach_districts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PIECES = "KnowledgePiece"
LOOKUPS = "PlaceLookup"
TOPIC_KEY_MAX_CHARS = 200
DISTRICT_SET_DIGEST_CHARS = 16
NOT_SLUG = re.compile(r"[^a-z0-9]+")
TOLD_DISTRICTS = """
UPDATE "KnowledgePiece" SET "districtLgds" = ARRAY(
    SELECT DISTINCT (district ->> 'districtLgd')::integer
    FROM jsonb_array_elements("payload" -> 'districts') AS district
    ORDER BY 1
)
WHERE "kind" = 'region_story'
  AND "craftId" IS NULL
  AND jsonb_typeof("payload" -> 'districts') = 'array'
  AND coalesce(jsonb_typeof("payload" -> 'river'), 'null') = 'null'
"""
PLACE_PIECES = """
SELECT p."id" AS id, p."topicKey" AS topic_key,
       coalesce(
           json_agg(json_build_object('lgd', d."lgd", 'name', d."name")) FILTER (WHERE d."lgd" IS NOT NULL),
           '[]'
       ) AS districts
FROM "KnowledgePiece" AS p
LEFT JOIN "CraftLocation" AS l ON l."craftId" = p."craftId"
LEFT JOIN "AdminDistrict" AS d ON d."lgd" = l."districtLgd"
WHERE p."craftId" IS NOT NULL AND p."facet" IN ('GEOGRAPHY', 'GEOLOGY', 'CLIMATE')
GROUP BY p."id", p."topicKey"
"""
REKEY = 'UPDATE "KnowledgePiece" SET "topicKey" = :key WHERE "id" = :id'
REVOKE_PUBLIC_ROLES = """
DO $do$
DECLARE grantee text;
BEGIN
    FOREACH grantee IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = grantee) THEN
            EXECUTE format('REVOKE ALL ON "PlaceLookup" FROM %I', grantee);
        END IF;
    END LOOP;
END
$do$
"""


def upgrade() -> None:
    op.add_column(
        "KnowledgePiece",
        sa.Column(
            "districtLgds",
            postgresql.ARRAY(sa.Integer()),
            server_default=sa.text("ARRAY[]::integer[]"),
            nullable=False,
        ),
    )
    op.create_index(
        "KnowledgePiece_districtLgds_gin_idx", PIECES, ["districtLgds"], unique=False, postgresql_using="gin"
    )
    op.execute(TOLD_DISTRICTS)
    _rekey_place_pieces()
    _create_place_lookups()


def downgrade() -> None:
    op.drop_table("PlaceLookup")
    op.drop_index("KnowledgePiece_districtLgds_gin_idx", table_name=PIECES)
    op.drop_column("KnowledgePiece", "districtLgds")


def rekeyed(topic_key: str, districts: Sequence[Mapping[str, object]]) -> str | None:
    namespace, _, subjects = topic_key.partition(":")
    named: dict[str, set[int]] = {}
    for district in districts:
        named.setdefault(_slug(str(district["name"])), set()).add(int(str(district["lgd"])))
    if not named or set(subjects.split("+")) != set(named):
        return None
    lgds = sorted(set().union(*named.values()))
    key = f"{namespace}:" + "+".join(sorted(f"lgd-{lgd}" for lgd in lgds))
    if len(key) <= TOPIC_KEY_MAX_CHARS:
        return key
    listed = ",".join(str(lgd) for lgd in lgds)
    return f"{namespace}:lgd-set-{hashlib.sha256(listed.encode('ascii')).hexdigest()[:DISTRICT_SET_DIGEST_CHARS]}"


def _rekey_place_pieces() -> None:
    if op.get_context().as_sql:
        return
    bind = op.get_bind()
    for row in bind.execute(sa.text(PLACE_PIECES)).mappings().all():
        key = rekeyed(row["topic_key"], row["districts"])
        if key is not None and key != row["topic_key"]:
            bind.execute(sa.text(REKEY), {"key": key, "id": row["id"]})


def _slug(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    bare = "".join(ch for ch in decomposed if not unicodedata.combining(ch)).casefold()
    return NOT_SLUG.sub("-", bare).strip("-")


def _create_place_lookups() -> None:
    op.create_table(
        "PlaceLookup",
        sa.Column("lookupKey", sa.String(length=320), nullable=False),
        sa.Column("answer", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("askedAt", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("\"lookupKey\" ~ '^(name|item):.+$'", name=op.f("PlaceLookup_lookupKey_check")),
        sa.PrimaryKeyConstraint("lookupKey", name=op.f("PlaceLookup_pkey")),
    )
    op.execute(f'ALTER TABLE "{LOOKUPS}" ENABLE ROW LEVEL SECURITY')
    op.execute(REVOKE_PUBLIC_ROLES)
