import argparse
import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from app.core.db import dispose_engine, session_scope, sessionmaker
from app.core.shielded import ShieldedWork
from app.models import Answer
from app.providers import router
from app.providers.answer_routes import answer_models
from app.providers.embedding import router_embedder
from app.providers.router import Principal
from app.providers.structured import router_structured_model
from app.research.explainer import Explainer
from app.research.mcp_ask import ASK_TIMEOUT_SECONDS
from app.services.ai_providers import AiTask
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
from app.services.explainer_payload import stored_explainer
from app.services.live_sources import LiveSourcesStore

TIMED_OUT = "the answer did not finish within {seconds} seconds"
INDEX = CraftIndexStore()


@asynccontextmanager
async def eval_pipeline(depth: str) -> AsyncIterator[AnswerPipeline]:
    live, shield = LiveSourcesStore(), ShieldedWork()
    system = Principal()
    try:
        yield build_answer_pipeline(
            sessions=sessionmaker(),
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


async def explainer(answer_id: uuid.UUID) -> Explainer | None:
    async with session_scope() as session:
        payload = await session.scalar(select(Answer.payload).where(Answer.id == answer_id))
    return stored_explainer(answer_id, payload)


async def spent_since(request_id_prefix: str, since: datetime) -> Decimal:
    async with session_scope() as session:
        return await router.tagged_spend(session, request_id_prefix=request_id_prefix, since=since)


async def run(*, only: list[str], limit: int | None, cap: Decimal) -> dict[str, Any]:
    every = load_questions().questions
    questions = [q for q in every if not only or q.id in only][:limit]
    tools = EvalTools(
        answer=answer,
        explainer=explainer,
        judge=router_structured_model(AiTask.EVAL_JUDGE),
        spent=spent_since,
    )
    try:
        report = await run_answer_eval(questions, tools, started_at=datetime.now(UTC), cap_usd=cap)
    finally:
        await dispose_engine()
    whole = len(questions) == len(every)
    return {**report.model_dump(mode="json", by_alias=True), **floor_report(report, whole=whole)}


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
    args = parser.parse_args(argv)
    report = asyncio.run(run(only=list(args.only), limit=args.limit, cap=args.cap))
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["answered"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
