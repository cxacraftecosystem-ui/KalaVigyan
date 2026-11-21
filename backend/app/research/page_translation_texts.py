from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from .page_translation_gates import TranslationCheck
from .review_switch import PUBLISHED
from .trust_tiers import DRAWN, ROLE, TRUSTED, TierPlacement
from .vocabulary import ANSWER_LANGUAGE_SPECS

__all__ = [
    "NO_PAGE",
    "NO_PASSAGE",
    "TRANSLATE_ACCEPTANCE",
    "placed_message",
    "translate_needed",
]

NO_PAGE = (
    "This page is not drawn as a monograph yet, so it has no passages to translate; translate a page that "
    "list_open_work offers as a TRANSLATE task."
)
NO_PASSAGE = (
    "{key} is not a passage of the page to translate: take the keys, texts and source_hash from the "
    "TRANSLATE task (reserve_tasks or my_work list them)."
)
REFUSED_PASSAGE = "Not taken: the {check} check refused it. {reason}"
SHOWN_AT_ONCE: Mapping[str, str] = MappingProxyType(
    {
        ROLE: "Shown on the {label} page at once, because your account reviews {label}.",
        TRUSTED: "Shown on the {label} page at once, because your account's record is proven.",
        DRAWN: "Shown on the {label} page, and drawn for a reviewer who reads {label} to check.",
    }
)
WAITING = (
    "Waits for a reviewer who reads {label}; until it is approved the page shows the English passage, marked "
    "as English."
)
TRANSLATE_ACCEPTANCE = (
    "Translate each passage of the task with preview_page and then propose_page, in a bundle whose translation "
    "part names the language, this task_key and each passage's key, source_hash and texts: one text for each "
    "English text, in order, the fixed ones (names, botanical names, quotes, formula parts) copied exactly and "
    "the cited one ending the sentence. The gates check that it translates the current English passage, keeps "
    "every number, unit and formula, adds nothing and is written in the language's script; a reviewer who reads "
    "the language approves it. The task closes when no passage is left to translate."
)
NEEDED = (
    "Translate the page of {name} into {label} ({autonym}): {count} passages wait, each sentence keeping its "
    "citations, names and quotes as the English has them."
)


def placed_message(placed: TierPlacement, language: str, failed: TranslationCheck | None) -> str:
    if failed is not None:
        return REFUSED_PASSAGE.format(check=failed.check, reason=failed.reasons[0])
    label = ANSWER_LANGUAGE_SPECS[language].label
    if placed.placed.outcome == PUBLISHED:
        return SHOWN_AT_ONCE.get(placed.why, SHOWN_AT_ONCE[DRAWN]).format(label=label)
    return WAITING.format(label=label)


def translate_needed(name: str, language: str, count: int) -> str:
    spec = ANSWER_LANGUAGE_SPECS[language]
    return NEEDED.format(name=name, label=spec.label, autonym=spec.autonym, count=count)
