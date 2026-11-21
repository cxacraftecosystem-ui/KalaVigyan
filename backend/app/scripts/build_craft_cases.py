import argparse
import json
from pathlib import Path

from app.data.craft_master_loader import ACTIVE, load_craft_aliases, load_master
from app.retrieval.craft_cases import CASES_FILE, CraftNames, RecordedName, craft_cases


def craft_names() -> list[CraftNames]:
    recorded = load_craft_aliases().get("crafts", {})
    return [
        CraftNames(
            slug=craft.slug,
            name=craft.name,
            sub_category=craft.sub_category_slug,
            aliases=tuple(
                RecordedName(
                    text=alias["alias"],
                    script=alias.get("script"),
                    source=alias["source"],
                    status=alias.get("status", ACTIVE),
                )
                for alias in (recorded.get(craft.slug) or {}).get("aliases", ())
            ),
        )
        for craft in load_master()
        if not craft.is_catch_all
    ]


def cases_text() -> str:
    cases = craft_cases(craft_names())
    return json.dumps(cases.model_dump(mode="json", by_alias=True), indent=1, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="build_craft_cases")
    parser.add_argument("--out", type=Path, default=CASES_FILE, help="write the craft-matching cases here")
    arguments = parser.parse_args(argv)
    arguments.out.write_text(cases_text(), encoding="utf-8", newline="\n")
    print(json.dumps({"ok": True, "out": str(arguments.out)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
