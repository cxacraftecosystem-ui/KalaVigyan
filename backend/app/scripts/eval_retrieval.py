import asyncio
import json
import uuid
from collections.abc import Sequence
from typing import Any

from app.core.db import dispose_engine, session_scope, sessionmaker
from app.core.errors import AppError
from app.providers.embedding import router_embedder
from app.retrieval.evaluation import GoldenQuestion, evaluate_golden, visible_claims
from app.retrieval.golden import golden_questions
from app.retrieval.hybrid import SessionScopedSearch
from app.services.claim_seed import seed_id

SEED_PREFIX = "seed-"


def golden_claim_id(key: str) -> uuid.UUID:
    return seed_id("claim", key) if key.startswith(SEED_PREFIX) else uuid.UUID(key)


def golden_claim_ids(golden: Sequence[GoldenQuestion]) -> dict[str, uuid.UUID]:
    return {key: golden_claim_id(key) for question in golden for fact in question.facts for key in fact}


async def run() -> dict[str, Any]:
    try:
        golden = golden_questions()
        ids = golden_claim_ids(golden)
        async with session_scope() as session:
            present = await visible_claims(session, ids.values())
        retriever = SessionScopedSearch(sessionmaker(), embed=router_embedder())
        report = await evaluate_golden(retriever, golden, claim_id=ids.__getitem__, present=present)
    except AppError as error:
        return {"ok": False, "error": str(error)}
    finally:
        await dispose_engine()
    return {"ok": True, **report.as_dict()}


def main() -> int:
    report = asyncio.run(run())
    print(json.dumps(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
