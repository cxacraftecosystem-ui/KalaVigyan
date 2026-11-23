from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.core.errors import ExternalFailure
from app.research.images import (
    IMAGE_DESCRIPTION_MAX_CHARS,
    ImageCandidate,
    ImageQuery,
    clipped,
    openly_licensed,
)
from app.research.licences import open_licence

from ..adapter import Clock, checked_k, usable_records, utc_now
from ..http import RatePolicy, SourceHttp
from ..records import UnusableRecord, clean_text, doi_of, doi_url, query_terms
from .jats_figures import JatsFigure, article_licence_url, jats_figures, jats_root

__all__ = [
    "EUROPE_PMC_FIGURES_RATE",
    "FIGURES_SITE",
    "FIGURE_ARTICLES_MAX",
    "FIGURE_CDN",
    "EuropePmcFiguresAdapter",
]

logger = logging.getLogger(__name__)

EUROPE_PMC_API = "https://www.ebi.ac.uk/europepmc/webservices/rest"
FIGURE_CDN = "https://cdn.ncbi.nlm.nih.gov/pmc/"
FIGURES_SITE = "Europe PMC"
EUROPE_PMC_FIGURES_RATE = RatePolicy(min_interval=0.2)
FIGURE_ARTICLES_MAX = 2
SEARCH_PAGE = 5
OPEN_FULL_TEXT = "OPEN_ACCESS:y AND HAS_FT:y"
YES = "Y"
PMCID = re.compile(r"^PMC\d+$")
LICENCE_NAMES = {"cc by": "CC BY", "cc by-sa": "CC BY-SA", "cc0": "CC0"}
LICENCE_VERSION = re.compile(r"/(\d+(?:\.\d+)*)/?$")
NO_FULL_TEXT_STATUSES = frozenset({404, 500})


@dataclass(frozen=True)
class _Article:
    pmcid: str
    page_url: str
    author: str
    licence: str


class EuropePmcFiguresAdapter:
    name = "europe_pmc_figures"

    def __init__(self, http: SourceHttp, *, clock: Clock = utc_now) -> None:
        self.http = http
        self.clock = clock

    async def images(self, query: ImageQuery, k: int) -> list[ImageCandidate]:
        wanted = checked_k(k)
        found: list[ImageCandidate] = []
        for article in (await self._articles(query))[:FIGURE_ARTICLES_MAX]:
            found.extend(await self._figures(article, self.clock()))
            if len(found) >= wanted:
                break
        return found[:wanted]

    async def _articles(self, query: ImageQuery) -> list[_Article]:
        terms = query_terms(query.text)
        if not terms:
            return []
        params = {
            "query": f"FIG:({' '.join(terms)}) AND {OPEN_FULL_TEXT}",
            "format": "json",
            "resultType": "core",
            "pageSize": str(SEARCH_PAGE),
        }
        response = await self.http.get(f"{EUROPE_PMC_API}/search", params=params)
        return usable_records(self.name, _results(response.json(self.name)), _article)

    async def _figures(self, article: _Article, retrieved_at: datetime) -> list[ImageCandidate]:
        try:
            response = await self.http.get(f"{EUROPE_PMC_API}/{article.pmcid}/fullTextXML")
        except ExternalFailure as failure:
            if failure.status not in NO_FULL_TEXT_STATUSES:
                raise
            logger.warning(
                "europe_pmc has no full text for %s, so none of its figures is offered", article.pmcid
            )
            return []
        root = jats_root(response.body, self.name)
        licence = _figure_licence(article.licence, article_licence_url(root))
        if licence is None:
            logger.warning(
                "the figures of %s are left out: its full text states no open licence", article.pmcid
            )
            return []
        return usable_records(
            self.name,
            jats_figures(root),
            lambda shown: self._candidate(article, shown, licence, retrieved_at),
        )

    def _candidate(
        self, article: _Article, figure: JatsFigure, licence: tuple[str, str | None], retrieved_at: datetime
    ) -> ImageCandidate:
        image = FIGURE_CDN + figure.image_path.lstrip("/")
        sized = figure.width is not None and figure.height is not None
        named, licence_url = licence
        candidate = ImageCandidate(
            provider=self.name,
            page_url=article.page_url,
            image_url=image,
            original_url=image,
            width=figure.width if sized else None,
            height=figure.height if sized else None,
            title=clipped(f"{figure.label}: {figure.heading}" if figure.label else figure.heading),
            description=clipped(figure.caption, IMAGE_DESCRIPTION_MAX_CHARS),
            author=clipped(article.author),
            site=FIGURES_SITE,
            licence=named,
            licence_url=licence_url,
            retrieved_at=retrieved_at,
        )
        if not openly_licensed(candidate):
            raise UnusableRecord(f"licence {named!r} is not on the open allow-list")
        return candidate


def _results(payload: Any) -> list[Any]:
    results = ((payload.get("resultList") or {}).get("result")) if isinstance(payload, dict) else None
    if not isinstance(results, list):
        raise ExternalFailure(
            "europe_pmc answered without a result list", service=EuropePmcFiguresAdapter.name
        )
    return results


def _article(record: Any) -> _Article:
    if not isinstance(record, dict):
        raise UnusableRecord("not an object")
    pmcid = clean_text(record.get("pmcid")) or ""
    if record.get("isOpenAccess") != YES or record.get("inEPMC") != YES or not PMCID.match(pmcid):
        raise UnusableRecord("no open full text in Europe PMC")
    licence = LICENCE_NAMES.get((clean_text(record.get("license")) or "").casefold())
    if licence is None or not open_licence(licence):
        raise UnusableRecord(f"licence {record.get('license')!r} is not open")
    author = _first_author(record)
    if author is None:
        raise UnusableRecord("no author to credit")
    doi = doi_of(record.get("doi"))
    page = doi_url(doi) if doi else f"https://europepmc.org/article/PMC/{pmcid}"
    return _Article(pmcid=pmcid, page_url=page, author=author, licence=licence)


def _first_author(record: dict[str, Any]) -> str | None:
    listed = ((record.get("authorList") or {}).get("author")) or []
    names = [name for name in (clean_text(author.get("fullName")) for author in listed) if name]
    if not names:
        return None
    return names[0] if len(names) == 1 else f"{names[0]} et al."


def _figure_licence(licence: str, url: str | None) -> tuple[str, str | None] | None:
    if url is None:
        return licence, None
    if not open_licence(url):
        return None
    version = LICENCE_VERSION.search(url)
    return (f"{licence} {version.group(1)}" if version else licence), url
