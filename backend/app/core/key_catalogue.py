from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

__all__ = ["MANAGED_KEYS", "KeyFormat", "ManagedKey", "format_problem", "is_managed"]

DEFAULT_FORMAT_HINT = "This doesn't look like a valid value."


@dataclass(frozen=True)
class KeyFormat:
    min_length: int = 8
    suffix: str | None = None
    hint: str = DEFAULT_FORMAT_HINT


@dataclass(frozen=True)
class ManagedKey:
    key: str
    label: str
    description: str
    group: str
    format: KeyFormat | None = None

    @property
    def format_only(self) -> bool:
        return self.format is not None

    @property
    def settings_attr(self) -> str:
        return self.key.lower()


def format_problem(spec: KeyFormat, value: str) -> str | None:
    candidate = value.strip()
    if len(candidate) < spec.min_length or (spec.suffix and not candidate.endswith(spec.suffix)):
        return spec.hint
    return None


_KEYS = (
    ManagedKey(
        "GEMINI_API_KEY", "Google Gemini", "Planner, reader, voice turns, embeddings, images and video.", "AI"
    ),
    ManagedKey("ANTHROPIC_API_KEY", "Anthropic Claude", "Answer composer and evaluation judge.", "AI"),
    ManagedKey("OPENAI_API_KEY", "OpenAI", "Fallback route for planning, composing and voice turns.", "AI"),
    ManagedKey("DEEPSEEK_API_KEY", "DeepSeek", "Public-text reading and extraction only.", "AI"),
    ManagedKey(
        "ELEVENLABS_API_KEY", "ElevenLabs", "Voice conversation: speech-to-text and text-to-speech.", "Voice"
    ),
    ManagedKey("VOYAGE_API_KEY", "Voyage AI", "Reranks stored facts for answers.", "AI", KeyFormat(16)),
    ManagedKey(
        "BRAVE_SEARCH_API_KEY",
        "Brave Search",
        "Web search fallback when SearXNG returns too little.",
        "Search",
    ),
    ManagedKey("EXA_API_KEY", "Exa", "Deep research search.", "Search", KeyFormat(16)),
    ManagedKey("TAVILY_API_KEY", "Tavily", "Deep research search.", "Search", KeyFormat(16)),
    ManagedKey(
        "OPENALEX_API_KEY", "OpenAlex", "Scholarly works metadata and open-access links.", "Scholarly"
    ),
    ManagedKey(
        "SEMANTIC_SCHOLAR_API_KEY", "Semantic Scholar", "Scholarly search and abstracts.", "Scholarly"
    ),
    ManagedKey("CORE_API_KEY", "CORE", "Open-access full text.", "Scholarly"),
    ManagedKey("SPRINGER_NATURE_API_KEY", "Springer Nature", "Open-access and TDM full text.", "Scholarly"),
    ManagedKey("ELSEVIER_API_KEY", "Elsevier", "ScienceDirect and Scopus text mining.", "Scholarly"),
    ManagedKey(
        "ELSEVIER_INSTTOKEN",
        "Elsevier institution token",
        "Institutional entitlement for Elsevier.",
        "Scholarly",
        KeyFormat(8),
    ),
    ManagedKey("WILEY_TDM_TOKEN", "Wiley TDM", "Wiley text and data mining.", "Scholarly", KeyFormat(8)),
    ManagedKey("DATA_GOV_IN_API_KEY", "data.gov.in", "Government open datasets.", "Data", KeyFormat(16)),
    ManagedKey(
        "GOOGLE_CLIENT_ID",
        "Google sign-in client ID",
        "Web client ID for Google sign-in.",
        "Sign-in",
        KeyFormat(30, ".apps.googleusercontent.com", "This should end in .apps.googleusercontent.com."),
    ),
)

MANAGED_KEYS: Mapping[str, ManagedKey] = MappingProxyType({spec.key: spec for spec in _KEYS})


def is_managed(key: str) -> bool:
    return key in MANAGED_KEYS
