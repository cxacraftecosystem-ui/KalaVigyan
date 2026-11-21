from __future__ import annotations

import argparse
import sys
from pathlib import Path

from hygiene.check import project_files
from repo_facts.counts import OUTPUT, Repo, gather
from repo_facts.render import render

REPO_ROOT = Path(__file__).resolve().parents[1]


def facts_text(root: Path) -> str:
    return render(gather(Repo(root, tuple(project_files(root)))))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"Write {OUTPUT}, the counts that change with the code.")
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="repository root to count")
    parser.add_argument("--check", action="store_true", help="fail when the file differs from a fresh count")
    options = parser.parse_args(argv)
    root = options.root.resolve()
    text = facts_text(root)
    target = root / OUTPUT
    if options.check:
        current = target.read_text(encoding="utf-8") if target.exists() else ""
        if current == text:
            print(f"{OUTPUT} is current")
            return 0
        print(f"{OUTPUT} is out of date; run tools/repo_facts_build.py", file=sys.stderr)
        return 1
    target.write_text(text, encoding="utf-8", newline="\n")
    print(f"{OUTPUT} written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
