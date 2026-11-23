from __future__ import annotations

import argparse
import sys
from pathlib import Path

from hygiene.baseline import BaselineError
from hygiene.check import project_files, render, run_check
from hygiene.register import RegisterError

REPO_ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Import direction, text encoding, ratcheted size budgets and the debt register's entry count."
    )
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="repository root to check")
    parser.add_argument(
        "--update-baseline", action="store_true", help="record lower counts as the new baseline"
    )
    options = parser.parse_args(argv)
    root = options.root.resolve()
    try:
        report = run_check(root, project_files(root), update_baseline=options.update_baseline)
    except (BaselineError, RegisterError) as error:
        print(f"hygiene check FAILED: {error}", file=sys.stderr)
        return 1
    for line in render(report):
        print(line)
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
