from __future__ import annotations

import re
from collections.abc import Sequence

__all__ = ["CLAUSE_BREAK", "CUE_GAP_MAX", "carried_there"]

CUE_GAP_MAX = 3
CLAUSE_BREAK = re.compile(r"[.;:!?()\[\]]")
ORIGIN_CUES = frozenset(
    {
        "from",
        "imported",
        "import",
        "imports",
        "mined",
        "quarried",
        "sourced",
        "brought",
        "obtained",
        "procured",
    }
)
TRADE_CUES = frozenset(
    {
        "exported",
        "export",
        "exports",
        "traded",
        "trade",
        "shipped",
        "sold",
        "reached",
        "excavated",
        "unearthed",
    }
)
FOUND_CUES = frozenset({("been", "found"), ("were", "found"), ("was", "found"), ("been", "discovered")})
CLAUSE_WORDS = frozenset(
    {
        "that",
        "which",
        "who",
        "whom",
        "whose",
        "when",
        "where",
        "while",
        "because",
        "if",
        "but",
        "so",
        "then",
        "although",
        "though",
        "whereas",
        "unlike",
        "like",
        "after",
        "before",
        "since",
        "until",
    }
)


def carried_there(before: Sequence[str]) -> bool:
    for gap in range(min(CUE_GAP_MAX, len(before) - 1) + 1):
        at = len(before) - 1 - gap
        word = before[at]
        if word in CLAUSE_WORDS:
            return False
        if word in ORIGIN_CUES or word in TRADE_CUES:
            return True
        if at > 0 and (before[at - 1], word) in FOUND_CUES:
            return True
    return False
