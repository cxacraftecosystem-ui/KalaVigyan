from collections.abc import Sequence

import sqlalchemy as sa
from alembic import context, op

revision: str = "0067_seed_rows_retired"
down_revision: str | Sequence[str] | None = "0068_journals_and_shared_terms"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STAMP = sa.DateTime(timezone=True)
GI_TABLE = "GiRegistration"
SEED_PARAMS = {
    "seed_actor": "import",
    "seed_note": "seed import %",
    "seed_variant": "seed_claims",
    "curation_actor": "curation",
    "retired_note": "seed row retired, the craft has a curated dossier",
    "restored_note": "seed row restored, its craft's curated dossier no longer retires it",
}
HIDDEN_STATUSES = "'DRAFT', 'REJECTED', 'RETRACTED', 'SUPERSEDED', 'WITHDRAWN'"
CURATED_CONCEPTS = 'SELECT "id" FROM "Concept" WHERE "craftId" IN (SELECT "craftId" FROM "CuratedCraft")'
NEW_EVENT = (
    'INSERT INTO "ReviewEvent" ("claimId", "actorKind", "systemActor", "fromStatus", "toStatus", '
    '"fromLevel", "toLevel", "note")'
)
RETIRE_CLAIMS = f"""
WITH concepts AS ({CURATED_CONCEPTS}),
retired AS (
    SELECT c."id", c."status", c."evidenceLevel" FROM "Claim" c
    WHERE c."status" NOT IN ({HIDDEN_STATUSES})
      AND NOT EXISTS (SELECT 1 FROM "CuratedClaim" k WHERE k."claimId" = c."id")
      AND EXISTS (
          SELECT 1 FROM "ReviewEvent" e
          WHERE e."claimId" = c."id" AND e."systemActor" = :seed_actor AND e."note" LIKE :seed_note
      )
      AND (
          (c."subjectType" = 'CONCEPT' AND c."subjectId" IN (SELECT "id" FROM concepts))
          OR (c."subjectType" = 'EDGE' AND c."subjectId" IN (
              SELECT g."id" FROM "ConceptEdge" g
              WHERE g."srcId" IN (SELECT "id" FROM concepts) OR g."dstId" IN (SELECT "id" FROM concepts)
          ))
      )
),
noted AS (
    {NEW_EVENT}
    SELECT "id", CAST('SYSTEM' AS "ActorKind"), :curation_actor, "status", CAST('SUPERSEDED' AS "ClaimStatus"),
           "evidenceLevel", "evidenceLevel", :retired_note
    FROM retired
)
UPDATE "Claim" SET "status" = 'SUPERSEDED', "updatedAt" = now()
FROM retired WHERE "Claim"."id" = retired."id"
"""
ARCHIVE_PROCESSES = """
UPDATE "Process" SET "archivedAt" = now(), "updatedAt" = now()
WHERE "variant" = :seed_variant AND "archivedAt" IS NULL
  AND "craftId" IN (SELECT "craftId" FROM "CuratedCraft")
"""
RESTORE_CLAIMS = f"""
WITH retirements AS (
    SELECT DISTINCT ON (e."claimId") e."claimId", e."fromStatus", e."createdAt"
    FROM "ReviewEvent" e WHERE e."note" = :retired_note
    ORDER BY e."claimId", e."createdAt" DESC
),
restored AS (
    SELECT c."id", r."fromStatus", c."evidenceLevel" FROM "Claim" c
    JOIN retirements r ON r."claimId" = c."id"
    WHERE c."status" = 'SUPERSEDED' AND r."fromStatus" IS NOT NULL
      AND NOT EXISTS (
          SELECT 1 FROM "ReviewEvent" x WHERE x."claimId" = c."id" AND x."createdAt" > r."createdAt"
      )
),
noted AS (
    {NEW_EVENT}
    SELECT "id", CAST('SYSTEM' AS "ActorKind"), :curation_actor, CAST('SUPERSEDED' AS "ClaimStatus"),
           "fromStatus", "evidenceLevel", "evidenceLevel", :restored_note
    FROM restored
)
UPDATE "Claim" SET "status" = restored."fromStatus", "updatedAt" = now()
FROM restored WHERE "Claim"."id" = restored."id"
"""
RESTORE_PROCESSES = """
UPDATE "Process" SET "archivedAt" = NULL, "updatedAt" = now()
WHERE "variant" = :seed_variant AND "archivedAt" IS NOT NULL
"""
REVOKE_PUBLIC_ROLES = """
DO $do$
DECLARE grantee text;
BEGIN
    FOREACH grantee IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = grantee) THEN
            EXECUTE format('REVOKE ALL ON "{table}" FROM %I', grantee);
        END IF;
    END LOOP;
END
$do$
"""


def _bound(statement: str) -> sa.TextClause:
    names = [name for name in SEED_PARAMS if f":{name}" in statement]
    return sa.text(statement).bindparams(**{name: SEED_PARAMS[name] for name in names})


def retire_statements() -> list[sa.TextClause]:
    return [_bound(RETIRE_CLAIMS), _bound(ARCHIVE_PROCESSES)]


def restore_statements() -> list[sa.TextClause]:
    return [_bound(RESTORE_CLAIMS), _bound(RESTORE_PROCESSES)]


def _refuse_written_gi_rows() -> None:
    if context.is_offline_mode():
        return
    written = op.get_bind().execute(sa.text(f'SELECT count(*) FROM "{GI_TABLE}"')).scalar_one()
    if written:
        raise RuntimeError(
            f"{GI_TABLE} holds {written} rows; move them into CraftGiRecord before it is dropped"
        )


def upgrade() -> None:
    op.add_column("Process", sa.Column("archivedAt", STAMP, nullable=True))
    op.add_column("KnowledgePiece", sa.Column("rebuildTriedAt", STAMP, nullable=True))
    for statement in retire_statements():
        op.execute(statement)
    _refuse_written_gi_rows()
    op.drop_index(op.f("GiRegistration_craftId_idx"), table_name=GI_TABLE)
    op.drop_table("GiRegistration")


def _gi_registration_parts() -> list[sa.SchemaItem]:
    return [
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("giNo", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column("goodsClass", sa.String(length=80), nullable=True),
        sa.Column("state", sa.String(length=120), nullable=True),
        sa.Column("registeredOn", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=80), nullable=True),
        sa.Column("holder", sa.Text(), nullable=True),
        sa.Column("craftId", sa.UUID(), nullable=True),
        sa.Column("sourceId", sa.UUID(), nullable=True),
        sa.Column("createdAt", STAMP, server_default=sa.text("now()"), nullable=False),
        sa.Column("updatedAt", STAMP, server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["craftId"], ["Craft.id"], name=op.f("GiRegistration_craftId_fkey"), ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["sourceId"], ["Source.id"], name=op.f("GiRegistration_sourceId_fkey"), ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("GiRegistration_pkey")),
        sa.UniqueConstraint("giNo", name=op.f("GiRegistration_giNo_key")),
    ]


def downgrade() -> None:
    op.create_table("GiRegistration", *_gi_registration_parts())
    op.create_index(op.f("GiRegistration_craftId_idx"), GI_TABLE, ["craftId"], unique=False)
    op.execute(f'ALTER TABLE "{GI_TABLE}" ENABLE ROW LEVEL SECURITY')
    op.execute(REVOKE_PUBLIC_ROLES.replace("{table}", GI_TABLE))
    for statement in restore_statements():
        op.execute(statement)
    op.drop_column("KnowledgePiece", "rebuildTriedAt")
    op.drop_column("Process", "archivedAt")
