from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any, Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, model_validator

from .base import ContractModel
from .vocabulary import TrustTier

__all__ = [
    "DOMAIN_KINDS",
    "RANKED_TRUSTS",
    "WEB_DEFAULT_TRUST",
    "WEB_TRUST_FILE",
    "TrustedDomain",
    "WebTrust",
    "WebTrustFile",
    "load_web_trust",
    "parse_web_trust",
    "web_trust",
]

WEB_TRUST_FILE = Path(__file__).with_name("web_trust.json")
WEB_DEFAULT_TRUST: TrustTier = "C"
RANKED_TRUSTS = ("A", "B")
DOMAIN_KINDS = ("government", "standards body", "museum", "university", "research institute", "heritage body")
DOMAIN_PATTERN = r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*$"
DOMAIN_MAX_CHARS = 253
REASON_MIN_CHARS = 40
REASON_MAX_CHARS = 400


class TrustedDomain(ContractModel):
    domain: str = Field(pattern=DOMAIN_PATTERN, max_length=DOMAIN_MAX_CHARS)
    trust: Literal[*RANKED_TRUSTS]
    kind: Literal[*DOMAIN_KINDS]
    reason: str = Field(min_length=REASON_MIN_CHARS, max_length=REASON_MAX_CHARS)


class WebTrustFile(ContractModel):
    schema_version: Literal[1]
    about: str = Field(min_length=REASON_MIN_CHARS)
    domains: tuple[TrustedDomain, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _each_domain_once(self) -> Self:
        names = [row.domain for row in self.domains]
        twice = sorted({name for name in names if names.count(name) > 1})
        if twice:
            raise ValueError(f"listed more than once: {', '.join(twice)}")
        return self


@dataclass(frozen=True)
class WebTrust:
    by_domain: Mapping[str, TrustTier]

    def trust_of(self, url: str) -> TrustTier:
        labels = _host_labels(url)
        for start in range(len(labels)):
            found = self.by_domain.get(".".join(labels[start:]))
            if found is not None:
                return found
        return WEB_DEFAULT_TRUST


def parse_web_trust(raw: Mapping[str, Any]) -> WebTrust:
    listed = WebTrustFile.model_validate(raw)
    return WebTrust(MappingProxyType({row.domain: row.trust for row in listed.domains}))


@lru_cache(maxsize=1)
def load_web_trust() -> WebTrust:
    return parse_web_trust(json.loads(WEB_TRUST_FILE.read_text(encoding="utf-8")))


def web_trust(url: str) -> TrustTier:
    return load_web_trust().trust_of(url)


def _host_labels(url: str) -> tuple[str, ...]:
    try:
        host = (urlsplit(url).hostname or "").rstrip(".")
        name = host.encode("idna").decode("ascii")
    except ValueError, UnicodeError:
        return ()
    return tuple(label for label in name.split(".") if label)
