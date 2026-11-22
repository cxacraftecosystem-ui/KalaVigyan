from __future__ import annotations

import re
import unicodedata
from typing import Any

INDIC_BLOCKS: dict[int, str] = {
    0x0900: "Deva",
    0x0980: "Beng",
    0x0A00: "Guru",
    0x0A80: "Gujr",
    0x0B00: "Orya",
    0x0B80: "Taml",
    0x0C00: "Telu",
    0x0C80: "Knda",
    0x0D00: "Mlym",
}
INDO_ARYAN = frozenset({"Deva", "Beng", "Guru", "Gujr", "Orya"})
SCRIPT_LANG: dict[str, str] = {
    "Deva": "hi",
    "Beng": "bn",
    "Guru": "pa",
    "Gujr": "gu",
    "Orya": "or",
    "Taml": "ta",
    "Telu": "te",
    "Knda": "kn",
    "Mlym": "ml",
}
STOP_TOKENS = frozenset({"craft", "crafts", "work", "works", "art", "arts", "of", "the", "prints", "kala"})

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_ZW = frozenset({"‌", "‍"})


def _indic(cp: int) -> tuple[int, int] | None:
    for base in INDIC_BLOCKS:
        if base <= cp < base + 0x80:
            return base, cp - base
    return None


def _is_consonant(off: int) -> bool:
    return 0x15 <= off <= 0x39 or 0x58 <= off <= 0x5F


def _is_vowel_sign_or_virama(off: int) -> bool:
    return 0x3E <= off <= 0x4D or 0x55 <= off <= 0x57 or off in (0x62, 0x63)


def _is_word_letter(off: int) -> bool:
    return _is_consonant(off) or 0x05 <= off <= 0x14 or 0x01 <= off <= 0x03 or off in (0x60, 0x61)


def script_of(text: Any) -> str:
    counts: dict[str, int] = {}
    for ch in str(text or ""):
        info = _indic(ord(ch))
        if info:
            name = INDIC_BLOCKS[info[0]]
        elif ch.isalpha() and ch.isascii():
            name = "Latn"
        elif ch.isalpha():
            uname = unicodedata.name(ch, "")
            if uname.startswith("LATIN"):
                name = "Latn"
            elif uname.startswith("ARABIC"):
                name = "Arab"
            elif uname.startswith("MEETEI"):
                name = "Mtei"
            elif uname.startswith("OL CHIKI"):
                name = "Olck"
            else:
                name = "Other"
        else:
            continue
        counts[name] = counts.get(name, 0) + 1
    if not counts:
        return "Zyyy"
    return max(sorted(counts), key=lambda k: counts[k])


def indic_inherent_vowels(value: str) -> str:
    chars = [ch for ch in value if not ((info := _indic(ord(ch))) and info[1] == 0x3C)]
    out: list[str] = []
    for i, ch in enumerate(chars):
        out.append(ch)
        info = _indic(ord(ch))
        if info and _is_consonant(info[1]) and i + 1 < len(chars):
            nxt = _indic(ord(chars[i + 1]))
            if nxt and nxt[0] == info[0] and not _is_vowel_sign_or_virama(nxt[1]) and _is_word_letter(nxt[1]):
                out.append("a")
    return "".join(out)


def _units(word: str) -> list[dict[str, Any]]:
    chars = [ch for ch in word if not ((info := _indic(ord(ch))) and info[1] == 0x3C)]
    units: list[dict[str, Any]] = []
    i = 0
    while i < len(chars):
        info = _indic(ord(chars[i]))
        if not info or not _is_consonant(info[1]):
            kind = "V" if info and (0x05 <= info[1] <= 0x14 or info[1] in (0x60, 0x61)) else "X"
            units.append({"head": chars[i], "tail": "", "kind": kind, "nasal": False})
            i += 1
            continue
        head = chars[i]
        i += 1
        kind = "CI"
        tail = ""
        if (
            i < len(chars)
            and (nxt := _indic(ord(chars[i])))
            and nxt[0] == info[0]
            and _is_vowel_sign_or_virama(nxt[1])
        ):
            kind = "CH" if nxt[1] == 0x4D else "CM"
            tail += chars[i]
            i += 1
        nasal = False
        while (
            i < len(chars) and (nxt := _indic(ord(chars[i]))) and nxt[0] == info[0] and 0x01 <= nxt[1] <= 0x03
        ):
            tail += chars[i]
            nasal = True
            i += 1
        units.append({"head": head, "tail": tail, "kind": kind, "nasal": nasal})
    return units


def schwa_deleted(value: str) -> str:
    out_words: list[str] = []
    for word in str(value or "").split():
        if script_of(word) not in INDO_ARYAN:
            out_words.append(indic_inherent_vowels(word))
            continue
        units = _units(word)
        keep = [u["kind"] == "CI" for u in units]
        last = len(units) - 1
        if last >= 1 and units[last]["kind"] == "CI" and not units[last]["nasal"]:
            keep[last] = False
        for k in range(last - 1, 0, -1):
            unit = units[k]
            if unit["kind"] != "CI" or unit["nasal"]:
                continue
            before = units[k - 1]
            after = units[k + 1]
            before_vocalic = before["kind"] in ("CM", "V") or (before["kind"] == "CI" and keep[k - 1])
            after_vocalic = after["kind"] == "CM" or (after["kind"] == "CI" and keep[k + 1])
            if before_vocalic and after_vocalic:
                keep[k] = False
        parts: list[str] = []
        for unit, flag in zip(units, keep, strict=True):
            parts.append(unit["head"])
            if unit["kind"] == "CI" and flag:
                parts.append("a")
            parts.append(unit["tail"])
        out_words.append("".join(parts))
    return " ".join(out_words)


def to_latin(value: Any) -> str:
    if value is None:
        return ""
    from anyascii import anyascii

    return anyascii(indic_inherent_vowels(unicodedata.normalize("NFC", str(value))))


def to_latin_spoken(value: Any) -> str:
    if value is None:
        return ""
    from anyascii import anyascii

    return anyascii(schwa_deleted(unicodedata.normalize("NFC", str(value))))


def unaccent(text: str) -> str:
    out: list[str] = []
    for ch in unicodedata.normalize("NFKD", text):
        if unicodedata.combining(ch) and out and out[-1].isascii():
            continue
        out.append(ch)
    return unicodedata.normalize("NFC", "".join(out))


def fold(text: Any) -> str:
    if text is None:
        return ""
    value = unicodedata.normalize("NFKC", str(text))
    value = "".join(ch for ch in value if ch not in _ZW or script_of(value) != "Latn")
    value = unaccent(value).casefold().replace("&", " and ")
    cleaned = "".join(
        ch if (ch.isalnum() or unicodedata.category(ch)[0] == "M" or ch in _ZW) else " " for ch in value
    )
    return " ".join(cleaned.split())


def ascii_key(text: Any) -> str:
    if text is None:
        return ""
    folded = to_latin(unaccent(unicodedata.normalize("NFKC", str(text)))).lower().replace("&", " and ")
    return " ".join(_NON_ALNUM.sub(" ", folded).split())


def core_key(text: Any) -> str:
    return " ".join(tok for tok in ascii_key(text).split() if tok not in STOP_TOKENS)


def alias_norm(text: Any) -> str:
    value = str(text or "")
    return ascii_key(value) if script_of(value) in ("Latn", "Zyyy") else fold(value)


def alias_lang(text: Any) -> str | None:
    script = script_of(text)
    return "en" if script == "Latn" else SCRIPT_LANG.get(script)


def key_phrases(key: str, max_tokens: int) -> list[str]:
    tokens = key.split()
    return [
        " ".join(tokens[start:end])
        for start in range(len(tokens))
        for end in range(start + 1, min(len(tokens), start + max_tokens) + 1)
    ]
