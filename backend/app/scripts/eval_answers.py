import argparse
import asyncio
import json
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import dispose_engine, research_sessionmaker, session_scope
from app.core.shielded import ShieldedWork
from app.models import Answer
from app.providers import router
from app.providers.answer_routes import answer_models
from app.providers.catalogue import AiTask
from app.providers.embedding import router_embedder
from app.providers.router import Principal
from app.providers.structured import router_structured_model
from app.research.explainer import Explainer
from app.research.mcp_ask import ASK_TIMEOUT_SECONDS
from app.services.answer_runs import AnswerRun, answer_to_the_end
from app.services.answer_store import build_answer_pipeline
from app.services.answering import AnswerAsk, AnswerPipeline
from app.services.coverage_eval import (
    EVAL_SPEND_CAP_USD,
    EvalTools,
    floor_report,
    load_questions,
    run_answer_eval,
)
from app.services.craft_resolver import CraftIndexStore
from app.services.eval_run_store import RunTimes, answers_record, keep_run, release_commit
from app.services.explainer_payload import stored_explainer
from app.services.live_sources import LiveSourcesStore
from app.services.off_question import explainer_off_question

TIMED_OUT = "the answer did not finish within {seconds} seconds"
Answering = Callable[[AnswerAsk], Awaitable[AnswerRun]]
INDEX = CraftIndexStore()


@asynccontextmanager
async def eval_pipeline(depth: str) -> AsyncIterator[AnswerPipeline]:
    live, shield = LiveSourcesStore(), ShieldedWork()
    system = Principal()
    try:
        yield build_answer_pipeline(
            sessions=research_sessionmaker(),
            index=INDEX,
            live=live,
            models=answer_models(depth, principal=system, optional=system),
            embed=router_embedder(),
            shield=shield,
        )
    finally:
        await shield.drain()
        await live.aclose()


async def answer(ask: AnswerAsk) -> AnswerRun:
    try:
        async with asyncio.timeout(ASK_TIMEOUT_SECONDS), eval_pipeline(ask.depth) as pipeline:
            return await answer_to_the_end(ask, pipeline)
    except TimeoutError:
        return AnswerRun(answer_id=None, problem=TIMED_OUT.format(seconds=ASK_TIMEOUT_SECONDS))


async def fresh_answer(ask: AnswerAsk) -> AnswerRun:
    return await answer(replace(ask, fresh=True))


async def explainer(answer_id: uuid.UUID) -> Explainer | None:
    async with session_scope() as session:
        payload = await session.scalar(select(Answer.payload).where(Answer.id == answer_id))
    return stored_explainer(answer_id, payload)


async def off_question(found: Explainer, craft_slug: str) -> int:
    async with session_scope() as session:
        return await explainer_off_question(session, INDEX, found, craft_slug)


async def spent_since(request_id_prefix: str, since: datetime) -> Decimal:
    async with session_scope() as session:
        return await router.tagged_settled_spend(session, request_id_prefix=request_id_prefix, since=since)


async def run(
    *, only: list[str], limit: int | None, cap: Decimal, answering: Answering = answer
) -> dict[str, Any]:
    every = load_questions().questions
    questions = [q for q in every if not only or q.id in only][:limit]
    tools = EvalTools(
        answer=answering,
        explainer=explainer,
        judge=router_structured_model(AiTask.EVAL_JUDGE),
        spent=spent_since,
        off_question=off_question,
    )
    whole, fresh = len(questions) == len(every), answering is fresh_answer
    try:
        report = await run_answer_eval(questions, tools, started_at=datetime.now(UTC), cap_usd=cap)
        times = RunTimes(report.started_at, datetime.now(UTC), release_commit(get_settings().release))
        kept = await keep_run(answers_record(report, times, whole=whole, fresh=fresh))
    finally:
        await dispose_engine()
    floors = floor_report(report, whole=whole)
    return {**report.model_dump(mode="json", by_alias=True), "fresh": fresh, **floors, **kept}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="eval_answers")
    parser.add_argument("--only", nargs="*", default=[], help="ask only these question ids")
    parser.add_argument("--limit", type=int, default=None, help="ask at most this many questions")
    parser.add_argument(
        "--cap",
        type=Decimal,
        default=EVAL_SPEND_CAP_USD,
        help="spend at most this many US dollars, never above the cap",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="answer each question afresh, reusing no stored section, as an owner's ask-again does",
    )
    args = parser.parse_args(argv)
    answering = fresh_answer if args.fresh else answer
    report = asyncio.run(run(only=list(args.only), limit=args.limit, cap=args.cap, answering=answering))
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["answered"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
