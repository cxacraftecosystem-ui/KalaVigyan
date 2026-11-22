from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from collections.abc import Iterable
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path("backend/app/data/english_words.scowl.txt")
SCOWL_VERSION = "2020.12.07"
SCOWL_URL = (
    f"https://downloads.sourceforge.net/project/wordlist/SCOWL/{SCOWL_VERSION}/scowl-{SCOWL_VERSION}.tar.gz"
)
LISTS = ("english-words", "american-words", "british-words")
LEVELS = (10, 20, 35, 40, 50)
WORD = re.compile(r"[a-z]{4,}")
HEADER = (
    f"# Ordinary English words: SCOWL {SCOWL_VERSION} ({SCOWL_URL}), the lists",
    f"# {', '.join(LISTS)} at levels {', '.join(map(str, LEVELS))} (size 50, a mid-size",
    "# dictionary), folded to lower-case ASCII, possessives dropped, words of four letters or more.",
    "# Written by tools/english_words_build.py; never edit by hand. Read by",
    "# app/data/english_words.load_english_words.",
    "#",
    "# Copyright 2000-2018 by Kevin Atkinson",
    "#",
    "# Permission to use, copy, modify, distribute and sell these word",
    "# lists, the associated scripts, the output created from the scripts,",
    "# and its documentation for any purpose is hereby granted without fee,",
    "# provided that the above copyright notice appears in all copies and",
    "# that both that copyright notice and this permission notice appear in",
    "# supporting documentation. Kevin Atkinson makes no representations",
    "# about the suitability of this array for any purpose. It is provided",
    '# "as is" without express or implied warranty.',
)


def folded(line: str) -> str:
    decomposed = unicodedata.normalize("NFKD", line.strip())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


def scowl_words(final: Path) -> list[str]:
    found: set[str] = set()
    for name in LISTS:
        for level in LEVELS:
            path = final / f"{name}.{level}"
            if path.exists():
                found.update(_words(path.read_text(encoding="latin-1").splitlines()))
    return sorted(found)


def _words(lines: Iterable[str]) -> Iterable[str]:
    for line in lines:
        word = folded(line)
        if WORD.fullmatch(word):
            yield word


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"Write {OUTPUT} from an unpacked SCOWL release.")
    parser.add_argument("final", type=Path, help=f"the final/ directory of scowl-{SCOWL_VERSION}")
    options = parser.parse_args(argv)
    words = scowl_words(options.final)
    if not words:
        print(f"no SCOWL word lists in {options.final}", file=sys.stderr)
        return 1
    text = "\n".join([*HEADER, *words]) + "\n"
    (REPO_ROOT / OUTPUT).write_text(text, encoding="utf-8", newline="\n")
    print(f"{OUTPUT} written: {len(words)} words")
    return 0


if __name__ == "__main__":
    sys.exit(main())
