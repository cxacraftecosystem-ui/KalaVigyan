from __future__ import annotations

import argparse
import sys
from pathlib import Path

from design.build import render
from design.system import load_system

REPO_ROOT = Path(__file__).resolve().parents[1]
REFERENCES = Path(".claude/skills/kalavigyan-design/references")
DESTINATIONS = {
    "tokens.json": (REFERENCES / "tokens.json", Path("backend/app/data/design/tokens.json")),
    "tokens.css": (REFERENCES / "tokens.css", Path("frontend/app/tokens.css")),
    "tailwind.config.ts": (REFERENCES / "tailwind.config.ts",),
}


def stale_outputs(root: Path, outputs: dict[str, str]) -> list[Path]:
    stale = []
    for name, paths in DESTINATIONS.items():
        for path in paths:
            target = root / path
            if not target.is_file() or target.read_text(encoding="utf-8") != outputs[name]:
                stale.append(path)
    return stale


def write_outputs(root: Path, outputs: dict[str, str]) -> None:
    for name, paths in DESTINATIONS.items():
        for path in paths:
            (root / path).write_text(outputs[name], encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the design tokens from tools/design/system.json.")
    parser.add_argument(
        "--check", action="store_true", help="fail when a written output differs from the generator"
    )
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="repository root to write into")
    options = parser.parse_args(argv)
    outputs, violations = render(load_system())
    if violations:
        print("design tokens REFUSED:", *violations, sep="\n  ", file=sys.stderr)
        return 1
    if options.check:
        stale = stale_outputs(options.root, outputs)
        for path in stale:
            print(f"stale: {path.as_posix()}; run python tools/design_tokens.py", file=sys.stderr)
        return 1 if stale else 0
    write_outputs(options.root, outputs)
    print("design tokens written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
