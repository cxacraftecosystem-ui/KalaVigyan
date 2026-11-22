from __future__ import annotations

from collections.abc import Iterable
from functools import lru_cache

from .craft_master_loader import DATA_DIR

__all__ = ["ENGLISH_WORDS_FILE", "load_english_words", "parse_english_words"]

ENGLISH_WORDS_FILE = DATA_DIR / "english_words.scowl.txt"
COMMENT = "#"


def parse_english_words(lines: Iterable[str]) -> frozenset[str]:
    words = frozenset(word for line in lines if (word := line.strip()) and not word.startswith(COMMENT))
    if not words:
        raise ValueError(f"{ENGLISH_WORDS_FILE.name} holds no words")
    unfolded = sorted(word for word in words if not (word.isascii() and word.isalpha() and word.islower()))
    if unfolded:
        raise ValueError(
            f"{ENGLISH_WORDS_FILE.name} holds words not folded to lower-case ASCII: {unfolded[:5]}"
        )
    return words


@lru_cache(maxsize=1)
def load_english_words() -> frozenset[str]:
    return parse_english_words(ENGLISH_WORDS_FILE.read_text(encoding="utf-8").splitlines())
