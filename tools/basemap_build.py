from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
INDIA = Path("frontend/components/map/indiaGeometry.ts")
OUTPUT = Path("frontend/public/boundaries/neighbours.json")
RANN = Path("frontend/components/map/rannGeometry.ts")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build the map's neighbouring land, coasts, borders and the Rann salt flat from Natural Earth 1:10m, "
            "fitted to the Survey of India outline. Needs shapely and pyogrio (the etl/geo environment)."
        )
    )
    parser.add_argument(
        "natural_earth",
        type=Path,
        help="folder holding each dataset's zip and its unzipped folder (see basemap/build.py DATASETS)",
    )
    parser.add_argument(
        "--root", type=Path, default=REPO_ROOT, help="repository root to read from and write into"
    )
    options = parser.parse_args(argv)
    from basemap.build import Datasets, render

    india_source = (options.root / INDIA).read_text(encoding="utf-8")
    body, rann = render(Datasets(options.natural_earth), india_source)
    for path, text in ((OUTPUT, body), (RANN, rann)):
        (options.root / path).write_text(text, encoding="utf-8", newline="\n")
        print(f"{path.as_posix()} written, {len(text.encode('utf-8'))} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
