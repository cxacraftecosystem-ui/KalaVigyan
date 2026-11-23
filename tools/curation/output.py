from __future__ import annotations

import sys
from pathlib import Path

from atomic_write import write_text_atomically

__all__ = ["BACKEND", "REPO_ROOT", "relative_label", "utf8_console", "write_text_atomically"]

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"


def relative_label(path: Path) -> str:
    resolved = path.resolve()
    return resolved.relative_to(REPO_ROOT).as_posix() if resolved.is_relative_to(REPO_ROOT) else str(path)


def utf8_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8")
