from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

__all__ = [
    "PUBLIC_SUFFIX_FILE",
    "PublicSuffixes",
    "load_public_suffixes",
    "parse_public_suffixes",
    "registrable_name",
]

PUBLIC_SUFFIX_FILE = Path(__file__).with_name("public_suffix_list.dat")
COMMENT = "//"
WILDCARD = "*."
EXCEPTION = "!"
ACE_PREFIX = "xn--"


@dataclass(frozen=True)
class PublicSuffixes:
    rules: frozenset[str]
    wildcards: frozenset[str]
    exceptions: frozenset[str]

    def suffix_labels(self, labels: Sequence[str]) -> int:
        for start in range(len(labels)):
            if ".".join(labels[start:]) in self.exceptions:
                return len(labels) - start - 1
        for start in range(len(labels)):
            if ".".join(labels[start:]) in self.rules or self._wildcard_at(labels, start):
                return len(labels) - start
        return 1

    def registrable(self, host: str) -> str | None:
        labels = [_unicode_label(label) for label in host.casefold().rstrip(".").split(".")]
        if not labels or not all(labels):
            return None
        size = self.suffix_labels(labels)
        if len(labels) <= size:
            return None
        return ".".join(labels[-(size + 1) :])

    def _wildcard_at(self, labels: Sequence[str], start: int) -> bool:
        return start + 1 < len(labels) and ".".join(labels[start + 1 :]) in self.wildcards


def parse_public_suffixes(lines: Iterable[str]) -> PublicSuffixes:
    rules: set[str] = set()
    wildcards: set[str] = set()
    exceptions: set[str] = set()
    for line in lines:
        words = line.split()
        if not words or words[0].startswith(COMMENT):
            continue
        rule = words[0].casefold()
        if rule.startswith(EXCEPTION):
            exceptions.add(rule.removeprefix(EXCEPTION))
        elif rule.startswith(WILDCARD):
            wildcards.add(rule.removeprefix(WILDCARD))
        else:
            rules.add(rule)
    if not rules:
        raise ValueError(f"{PUBLIC_SUFFIX_FILE.name} holds no rules")
    return PublicSuffixes(frozenset(rules), frozenset(wildcards), frozenset(exceptions))


@lru_cache(maxsize=1)
def load_public_suffixes() -> PublicSuffixes:
    return parse_public_suffixes(PUBLIC_SUFFIX_FILE.read_text(encoding="utf-8").splitlines())


def registrable_name(host: str) -> str | None:
    return load_public_suffixes().registrable(host)


def _unicode_label(label: str) -> str:
    if not label.startswith(ACE_PREFIX):
        return label
    try:
        return label.encode("ascii").decode("idna")
    except UnicodeError:
        return label
