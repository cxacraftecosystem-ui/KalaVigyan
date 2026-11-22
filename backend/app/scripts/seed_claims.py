import argparse
import asyncio
import json
from typing import Any

from app.services.claim_seed import claim_seed_plan, load_seed_claims
from app.services.claim_seed_passages import seed_passages
from app.services.science_seed import load_science_seed, science_seed_plan


async def run() -> dict[str, Any]:
    from app.core.db import dispose_engine, session_scope
    from app.services.claim_seed import seed_claims
    from app.services.claim_seed_passages import store_seed_passages
    from app.services.curation_seed_rows import retire_curated_seed_rows
    from app.services.science_seed import seed_science
    from app.services.term_glossary import seed_terms

    data = load_seed_claims()
    try:
        async with session_scope() as session:
            claims = await seed_claims(session, data)
            passages = await store_seed_passages(session, data)
            science = await seed_science(session)
            terms = await seed_terms(session)
            retired = await retire_curated_seed_rows(session)
            return {**claims, "passages": passages, "science": science, "terms": terms} | {
                "retiredSeedRows": retired.summary()
            }
    finally:
        await dispose_engine()


def dry_run() -> dict[str, Any]:
    data = load_seed_claims()
    plan = claim_seed_plan(data)
    science = science_seed_plan(load_science_seed(), data)
    return {
        "total": {key: len(rows) for key, rows in plan.items()},
        "passages": sum(len(passages.chunks) for passages in seed_passages(data)),
        "science": science.totals(),
        "dryRun": True,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="seed_claims")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    result = dry_run() if args.dry_run else asyncio.run(run())
    print(json.dumps(result))
    if result.get("unresolvedSlugs"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
