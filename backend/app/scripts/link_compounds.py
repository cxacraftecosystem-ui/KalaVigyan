import asyncio
import json
from typing import Any

from app.core.db import dispose_engine, sessionmaker
from app.services.compound_lookup import link_compounds, pubchem_finder
from app.services.live_sources import live_source_client


async def run() -> dict[str, Any]:
    try:
        async with live_source_client() as client:
            pubchem = pubchem_finder(client)
            report = await link_compounds(sessionmaker(), pubchem, now=pubchem.clock())
    finally:
        await dispose_engine()
    return report.as_dict()


def main() -> int:
    report = asyncio.run(run())
    print(json.dumps(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
