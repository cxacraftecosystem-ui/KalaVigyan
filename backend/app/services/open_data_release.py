from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from app.core.errors import InvalidInput
from app.models.open_data import DEPOSIT_TARGETS, SCOPE_CHARS

__all__ = [
    "DOI_PATTERN",
    "SANDBOX",
    "VERSION_PATTERN",
    "ZENODO",
    "ReleaseStamp",
    "checked_craft",
    "checked_doi",
    "checked_target",
    "released_on",
]

SANDBOX, ZENODO = DEPOSIT_TARGETS
VERSION_PATTERN = re.compile(r"^(\d{4})\.(\d{2})\.(\d{2})(?:\.([1-9]\d?))?$")
DOI_PATTERN = re.compile(r"^10\.\d{4,9}/[A-Za-z0-9._;()/:-]{1,200}$")
BAD_VERSION = (
    "A release version is YYYY.MM.DD, or YYYY.MM.DD.N for a second release that day; {version!r} is not."
)
BAD_DOI = "{doi!r} is not a DOI such as 10.5281/zenodo.1234567."
BAD_TARGET = "The deposit target is SANDBOX or ZENODO, not {target!r}."
CRAFT_PATTERN = re.compile(rf"^\S{{1,{SCOPE_CHARS}}}$")
BAD_CRAFT = "A craft release names one craft by its slug, such as Kutch-Ajrakh; {craft!r} is not a slug."


@dataclass(frozen=True)
class ReleaseStamp:
    target: str
    version: str
    doi: str
    concept_doi: str
    record_id: int
    concept_record_id: int
    craft: str | None = None

    def __post_init__(self) -> None:
        checked_target(self.target)
        released_on(self.version)
        checked_doi(self.doi)
        checked_doi(self.concept_doi)
        checked_craft(self.craft)
        if self.record_id < 1 or self.concept_record_id < 1:
            raise InvalidInput("Zenodo record ids are positive integers.")

    @property
    def released(self) -> date:
        return released_on(self.version)

    def doi_url(self) -> str:
        return f"https://doi.org/{self.doi}"

    def concept_doi_url(self) -> str:
        return f"https://doi.org/{self.concept_doi}"


def released_on(version: str) -> date:
    found = VERSION_PATTERN.fullmatch(version)
    if found is None:
        raise InvalidInput(BAD_VERSION.format(version=version))
    year, month, day = (int(part) for part in found.groups()[:3])
    try:
        return date(year, month, day)
    except ValueError as wrong:
        raise InvalidInput(BAD_VERSION.format(version=version)) from wrong


def checked_doi(doi: str) -> str:
    if DOI_PATTERN.fullmatch(doi) is None:
        raise InvalidInput(BAD_DOI.format(doi=doi))
    return doi


def checked_craft(craft: str | None) -> str | None:
    if craft is not None and CRAFT_PATTERN.fullmatch(craft) is None:
        raise InvalidInput(BAD_CRAFT.format(craft=craft))
    return craft


def checked_target(target: str) -> str:
    if target not in DEPOSIT_TARGETS:
        raise InvalidInput(BAD_TARGET.format(target=target))
    return target
