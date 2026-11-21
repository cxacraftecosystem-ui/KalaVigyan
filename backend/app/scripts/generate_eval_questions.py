import argparse
import asyncio
import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.core.db import dispose_engine, session_scope, sessionmaker
from app.core.errors import AppError
from app.data.state_languages import load_state_languages
from app.retrieval.golden import GENERATED_FILE, GENERATED_SCHEMA_FILE, generated_schema_text, generated_set
from app.retrieval.question_facts import FactSampling, craft_fact_sets, eval_crafts
from app.retrieval.question_generation import (
    GENERATION_CAP_USD,
    GENERATION_TAG,
    GenerationPlan,
    WritingTools,
    generate_questions,
)
from app.scripts.eval_retrieval import cheapest_judge, spent_since

CENT = Decimal("0.0001")


async def generate(cap: Decimal, out: Path, previous_file: Path) -> dict[str, Any]:
    started, tag = datetime.now(UTC), f"{GENERATION_TAG}{uuid.uuid4().hex[:12]}"

    async def spent() -> Decimal:
        return await spent_since(tag, started)

    plan = GenerationPlan(cap_usd=cap)
    previous = generated_set(previous_file)
    sampling = FactSampling(seed=plan.seed, per_craft=plan.per_craft, state_languages=load_state_languages())
    async with session_scope() as session:
        crafts = await eval_crafts(session)
    outcome = await generate_questions(
        craft_fact_sets(sessionmaker(), crafts, sampling),
        WritingTools(write=cheapest_judge(), spent=spent, tag=tag),
        plan,
        previous,
    )
    revision = previous.revision + 1 if previous is not None else 1
    generated = outcome.generated(plan, revision=revision, at=started)
    out.write_text(generated.model_dump_json(by_alias=True, indent=1) + "\n", encoding="utf-8")
    spend = (await spent()).quantize(CENT)
    return {
        "ok": True,
        **outcome.summary(),
        "revision": revision,
        "spentUsd": str(spend),
        "capUsd": str(cap),
        "out": str(out),
    }


async def run(cap: Decimal, out: Path, previous_file: Path) -> dict[str, Any]:
    try:
        return await generate(cap, out, previous_file)
    except AppError as error:
        return {"ok": False, "error": str(error)}
    finally:
        await dispose_engine()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="generate_eval_questions")
    parser.add_argument(
        "--cap", type=Decimal, default=GENERATION_CAP_USD, help="spend at most this many US dollars"
    )
    parser.add_argument("--out", type=Path, default=GENERATED_FILE, help="write the generated set here")
    parser.add_argument("--previous", type=Path, default=GENERATED_FILE, help="reuse this set's questions")
    parser.add_argument("--schema", action="store_true", help="write the set's JSON Schema and stop")
    arguments = parser.parse_args(argv)
    if arguments.schema:
        GENERATED_SCHEMA_FILE.write_text(generated_schema_text(), encoding="utf-8", newline="\n")
        print(json.dumps({"ok": True, "schema": str(GENERATED_SCHEMA_FILE)}))
        return 0
    if arguments.cap <= 0:
        parser.error("the cap is a positive number of US dollars")
    report = asyncio.run(run(arguments.cap, arguments.out, arguments.previous))
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
