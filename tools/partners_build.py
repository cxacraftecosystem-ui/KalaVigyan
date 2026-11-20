from __future__ import annotations

import argparse
import sys
from pathlib import Path

from partners.raster import web_mark
from partners.svg import minified_svg

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path("frontend/public/partners")
SVG_GRID = 0.1
WEB_WIDTH = 600
WEB_QUALITY = 100


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Write the partners' marks for the landing at web weight: the IIT Kharagpur SVG minified "
        "and the Development Commissioner (Handicrafts) mark as a trimmed WebP. Needs Pillow (the backend environment)."
    )
    parser.add_argument("iit_svg", type=Path, help="IIT_Kharagpur_Logo.svg as supplied by the owner")
    parser.add_argument("handicrafts_png", type=Path, help="DC-Handicrafts-logo.png as supplied by the owner")
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="repository root to write into")
    options = parser.parse_args(argv)
    folder = options.root / OUTPUT
    folder.mkdir(parents=True, exist_ok=True)
    svg = minified_svg(options.iit_svg.read_text(encoding="utf-8"), SVG_GRID)
    (folder / "iit-kharagpur.svg").write_text(svg, encoding="utf-8", newline="\n")
    webp, size = web_mark(options.handicrafts_png, WEB_WIDTH, WEB_QUALITY)
    (folder / "dc-handicrafts.webp").write_bytes(webp)
    print(
        f"iit-kharagpur.svg {len(svg.encode('utf-8'))} bytes; dc-handicrafts.webp {len(webp)} bytes at {size}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
