import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from app.core.db import dispose_engine, session_scope
from app.research.category_page import contract_text
from app.research.craft_page import craft_page_text
from app.services.category_import import import_categories
from app.services.category_preview import category_list_preview, category_page_preview
from app.services.chapter_preview import chapter_preview
from app.services.craft_page_preview import register_page
from app.services.curation_import import import_curation
from app.services.curation_retire import retire_dossier


async def run() -> dict[str, Any]:
    try:
        async with session_scope() as session:
            report = await import_curation(session)
            categories = await import_categories(session)
            return report.summary() | {"categories": categories.summary()}
    finally:
        await dispose_engine()


async def retire(craft_slug: str) -> dict[str, Any]:
    try:
        async with session_scope() as session:
            return (await retire_dossier(session, craft_slug)).summary()
    finally:
        await dispose_engine()


def preview(
    craft_slug: str, out: Path, *, family: str | None = None, inputs: Path | None = None
) -> dict[str, Any]:
    page = chapter_preview(craft_slug, family=family, inputs=inputs)
    out.write_text(craft_page_text(page), encoding="utf-8", newline="\n")
    return {"preview": craft_slug, "out": str(out), "claims": len(page.claims)}


def register_preview(
    craft_slug: str, dossiers: list[str], out: Path, *, family: str | None = None
) -> dict[str, Any]:
    page = register_page(craft_slug, dossiers=dossiers, family=family)
    out.write_text(craft_page_text(page), encoding="utf-8", newline="\n")
    return {"registerPreview": craft_slug, "out": str(out), "relatives": len(page.same_family)}


def category_preview(category_slug: str, dossiers: list[Path], out: Path) -> dict[str, Any]:
    page = category_page_preview(category_slug, dossier=dossiers[0] if dossiers else None)
    out.write_text(contract_text(page), encoding="utf-8", newline="\n")
    return {"categoryPage": category_slug, "out": str(out), "claims": len(page.claims)}


def list_preview(dossiers: list[Path], out: Path) -> dict[str, Any]:
    listing = category_list_preview(dossiers)
    out.write_text(contract_text(listing), encoding="utf-8", newline="\n")
    return {"categoryList": len(listing.categories), "out": str(out), "curated": len(dossiers)}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="import_curation")
    chosen = parser.add_mutually_exclusive_group()
    chosen.add_argument(
        "--preview", metavar="CRAFT_SLUG", help="write a dossier's craft page without a database"
    )
    chosen.add_argument(
        "--register-preview",
        metavar="CRAFT_SLUG",
        help="write the page of a craft without a dossier, without a database",
    )
    chosen.add_argument(
        "--category-page", metavar="CATEGORY_SLUG", help="write a category page without a database"
    )
    chosen.add_argument(
        "--category-list", action="store_true", help="write the category list without a database"
    )
    chosen.add_argument(
        "--retire",
        metavar="CRAFT_SLUG",
        help="un-import a craft whose dossier was removed from the folder: supersede its curated claims and pieces",
    )
    parser.add_argument(
        "--dossier", type=Path, action="append", default=[], help="a category dossier the page or list shows"
    )
    parser.add_argument(
        "--with-dossier",
        metavar="CRAFT_SLUG",
        action="append",
        default=[],
        help="a craft dossier the register preview holds beside the craft",
    )
    parser.add_argument(
        "--family", metavar="CATEGORY_SLUG", help="a family dossier whose science a craft preview borrows"
    )
    parser.add_argument(
        "--inputs", type=Path, help="stored rows the craft preview adds: geo values, conformers, explainers"
    )
    parser.add_argument("--out", type=Path, help="where a preview writes its JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    previewing = args.preview or args.register_preview or args.category_page or args.category_list
    if previewing and args.out is None:
        parser.error("a preview needs --out")
    if args.preview:
        print(json.dumps(preview(args.preview, args.out, family=args.family, inputs=args.inputs)))
        return 0
    if args.register_preview:
        found = register_preview(args.register_preview, args.with_dossier, args.out, family=args.family)
        print(json.dumps(found))
        return 0
    if args.category_page:
        print(json.dumps(category_preview(args.category_page, args.dossier, args.out)))
        return 0
    if args.category_list:
        print(json.dumps(list_preview(args.dossier, args.out)))
        return 0
    if args.retire:
        print(json.dumps(asyncio.run(retire(args.retire))))
        return 0
    result = asyncio.run(run())
    print(json.dumps(result))
    return 2 if result["refused"] or result["categories"]["refused"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
