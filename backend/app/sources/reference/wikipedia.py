from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any

from app.core.errors import InvalidInput
from app.research.evidence import EvidenceItem, SearchQuery, SourceDocument

from ..adapter import HttpSourceAdapter, build_document
from ..records import UnusableRecord, clean_text, https_or_none, title_of
from .mediawiki import (
    WIKIMEDIA_PUBLISHER,
    WIKIMEDIA_RATE,
    action_api,
    page_revision,
    pages_in_order,
    primary_language,
    rights_text,
)
from .wikipedia_editions import WIKIPEDIA_EDITIONS_FILE, wikipedia_editions

__all__ = ["LANGUAGE_ALIASES", "WIKIPEDIA_LANGUAGES", "WIKIPEDIA_RATE", "WikipediaAdapter", "wiki_language"]

WIKIPEDIA_RATE = WIKIMEDIA_RATE
WIKIPEDIA_LANGUAGES = wikipedia_editions(WIKIPEDIA_EDITIONS_FILE)
LANGUAGE_ALIASES: Mapping[str, str] = MappingProxyType(
    {
        "bho": "bh",
        "gsw": "als",
        "kok": "gom",
        "lzh": "zh-classical",
        "nan": "zh-min-nan",
        "nb": "no",
        "ori": "or",
        "rup": "roa-rup",
        "sgs": "bat-smg",
        "vro": "fiu-vro",
        "yue": "zh-yue",
    }
)
NATIVE_ID = re.compile(r"^([a-z]{2,8}(?:-[a-z]{2,8})*):([1-9]\d*)$")
PAGE_PROPS = {
    "prop": "info|pageprops|revisions",
    "inprop": "url",
    "ppprop": "wikibase_item",
    "rvprop": "ids|timestamp",
    "meta": "siteinfo",
    "siprop": "rightsinfo",
}


@dataclass(frozen=True)
class WikiPage:
    language: str
    page: dict[str, Any]
    licence: str | None


class WikipediaAdapter(HttpSourceAdapter):
    name = "wikipedia"

    async def _search_records(self, query: SearchQuery, k: int) -> list[Any]:
        language = wiki_language(query.language)
        params = PAGE_PROPS | {
            "action": "query",
            "generator": "search",
            "gsrsearch": query.text,
            "gsrnamespace": "0",
            "gsrlimit": str(k),
        }
        payload = await action_api(self.http, _endpoint(language), params)
        licence = rights_text(payload)
        return [WikiPage(language, page, licence) for page in pages_in_order(payload)]

    def _item(self, record: Any, retrieved_at: datetime) -> EvidenceItem:
        page, language = record.page, record.language
        page_id = page.get("pageid")
        url = https_or_none(page.get("canonicalurl") or page.get("fullurl"))
        if not page_id or url is None:
            raise UnusableRecord("no page id or https URL")
        title = title_of(page.get("title"))
        revision = page_revision(page)
        external_ids = {"wikipedia": f"{language}:{page_id}", "revision": revision.id}
        wikidata = clean_text((page.get("pageprops") or {}).get("wikibase_item"))
        if wikidata:
            external_ids["wikidata"] = wikidata
        return EvidenceItem(
            id=f"{self.name}:{language}:{page_id}",
            adapter=self.name,
            tier=self.tier,
            source_type="ENCYCLOPEDIA",
            url=url,
            title=title,
            published=revision.published,
            retrieved_at=retrieved_at,
            licence=record.licence,
            attribution=f'Wikipedia contributors, "{title}", {language} Wikipedia, revision {revision.id}',
            publisher=WIKIMEDIA_PUBLISHER,
            trust="B",
            external_ids=external_ids,
        )

    async def _fetch_document(self, native: str, retrieved_at: datetime) -> SourceDocument:
        match = NATIVE_ID.match(native)
        if match is None or match.group(1) not in WIKIPEDIA_LANGUAGES:
            raise InvalidInput(f"{native!r} is not '<language>:<page id>' on a supported Wikipedia")
        language, page_id = match.groups()
        params = PAGE_PROPS | {
            "action": "query",
            "pageids": page_id,
            "prop": f"{PAGE_PROPS['prop']}|extracts",
            "explaintext": "1",
            "exsectionformat": "plain",
        }
        payload = await action_api(self.http, _endpoint(language), params)
        pages = pages_in_order(payload)
        if not pages or pages[0].get("missing") or pages[0].get("ns") != 0:
            raise self._not_found(native, "no article")
        extract = pages[0].get("extract")
        text = extract.strip() if isinstance(extract, str) else ""
        if not text:
            raise self._not_found(native, "no article text")
        item = self._item(WikiPage(language, pages[0], rights_text(payload)), retrieved_at)
        return build_document(item, text, "FULL_TEXT")


def wiki_language(language: str) -> str:
    primary = primary_language(language)
    code = LANGUAGE_ALIASES.get(primary, primary)
    if code not in WIKIPEDIA_LANGUAGES:
        raise InvalidInput(f"No Wikipedia edition is written in language {language!r}")
    return code


def _endpoint(language: str) -> str:
    return f"https://{language}.wikipedia.org/w/api.php"
