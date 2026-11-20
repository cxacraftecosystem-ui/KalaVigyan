from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from webfonts.build import build_face, features_of, read_source
from webfonts.ranges import NEWSREADER_FACES

REPO_ROOT = Path(__file__).resolve().parents[1]
FONTS = REPO_ROOT / "frontend" / "fonts"
CACHE = Path(tempfile.gettempdir()) / "kv-webfont-sources"


def report(name: str, before: Path, content: bytes) -> str:
    old = before.stat().st_size if before.is_file() else 0
    return f"{name}: {old} -> {len(content)} bytes; features {' '.join(features_of(content))}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Subset the Newsreader web fonts from the pinned google/fonts sources."
    )
    parser.add_argument("--out", type=Path, default=FONTS, help="folder to write the WOFF2 files into")
    parser.add_argument("--cache", type=Path, default=CACHE, help="folder that keeps the downloaded sources")
    options = parser.parse_args(argv)
    options.out.mkdir(parents=True, exist_ok=True)
    for output in NEWSREADER_FACES:
        source = read_source(output.face, options.cache)
        print(f"{output.face.source}: features {' '.join(features_of(source))}")
        content = build_face(output, source)
        print(report(output.name, FONTS / output.name, content))
        (options.out / output.name).write_bytes(content)
    return 0


if __name__ == "__main__":
    sys.exit(main())
