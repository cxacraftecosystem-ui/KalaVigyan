import argparse
import json
from pathlib import Path
from typing import Any

from app.data.craft_master_loader import DATA_DIR
from app.services.document_components_homes import authored_homes
from app.services.document_kit_defs import kit_defs, kit_style_references

__all__ = ["DEFS_FILE", "HOMES_FILE", "defs_text", "homes_text", "main"]

HOMES_FILE = DATA_DIR.parents[2] / "frontend" / "lib" / "componentHomes.ts"
DEFS_FILE = DATA_DIR.parents[2] / "frontend" / "generated" / "kitDefs.ts"
TYPES = (
    "export type FrameStep = { classes: string[]; box: boolean; attrs?: Readonly<Record<string, string>> };\n"
    "export type HomeRecord = { kind: string; scope: string | null; frame: FrameStep[]; root: string | null; "
    "within?: string };\n"
    "export type KindRecord = { scope: string | null; keys: string[] };\n"
    "export type HomeBook = { homes: Readonly<Record<string, HomeRecord>>; "
    "kinds: Readonly<Record<string, KindRecord[]>> };\n"
)


def _entries(values: dict[str, Any]) -> str:
    return ",\n".join(
        f"    {json.dumps(key)}: {json.dumps(value, ensure_ascii=False)}" for key, value in values.items()
    )


def homes_text() -> str:
    body = authored_homes()
    return (
        f"{TYPES}\n"
        "export const COMPONENT_HOMES: HomeBook = {\n"
        f"  homes: {{\n{_entries(body['homes'])}\n  }},\n"
        f"  kinds: {{\n{_entries(body['kinds'])}\n  }}\n"
        "};\n"
    )


def defs_text() -> str:
    return (
        "export type KitDef = { scope: string | null; markup: string };\n\n"
        f"export const KIT_DEFS: Readonly<Record<string, KitDef>> = {{\n{_entries(kit_defs())}\n}};\n\n"
        "export const KIT_STYLE_REFERENCES: Readonly<Record<string, readonly string[]>> = "
        f"{json.dumps(kit_style_references())};\n"
    )


def _written(file: Path, text: str, *, check: bool) -> bool:
    current = file.read_bytes().decode("utf-8") if file.is_file() else None
    if check:
        return current == text
    file.write_bytes(text.encode("utf-8"))
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="write_component_homes")
    parser.add_argument(
        "--check", action="store_true", help="fail when the committed homes or kit defs differ from the build"
    )
    args = parser.parse_args(argv)
    outcomes = {
        str(file): _written(file, text, check=args.check)
        for file, text in ((HOMES_FILE, homes_text()), (DEFS_FILE, defs_text()))
    }
    ok = all(outcomes.values())
    print(json.dumps({"ok": ok, "checked" if args.check else "written": outcomes}))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
