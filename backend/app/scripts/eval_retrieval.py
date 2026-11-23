import argparse
import asyncio
import json
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.db import dispose_engine, session_scope, sessionmaker
from app.core.errors import AppError
from app.core.logging import request_id_scope
from app.providers import router
from app.providers.embedding import router_embedder
from app.providers.judge_routes import thrifty_judges
from app.providers.rerank_router import router_reranker
from app.providers.router import Principal
from app.research.crafts import CraftQuery
from app.research.structured import StructuredModel
from app.retrieval.craft_cases import CaseOutcome, CraftCase, case_report, craft_cases_file, outcome_of
from app.retrieval.deadline import Deadline
from app.retrieval.eval_floors import eval_floors
from app.retrieval.eval_runs import EVAL_CONCURRENCY, EvalTools, QuestionSets, release_run, weekly_run
from app.retrieval.evaluation import GoldenQuestion
from app.retrieval.fusion_settings import fusion_settings, settings_text
from app.retrieval.fusion_sweep import fusion_sweep, picked_settings
from app.retrieval.golden import generated_set, golden_questions
from app.retrieval.miss_judging import MISS_JUDGE_CAP_USD, MISS_JUDGE_TAG, JudgeTools
from app.retrieval.release_check import RELEASE_SECONDS
from app.services.claim_seed import seed_id
from app.services.craft_resolver import CraftIndexStore, DatabaseCraftResolver
from app.services.eval_run_store import (
    RunTimes,
    keep_run,
    release_check_record,
    release_commit,
    weekly_record,
)

SEED_PREFIX = "seed-"
SEARCH_TAG = "eval-search-"
EXIT_FAILED = 1
SPEND_PLACES = Decimal("0.0001")


def golden_claim_id(key: str) -> uuid.UUID:
    return seed_id("claim", key) if key.startswith(SEED_PREFIX) else uuid.UUID(key)


def golden_claim_ids(golden: Sequence[GoldenQuestion]) -> dict[str, uuid.UUID]:
    return {key: golden_claim_id(key) for question in golden for fact in question.facts for key in fact}


def eval_tools() -> EvalTools:
    return EvalTools(
        sessions=sessionmaker(), embed=router_embedder(), rerank=router_reranker(), claim_id=golden_claim_id
    )


def run_tag(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:12]}"


def cheapest_judge() -> StructuredModel:
    return thrifty_judges(Principal()).first


async def spent_since(tag: str, since: datetime) -> Decimal:
    async with session_scope() as session:
        return await router.tagged_spend(session, request_id_prefix=tag, since=since)


async def weekly(cap: Decimal, out: Path | None) -> dict[str, Any]:
    started, tag, searches = datetime.now(UTC), run_tag(MISS_JUDGE_TAG), run_tag(SEARCH_TAG)

    async def spent() -> Decimal:
        return await spent_since(tag, started)

    judge = JudgeTools(judge=cheapest_judge(), spent=spent, tag=tag, cap_usd=cap)
    with request_id_scope(searches):
        run = await weekly_run(
            eval_tools(), QuestionSets(golden_questions(), generated_set()), judge=judge, floors=eval_floors()
        )
    written = None
    if out is not None and run.revised is not None:
        out.write_text(run.revised.model_dump_json(by_alias=True, indent=1) + "\n", encoding="utf-8")
        written = str(out)
    search_spent = (await spent_since(searches, started)).quantize(SPEND_PLACES)
    judge_spent = (await spent()).quantize(SPEND_PLACES)
    record = weekly_record(run, run_times(started), spent_usd=search_spent + judge_spent, cap_usd=cap)
    return {
        **run.as_dict(),
        "searchSpentUsd": str(search_spent),
        "judgeSpentUsd": str(judge_spent),
        "judgeCapUsd": str(cap),
        "out": written,
        **await keep_run(record),
    }


async def release(seconds: float) -> tuple[dict[str, Any], int]:
    started, searches = datetime.now(UTC), run_tag(SEARCH_TAG)
    with request_id_scope(searches):
        check = await release_run(
            eval_tools(),
            QuestionSets(golden_questions(), generated_set()),
            floors=eval_floors(),
            deadline=Deadline.after(seconds),
        )
    spent = (await spent_since(searches, started)).quantize(SPEND_PLACES)
    kept = await keep_run(release_check_record(check, run_times(started), spent_usd=spent))
    return {**check.as_dict(), "searchSpentUsd": str(spent), **kept}, check.exit_code


def run_times(started: datetime) -> RunTimes:
    return RunTimes(started, datetime.now(UTC), release_commit(get_settings().release))


async def crafts() -> dict[str, Any]:
    store, embed, gate = CraftIndexStore(), router_embedder(), asyncio.Semaphore(EVAL_CONCURRENCY)

    async def resolved(case: CraftCase) -> CaseOutcome:
        async with gate, session_scope() as session:
            found = await DatabaseCraftResolver(session, store=store, embed=embed).resolve(
                CraftQuery(text=case.text)
            )
        return outcome_of(case, found)

    outcomes = await asyncio.gather(*(resolved(case) for case in craft_cases_file().cases))
    return {"ok": True, "cases": len(outcomes), "byKind": case_report(outcomes)}


async def fusion(out: Path | None) -> dict[str, Any]:
    current = fusion_settings()
    swept = await fusion_sweep(
        eval_tools(), QuestionSets(golden_questions(), generated_set()), current=current
    )
    written = None
    if out is not None:
        out.write_text(settings_text(picked_settings(swept, at=datetime.now(UTC))), encoding="utf-8")
        written = str(out)
    return {**swept.as_dict(), "out": written}


async def run(arguments: argparse.Namespace) -> tuple[dict[str, Any], int]:
    try:
        if arguments.release:
            return await release(arguments.seconds)
        if arguments.crafts:
            return await crafts(), 0
        if arguments.fusion:
            return await fusion(arguments.out), 0
        return await weekly(min(arguments.cap, MISS_JUDGE_CAP_USD), arguments.out), 0
    except AppError as error:
        return {"ok": False, "error": str(error)}, EXIT_FAILED
    finally:
        await dispose_engine()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="eval_retrieval")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--release", action="store_true", help="score the release sample against the floors")
    mode.add_argument("--crafts", action="store_true", help="score the craft resolver on the matching cases")
    mode.add_argument(
        "--fusion", action="store_true", help="score each weighting of the first-stage fusion, read-only"
    )
    parser.add_argument(
        "--seconds", type=float, default=RELEASE_SECONDS, help="the release check's time budget"
    )
    parser.add_argument("--cap", type=Decimal, default=MISS_JUDGE_CAP_USD, help="the judge's US dollar cap")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="write the next generated set's revision, or the picked fusion, here",
    )
    report, code = asyncio.run(run(parser.parse_args(argv)))
    print(json.dumps(report, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
