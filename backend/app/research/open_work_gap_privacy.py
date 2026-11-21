from __future__ import annotations

import re
from collections.abc import Iterable

__all__ = [
    "ADDRESS_MARK",
    "EMAIL_MARK",
    "LINK_MARK",
    "NAME_MARK",
    "PHONE_DIGITS_MIN",
    "PHONE_MARK",
    "WORDS_MIN",
    "anonymised",
    "known_words",
]

NAME_MARK = "[name]"
ADDRESS_MARK = "[address]"
PHONE_MARK = "[phone]"
EMAIL_MARK = "[email]"
LINK_MARK = "[link]"
MARKS = (NAME_MARK, ADDRESS_MARK, PHONE_MARK, EMAIL_MARK, LINK_MARK)
PHONE_DIGITS_MIN = 10
DIALLED_DIGITS_MIN = 8
WORDS_MIN = 3
NAME_WORD = r"[A-Z][a-z][\w'’-]*"
NAME = rf"{NAME_WORD}(?:\s+{NAME_WORD}){{0,3}}"
FULL_NAME = rf"{NAME_WORD}(?:\s+{NAME_WORD}){{1,3}}"
HONORIFIC = r"(?i:mrs|mr|ms|miss|dr|shri|sri(?!\s+lanka)|smt|kumari|prof|ustad|pandit|begum|madam)"
HINDI_HONORIFIC = r"(?:श्रीमती|श्री|डॉ\.?|कुमारी|सुश्री|उस्ताद)"
HINDI_PARTICLE = r"(?:ने|का|की|के|को|से|में|है|हैं)(?:\s|$|[,.?।])"
HINDI_NAME = rf"\S+(?:\s+(?!{HINDI_PARTICLE})\S+)?"
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
LINK = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
HANDLE = re.compile(r"(?<![\w@])@\w{2,}")
PHONE = re.compile(r"(?<![\w+])\+?\d[\d\s().-]{6,}\d(?!\w)")
PIN = re.compile(r"\b(?:pin\s*(?:code)?|postal\s+code|zip)\s*[:#.-]?\s*\d{3}\s?\d{3}\b", re.IGNORECASE)
HOUSE = re.compile(
    r"\b(?:house|flat|plot|door|shop|h\.?\s?no)\.?\s*(?:no\.?|number)?\s*[:#.-]?\s*\d+[\w/-]*", re.IGNORECASE
)
STREET = re.compile(
    r"\b\d+[\w/-]*,?\s+(?:[A-Z][\w.]*\s+){0,3}"
    r"(?i:road|rd|street|lane|marg|nagar|colony|sector|gali|mohalla|chowk|society|apartments?)\b"
)
SELF_NAMED = re.compile(rf"\b(?i:my\s+name\s+is|i\s+am|i'm|myself|call\s+me)\s+({NAME})")
HINDI_SELF_NAMED = re.compile(rf"(मेरा नाम\s+){HINDI_NAME}")
TITLED = re.compile(rf"\b{HONORIFIC}\.?\s+{NAME}")
HINDI_TITLED = re.compile(rf"{HINDI_HONORIFIC}\s+{HINDI_NAME}")
RUN = re.compile(FULL_NAME)
CONTACT_ASKS = re.compile(
    r"\b(?:phone|mobile|cell|whatsapp|telephone|contact)\s*(?:no\.?|number|details?|info\w*)?\s+(?:of|for)\b"
    r"|\b(?:e-?mail|email\s+id|address)\s+of\b|\b(?:home|residential)\s+address\b"
    r"|\bhow\s+(?:can|do|could)\s+i\s+(?:contact|reach|call|meet|find)\b",
    re.IGNORECASE,
)
PERSONAL_ASKS = re.compile(
    r"\b(?:who\s+is|who\s+was|tell\s+me\s+about|biography|life\s+of|how\s+old|married|lives?|stays?|resides?)\b"
    r"|\b(?:his|her|their)\s+(?:age|wife|husband|children|son|daughter|family|salary|income|caste|religion"
    r"|health|illness|address|number|house|home)\b",
    re.IGNORECASE,
)
SENTENCE_END = re.compile(r"[.!?।]\s*$")
WORD = re.compile(r"\w{2,}")
TOKEN = re.compile(r"\S*[^\W\d_]\S*")
SPACED_WORD = re.compile(r"\S+")
POSSESSIVE = re.compile(r"['’]s$")


def known_words(names: Iterable[str]) -> frozenset[str]:
    return frozenset(word.casefold() for name in names for word in WORD.findall(name))


def anonymised(question: str, known: frozenset[str] = frozenset()) -> str | None:
    if CONTACT_ASKS.search(question):
        return None
    text = _without_contacts(_without_self(question))
    if _names_someone(text, known) and PERSONAL_ASKS.search(text):
        return None
    return _kept(_without_names(text, known))


def _without_self(text: str) -> str:
    text = SELF_NAMED.sub(lambda found: found.group(0).replace(found.group(1), NAME_MARK), text)
    return HINDI_SELF_NAMED.sub(lambda found: f"{found.group(1)}{NAME_MARK}", text)


def _without_contacts(text: str) -> str:
    text = EMAIL.sub(EMAIL_MARK, text)
    text = LINK.sub(LINK_MARK, text)
    text = HANDLE.sub(NAME_MARK, text)
    text = PHONE.sub(_phone, text)
    for address in (PIN, HOUSE, STREET):
        text = address.sub(ADDRESS_MARK, text)
    return text


def _names_someone(text: str, known: frozenset[str]) -> bool:
    return bool(TITLED.search(text) or HINDI_TITLED.search(text) or _unknown_runs(text, known))


def _without_names(text: str, known: frozenset[str]) -> str:
    text = TITLED.sub(NAME_MARK, text)
    text = HINDI_TITLED.sub(NAME_MARK, text)
    for start, end in reversed(_unknown_runs(text, known)):
        text = f"{text[:start]}{NAME_MARK}{text[end:]}"
    return text


def _unknown_runs(text: str, known: frozenset[str]) -> list[tuple[int, int]]:
    spans = []
    for found in RUN.finditer(text):
        words = [(word.start(), word.end()) for word in SPACED_WORD.finditer(found.group(0))]
        if _opens_sentence(text, found.start()):
            words = words[1:]
        if len(words) < 2 or all(_known(found.group(0)[start:end], known) for start, end in words):
            continue
        spans.append((found.start() + words[0][0], found.start() + words[-1][1]))
    return spans


def _opens_sentence(text: str, start: int) -> bool:
    before = text[:start].rstrip()
    return not before or SENTENCE_END.search(before) is not None or before.endswith((":", '"', "“"))


def _known(word: str, known: frozenset[str]) -> bool:
    return POSSESSIVE.sub("", word).casefold() in known


def _phone(found: re.Match[str]) -> str:
    digits = sum(character.isdigit() for character in found.group(0))
    wanted = DIALLED_DIGITS_MIN if found.group(0).startswith("+") else PHONE_DIGITS_MIN
    return PHONE_MARK if digits >= wanted else found.group(0)


def _kept(text: str) -> str | None:
    cleaned = " ".join(text.split())
    left = cleaned
    for mark in MARKS:
        left = left.replace(mark, " ")
    return cleaned if len(TOKEN.findall(left)) >= WORDS_MIN else None
