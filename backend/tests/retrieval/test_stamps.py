import ast
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.models import Chunk, Claim, KnowledgePiece
from app.models.crafts import EMBEDDING_DIMENSIONS
from app.retrieval.indexing import _vector_values
from app.retrieval.stamps import (
    EMBEDDING_RECIPE,
    RECIPE_MARK,
    made_by_current_model,
    needs_model_vector,
    needs_vector,
    renewal_order,
)
from app.retrieval.statements import (
    CraftScope,
    chunk_conditions,
    chunk_vector_ranking,
    claim_conditions,
    claim_vector_ranking,
)

SCOPE = CraftScope(craft_id=uuid.uuid5(uuid.NAMESPACE_URL, "test-craft/Qorvane-Ikat"), sub_category_id=None)
VECTOR = [0.0] * EMBEDDING_DIMENSIONS
CURRENT = "(SELECT kv_embedding_model() AS kv_embedding_model_1)"
MIGRATION = Path(__file__).resolve().parents[2] / "migrations" / "versions" / "0061_embedding_recipe.py"


def sql_of(statement: Any) -> str:
    return " ".join(str(statement.compile(dialect=postgresql.dialect())).split())


def migration_constants() -> dict[str, object]:
    found: dict[str, object] = {}
    for node in ast.parse(MIGRATION.read_text("utf-8")).body:
        if isinstance(node, ast.AnnAssign | ast.Assign) and isinstance(node.value, ast.Constant):
            target = node.target if isinstance(node, ast.AnnAssign) else node.targets[0]
            if isinstance(target, ast.Name):
                found[target.id] = node.value.value
    return found


def test_the_stamp_is_the_model_and_the_recipe_in_python_and_in_the_migration() -> None:
    held = migration_constants()
    assert (RECIPE_MARK, EMBEDDING_RECIPE) == ("#", "ctx1")
    assert (held["RECIPE_MARK"], held["EMBEDDING_RECIPE"]) == (RECIPE_MARK, EMBEDDING_RECIPE)
    assert held["revision"] == "0061_embedding_recipe" and held["down_revision"] == "0060_reranking"


def test_the_claim_vector_ranking_reads_every_recipe_of_the_routes_current_model() -> None:
    sql = sql_of(claim_vector_ranking(claim_conditions(SCOPE, mode="HYBRID"), VECTOR))
    assert 'split_part("Claim"."embeddingModel", ' in sql
    assert f"= split_part({CURRENT}, " in sql
    assert '"Claim".embedding IS NOT NULL' in sql


def test_the_chunk_vector_ranking_reads_every_recipe_of_the_routes_current_model() -> None:
    sql = sql_of(chunk_vector_ranking(chunk_conditions(SCOPE, mode="HYBRID", acls=("PUBLIC",)), VECTOR))
    assert 'split_part("Chunk"."embeddingModel", ' in sql
    assert f"= split_part({CURRENT}, " in sql


def test_a_run_renews_a_vector_that_is_missing_or_carries_another_stamp() -> None:
    sql = sql_of(select(Claim.id).where(needs_vector(Claim.embedding, Claim.embeddingModel)))
    assert '"Claim".embedding IS NULL OR' in sql
    assert f'"Claim"."embeddingModel" IS DISTINCT FROM {CURRENT}' in sql


def test_a_written_row_is_embedded_only_when_it_has_no_vector_of_the_current_model() -> None:
    statement = select(Claim.id).where(needs_model_vector(Claim.embedding, Claim.embeddingModel))
    compiled = statement.compile(dialect=postgresql.dialect())
    sql = " ".join(str(compiled).split())
    assert '"Claim".embedding IS NULL OR split_part("Claim"."embeddingModel", ' in sql
    assert f"IS DISTINCT FROM split_part({CURRENT}, " in sql
    assert sorted(value for value in compiled.params.values() if value == RECIPE_MARK) == ["#", "#"]


def test_a_current_vector_is_one_of_the_routes_model_whatever_its_recipe() -> None:
    compiled = (
        select(Chunk.id)
        .where(made_by_current_model(Chunk.embeddingModel))
        .compile(dialect=postgresql.dialect())
    )
    sql = " ".join(str(compiled).split())
    assert sql.startswith('SELECT "Chunk".id FROM "Chunk" WHERE split_part("Chunk"."embeddingModel", ')
    assert sorted(str(value) for value in compiled.params.values()) == ["#", "#", "1", "1"]


def test_runs_renew_missing_vectors_then_other_models_then_old_recipes_oldest_first() -> None:
    order = renewal_order(Claim.embedding, Claim.embeddingModel, Claim.updatedAt)
    sql = sql_of(select(Claim.id).order_by(*order, Claim.id))
    assert sql.index('"Claim".embedding IS NOT NULL') < sql.index("coalesce(split_part(")
    assert sql.endswith('"Claim"."updatedAt", "Claim".id')


def test_claims_and_chunks_are_stamped_as_they_are_written_and_pieces_are_not() -> None:
    vector = [1.0] * 3
    claim = _vector_values(Claim, vector)
    assert set(claim) == {"embedding", "embeddingModel"} and claim["embedding"] == vector
    assert "SELECT kv_embedding_model()" in sql_of(claim["embeddingModel"])
    assert set(_vector_values(Chunk, vector)) == {"embedding", "embeddingModel"}
    assert _vector_values(KnowledgePiece, vector) == {"embedding": vector}
