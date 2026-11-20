import argparse
import json
from typing import Any

from app.data.craft_master_loader import DATA_DIR
from app.services.document_components_homes import authored_homes

__all__ = ["HOMES_FILE", "homes_text", "main"]

HOMES_FILE = DATA_DIR.parents[2] / "frontend" / "lib" / "componentHomes.ts"
TYPES = (
    "export type FrameStep = { classes: string[]; box: boolean };\n"
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="write_component_homes")
    parser.add_argument(
        "--check", action="store_true", help="fail when the committed homes differ from the build"
    )
    args = parser.parse_args(argv)
    text = homes_text()
    current = HOMES_FILE.read_bytes().decode("utf-8") if HOMES_FILE.is_file() else None
    if args.check:
        print(json.dumps({"ok": current == text, "file": str(HOMES_FILE)}))
        return 0 if current == text else 1
    HOMES_FILE.write_bytes(text.encode("utf-8"))
    print(json.dumps({"ok": True, "written": str(HOMES_FILE)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
