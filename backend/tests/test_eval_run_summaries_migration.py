from app.models import EvalRun
from app.models.evaluation import EVAL_RUN_KINDS

from .migration_scripts import migration

STEP = migration("0094_eval_run_summaries")
CREATED = migration("0001_initial_schema")


def test_it_follows_round_7s_head() -> None:
    assert (STEP.revision, STEP.down_revision) == ("0094_eval_run_summaries", "0097_chunk_kinds")


def test_it_reuses_the_eval_run_table_the_first_schema_made_and_no_code_wrote() -> None:
    assert STEP.RUNS == "EvalRun" == EvalRun.__tablename__
    assert STEP.RUNS in CREATED.TABLES


def test_the_kinds_it_allows_are_the_ones_the_store_writes() -> None:
    assert STEP.KINDS == EVAL_RUN_KINDS == ("ANSWERS", "RETRIEVAL", "RELEASE_CHECK")
    names = {str(constraint.name) for constraint in EvalRun.__table__.constraints}
    assert STEP.KIND_CHECK in names
    assert STEP.FINISHED_INDEX == "EvalRun_suite_finishedAt_idx"


def test_the_release_before_writes_a_run_without_the_new_columns() -> None:
    columns = EvalRun.__table__.columns
    assert columns["floorsHeld"].nullable is True
    assert columns["fresh"].nullable is False and columns["fresh"].server_default is not None
