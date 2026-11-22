import argparse
import asyncio
import json
import os
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.db import dispose_engine, session_scope
from app.core.errors import InvalidInput
from app.services.open_data import Publication, build_release, latest_release, record_release
from app.services.open_data_deposit import checked_scope, deposit_files, read_release_folder
from app.services.open_data_release import ReleaseStamp, checked_craft, released_on
from app.services.open_data_scope import WHOLE, ReleaseScope
from app.services.open_data_slice import craft_slice
from app.services.open_data_zenodo import ZenodoDeposit, deposit_metadata

RESULT_MARK = "OPEN_DATA_RESULT"
TOKEN_VARIABLE = "ZENODO_TOKEN"
ZENODO_TIMEOUT = httpx.Timeout(60.0, write=600.0)
NAMELESS_CRAFT = "A craft release's draft takes --craft-name, the name the latest step printed for the craft."


async def _latest(args: argparse.Namespace) -> dict[str, Any]:
    async with session_scope() as session:
        scope = (await craft_slice(session, args.craft)).scope if args.craft is not None else WHOLE
        found = await latest_release(session, args.target, craft=scope.craft)
    craft = None if scope.craft is None else {"slug": scope.craft, "name": scope.name, "title": scope.title}
    if found is None:
        return {"latest": None, "craft": craft}
    return {
        "latest": {
            "version": found.version,
            "recordId": found.recordId,
            "conceptRecordId": found.conceptRecordId,
            "doi": found.doi,
            "conceptDoi": found.conceptDoi,
        },
        "craft": craft,
    }


async def _build(args: argparse.Namespace) -> dict[str, Any]:
    stamp = ReleaseStamp(
        target=args.target,
        version=args.version,
        doi=args.doi,
        concept_doi=args.concept_doi,
        record_id=args.record_id,
        concept_record_id=args.concept_record_id,
        craft=args.craft,
    )
    site = get_settings().public_web_url.rstrip("/")
    async with session_scope() as session:
        built = await build_release(session, stamp, site=site)
    args.out.mkdir(parents=True, exist_ok=True)
    for name, body in built.files.files.items():
        (args.out / name).write_bytes(body)
    return built.summary()


async def _record(args: argparse.Namespace) -> dict[str, Any]:
    publication = Publication(
        target=args.target,
        version=args.version,
        doi=args.doi,
        record_url=args.record_url,
        published_at=datetime.fromisoformat(args.published_at),
        craft=args.craft,
    )
    async with session_scope() as session:
        release = await record_release(session, publication)
    return {
        "version": release.version,
        "craft": release.scope,
        "doi": release.doi,
        "recordUrl": release.recordUrl,
        "state": release.state,
    }


def _draft(args: argparse.Namespace) -> dict[str, Any]:
    metadata = deposit_metadata(
        version=args.version,
        released=released_on(args.version),
        counts={},
        site=args.site,
        scope=_named_scope(args.craft, args.craft_name),
    )
    with httpx.Client(timeout=ZENODO_TIMEOUT) as client:
        zenodo = ZenodoDeposit(client, target=args.target, token=os.environ.get(TOKEN_VARIABLE, ""))
        return zenodo.open_draft(args.latest_record, metadata).as_dict()


def _deposit(args: argparse.Namespace) -> dict[str, Any]:
    folder = checked_scope(read_release_folder(args.files), args.craft)
    with httpx.Client(timeout=ZENODO_TIMEOUT) as client:
        zenodo = ZenodoDeposit(client, target=args.target, token=os.environ.get(TOKEN_VARIABLE, ""))
        return deposit_files(zenodo, folder, record_id=args.record_id, publish=args.publish, site=args.site)


def _named_scope(craft: str | None, name: str | None) -> ReleaseScope:
    if checked_craft(craft) is None:
        return WHOLE
    if not name or not name.strip():
        raise InvalidInput(NAMELESS_CRAFT)
    return ReleaseScope(craft=craft, name=name.strip())


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="build_open_data",
        description="Build KalaVigyan's open data release and deposit it on Zenodo (docs/contracts/open-data.md).",
    )
    steps = parser.add_subparsers(dest="step", required=True)
    latest = steps.add_parser("latest", help="print the latest published release of a target and scope")
    _target(latest)
    draft = steps.add_parser("draft", help="open a Zenodo draft and reserve its DOI")
    _target(draft)
    draft.add_argument("--version", required=True)
    draft.add_argument("--site", required=True, help="the site's address, for the dataset's page")
    draft.add_argument("--latest-record", type=int, default=None, help="the scope's latest published record")
    draft.add_argument("--craft-name", default=None, help="the craft's name, as the latest step printed it")
    build = steps.add_parser("build", help="build the release files from the database")
    _target(build)
    for name in ("--version", "--doi", "--concept-doi"):
        build.add_argument(name, required=True)
    build.add_argument("--record-id", type=int, required=True)
    build.add_argument("--concept-record-id", type=int, required=True)
    build.add_argument("--out", type=Path, required=True, help="an empty folder for the release files")
    deposit = steps.add_parser("deposit", help="upload the release files to the draft and publish it")
    _target(deposit)
    deposit.add_argument("--record-id", type=int, required=True)
    deposit.add_argument("--files", type=Path, required=True)
    deposit.add_argument("--site", required=True)
    deposit.add_argument("--publish", action="store_true", help="publish the draft once its files are up")
    record = steps.add_parser("record", help="record a published release's DOI and address")
    _target(record)
    for name in ("--version", "--doi", "--record-url", "--published-at"):
        record.add_argument(name, required=True)
    return parser


def _target(step: argparse.ArgumentParser) -> None:
    step.add_argument("--target", required=True, choices=("SANDBOX", "ZENODO"))
    step.add_argument("--craft", default=None, help="a craft's slug, for a release of that craft alone")


async def _with_database(
    work: Callable[[argparse.Namespace], Any], args: argparse.Namespace
) -> dict[str, Any]:
    try:
        result: dict[str, Any] = await work(args)
        return result
    finally:
        await dispose_engine()


DATABASE_STEPS = {"latest": _latest, "build": _build, "record": _record}
ZENODO_STEPS = {"draft": _draft, "deposit": _deposit}


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.step in DATABASE_STEPS:
        result = asyncio.run(_with_database(DATABASE_STEPS[args.step], args))
    else:
        result = ZENODO_STEPS[args.step](args)
    print(f"{RESULT_MARK} {json.dumps(result, ensure_ascii=False, default=str)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
