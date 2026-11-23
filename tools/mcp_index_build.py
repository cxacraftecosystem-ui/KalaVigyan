from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = REPO_ROOT / "backend" / "app" / "data" / "contributor" / "index.md"


def main() -> int:
    parser = argparse.ArgumentParser(description="Write the MCP server's index from its registry.")
    parser.add_argument("--check", action="store_true", help="fail when the written index differs")
    options = parser.parse_args()
    sys.path.insert(0, str(REPO_ROOT / "backend"))
    from app.api.mcp_index import index_text

    text = index_text()
    if options.check:
        same = OUTPUT.read_bytes().decode("utf-8") == text
        print("the index is up to date" if same else f"{OUTPUT} differs from the registry")
        return 0 if same else 1
    OUTPUT.write_bytes(text.encode("utf-8"))
    print(f"wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
