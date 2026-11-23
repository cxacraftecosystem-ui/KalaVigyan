from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from app.data.craft_text import INDIC_BLOCKS, SCRIPT_LANG, ascii_key, script_of, to_latin, to_latin_spoken

from alias_entries import GENERIC_WORDS, PROPOSED, TRANSLITERATION, entry

__all__ = [
    "INDIC_SCRIPTS",
    "SCHEMES",
    "STATE_SCRIPTS",
    "common_romanisations",
    "cross_script",
    "latin_forms",
    "latin_to_devanagari",
    "pure_script",
    "transliterations",
    "vocabulary_tokens",
]

SCHEMES: dict[str, str] = {
    "Deva": "devanagari",
    "Beng": "bengali",
    "Guru": "gurmukhi",
    "Gujr": "gujarati",
    "Orya": "oriya",
    "Taml": "tamil",
    "Telu": "telugu",
    "Knda": "kannada",
    "Mlym": "malayalam",
}
STATE_SCRIPTS: dict[str, tuple[str, ...]] = {
    "Andhra Pradesh": ("Telu",),
    "Telangana": ("Telu",),
    "Tamil Nadu": ("Taml",),
    "Puducherry": ("Taml",),
    "Karnataka": ("Knda",),
    "Kerala": ("Mlym",),
    "Gujarat": ("Gujr",),
    "Punjab": ("Guru",),
    "Odisha": ("Orya",),
    "West Bengal": ("Beng",),
    "Tripura": ("Beng",),
    "Assam": ("Beng",),
    "Maharashtra": ("Deva",),
    "Goa": ("Deva",),
}
INDIC_SCRIPTS = frozenset(SCHEMES)


def common_romanisations(latin: str) -> list[str]:
    variants = {latin}
    ch = re.sub(r"c(?!h)", "ch", latin)
    variants.add(ch)
    for base in list(variants):
        variants.add(re.sub(r"m(?=[^aeioubpm\s])", "n", base))
    return sorted(v for v in variants if v)


def latin_forms(alias: str) -> list[str]:
    forms: list[str] = []
    for base in (to_latin(alias), to_latin_spoken(alias)):
        forms.extend(common_romanisations(ascii_key(base)))
    seen: set[str] = set()
    return [f for f in forms if f and not (f in seen or seen.add(f))]


def cross_script(alias: str, target: str) -> str | None:
    from indic_transliteration import sanscript

    source = script_of(alias)
    if source not in SCHEMES or target not in SCHEMES or source == target:
        return None
    if "Deva" not in (source, target):
        return None
    try:
        out = sanscript.transliterate(alias, SCHEMES[source], SCHEMES[target])
    except KeyError, ValueError:
        return None
    return out if out and out != alias and pure_script(out, target) else None


def pure_script(text: str, script: str) -> bool:
    base = next(b for b, name in INDIC_BLOCKS.items() if name == script)
    for ch in text:
        if ch.isspace() or ch in "()-.,'\u200c\u200d":
            continue
        if not base <= ord(ch) < base + 0x80:
            return False
    return True


def latin_to_devanagari(name: str, vocabulary: frozenset[str]) -> str | None:
    from indic_transliteration import sanscript

    tokens = [t for t in ascii_key(name).split() if t in vocabulary and t not in GENERIC_WORDS]
    if not tokens:
        return None
    words = [sanscript.transliterate(t, sanscript.ITRANS, sanscript.DEVANAGARI).removesuffix("\u094d") for t in tokens]
    out = " ".join(words)
    return out if script_of(out) == "Deva" else None


def vocabulary_tokens(text: str) -> frozenset[str]:
    tokens: set[str] = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        tokens.update(t for t in ascii_key(line).split() if len(t) > 2)
    return frozenset(tokens)


def transliterations(
    aliases: list[dict[str, Any]], states: Iterable[str], name: str, vocabulary: frozenset[str]
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    targets: set[str] = {"Deva"}
    for state in states:
        targets.update(STATE_SCRIPTS.get(state, ()))
    indic = [a for a in aliases if a["script"] in INDIC_SCRIPTS]
    for alias in indic:
        lang = alias.get("lang") or SCRIPT_LANG.get(alias["script"])
        for form in latin_forms(alias["alias"]):
            made = entry(form, TRANSLITERATION, lang=f"{lang}-Latn", via=f"{alias['script']}-to-Latn")
            if made:
                out.append(made)
        for target in sorted(targets):
            converted = cross_script(alias["alias"], target)
            if converted:
                made = entry(
                    converted,
                    TRANSLITERATION,
                    lang=SCRIPT_LANG[target],
                    status=PROPOSED,
                    via=f"{alias['script']}-to-{target}",
                )
                if made:
                    out.append(made)
    if not any(a["script"] == "Deva" for a in indic):
        deva = latin_to_devanagari(name, vocabulary)
        if deva:
            made = entry(deva, TRANSLITERATION, lang="hi", status=PROPOSED, via="Latn-to-Deva")
            if made:
                out.append(made)
    return out
