import argparse
import asyncio
import json
import uuid
from typing import Any

from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import dispose_engine, session_scope
from app.models import User
from app.services.source_titles import junk_titled, producer_authored, retitle_source


async def listed() -> dict[str, list[dict[str, Any]]]:
    try:
        async with session_scope() as session:
            return {
                "titles": [found.as_dict() for found in await junk_titled(session)],
                "authors": [found.as_dict() for found in await producer_authored(session)],
            }
    finally:
        await dispose_engine()


async def retitled(source_id: uuid.UUID, title: str) -> dict[str, Any]:
    try:
        async with session_scope() as session:
            actor = await session.scalar(select(User).where(User.email == get_settings().master_admin_email))
            before = await retitle_source(session, source_id, title, actor=actor)
            await session.commit()
            return {"id": str(source_id), "from": before, "to": title}
    finally:
        await dispose_engine()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="retitle_sources")
    parser.add_argument("--set", dest="source_id", type=uuid.UUID, help="the source whose title is replaced")
    parser.add_argument("--title", help="the work's own title, three words or more")
    args = parser.parse_args(argv)
    if args.source_id is None:
        print(json.dumps(asyncio.run(listed())))
        return 0
    if not args.title:
        parser.error("--set needs --title")
    print(json.dumps(asyncio.run(retitled(args.source_id, args.title))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
