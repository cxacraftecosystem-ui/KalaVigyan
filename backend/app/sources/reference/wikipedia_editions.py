from __future__ import annotations

import json
import re
from pathlib import Path

from app.research.vocabulary import CANONICAL_LANGUAGE

__all__ = ["EDITIONS_SCHEMA_VERSION", "EDITION_CODE", "WIKIPEDIA_EDITIONS_FILE", "wikipedia_editions"]

WIKIPEDIA_EDITIONS_FILE = Path(__file__).with_name("wikipedia_editions.json")
EDITIONS_SCHEMA_VERSION = 1
EDITION_CODE = re.compile(r"[a-z]{2,8}(?:-[a-z]{2,9})*")


def wikipedia_editions(path: Path) -> frozenset[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schemaVersion") != EDITIONS_SCHEMA_VERSION:
        raise ValueError(f"{path.name} is not a schema version {EDITIONS_SCHEMA_VERSION} list of editions")
    editions = payload.get("editions")
    if not isinstance(editions, list) or not editions:
        raise ValueError(f"{path.name} lists no editions")
    malformed = [code for code in editions if not isinstance(code, str) or not EDITION_CODE.fullmatch(code)]
    if malformed:
        raise ValueError(f"{path.name} has malformed edition codes: {malformed}")
    if editions != sorted(set(editions)):
        raise ValueError(f"{path.name} lists each edition once, in order")
    if CANONICAL_LANGUAGE not in editions:
        raise ValueError(f"{path.name} lacks the {CANONICAL_LANGUAGE} Wikipedia")
    return frozenset(editions)
