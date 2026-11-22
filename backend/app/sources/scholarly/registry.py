from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import httpx

from app.core.errors import NotConfigured

from ..adapter import Clock, HttpSourceAdapter, utc_now
from ..http import RatePolicy
from .arxiv import ARXIV_LIMITS, ArxivAdapter
from .core_works import CORE_LIMITS, CoreAdapter
from .crossref import CROSSREF_LIMITS, CrossrefAdapter
from .doaj import DOAJ_LIMITS, DoajAdapter
from .elsevier import ELSEVIER_LIMITS, ElsevierAdapter, ElsevierFullText
from .europe_pmc import EUROPE_PMC_LIMITS, EuropePmcAdapter
from .open_copies import OpenCopyLocator
from .openalex import OPENALEX_KEYED_LIMITS, OPENALEX_LIMITS, OpenAlexAdapter
from .pacing import PacedHttp, ScholarlyPacing, ServiceLimits, shared_pacing
from .publishers import PublisherFullText, PublisherReader
from .semantic_scholar import SEMANTIC_SCHOLAR_LIMITS, SemanticScholarAdapter
from .springer_nature import SPRINGER_NATURE_LIMITS, SpringerNatureAdapter, SpringerNatureFullText
from .unpaywall import UNPAYWALL_LIMITS, UnpaywallLocator
from .zenodo import ZENODO_LIMITS, ZenodoAdapter, ZenodoLocator

__all__ = ["SCHOLARLY_KEY_NAMES", "ScholarlyKeys", "ScholarlySources", "scholarly_sources"]

SCHOLARLY_KEY_NAMES = (
    "OPENALEX_API_KEY",
    "SEMANTIC_SCHOLAR_API_KEY",
    "CORE_API_KEY",
    "ELSEVIER_API_KEY",
    "ELSEVIER_INSTTOKEN",
    "SPRINGER_NATURE_API_KEY",
)


SPACED_BY_LIMITS = RatePolicy(min_interval=0.0)

HttpFactory = Callable[[str, ServiceLimits], PacedHttp]


@dataclass(frozen=True, repr=False)
class ScholarlyKeys:
    contact_email: str
    openalex_api_key: str | None = None
    semantic_scholar_api_key: str | None = None
    core_api_key: str | None = None
    elsevier_api_key: str | None = None
    elsevier_insttoken: str | None = None
    springer_nature_api_key: str | None = None

    def __repr__(self) -> str:
        present = [name for name in SCHOLARLY_KEY_NAMES if getattr(self, name.lower())]
        return f"ScholarlyKeys(contact_email={self.contact_email!r}, present={present})"


@dataclass(frozen=True)
class ScholarlySources:
    adapters: tuple[HttpSourceAdapter, ...]
    locator: OpenCopyLocator
    unconfigured: tuple[str, ...]
    publisher: PublisherFullText | None = None


def scholarly_sources(
    keys: ScholarlyKeys,
    client: httpx.AsyncClient,
    *,
    clock: Clock = utc_now,
    pacing: ScholarlyPacing | None = None,
) -> ScholarlySources:
    if not keys.contact_email:
        raise NotConfigured("RESEARCH_CONTACT_EMAIL", "Scholarly APIs need a contact email address")
    http = _http_factory(client, pacing or shared_pacing())
    keyed, unconfigured = _keyed_adapters(keys, http, clock)
    unpaywall = UnpaywallLocator(
        http("unpaywall", UNPAYWALL_LIMITS), contact_email=keys.contact_email, clock=clock
    )
    locator = OpenCopyLocator(unpaywall, ZenodoLocator(http("zenodo", ZENODO_LIMITS), clock=clock))
    adapters = (*_open_adapters(keys, http, clock), *keyed)
    return ScholarlySources(adapters, locator, unconfigured, _publisher(keys, http, locator))


def _open_adapters(keys: ScholarlyKeys, http: HttpFactory, clock: Clock) -> list[HttpSourceAdapter]:
    email = keys.contact_email
    openalex_limits = OPENALEX_KEYED_LIMITS if keys.openalex_api_key else OPENALEX_LIMITS
    return [
        OpenAlexAdapter(
            http("openalex", openalex_limits), contact_email=email, api_key=keys.openalex_api_key, clock=clock
        ),
        CrossrefAdapter(http("crossref", CROSSREF_LIMITS), contact_email=email, clock=clock),
        SemanticScholarAdapter(
            http("semantic_scholar", SEMANTIC_SCHOLAR_LIMITS),
            api_key=keys.semantic_scholar_api_key,
            clock=clock,
        ),
        EuropePmcAdapter(http("europe_pmc", EUROPE_PMC_LIMITS), clock=clock),
        ArxivAdapter(http("arxiv", ARXIV_LIMITS), clock=clock),
        DoajAdapter(http("doaj", DOAJ_LIMITS), clock=clock),
        ZenodoAdapter(http("zenodo", ZENODO_LIMITS), clock=clock),
    ]


def _keyed_adapters(
    keys: ScholarlyKeys, http: HttpFactory, clock: Clock
) -> tuple[list[HttpSourceAdapter], tuple[str, ...]]:
    adapters: list[HttpSourceAdapter] = []
    unconfigured: tuple[str, ...] = ()
    if keys.core_api_key:
        adapters.append(CoreAdapter(http("core", CORE_LIMITS), api_key=keys.core_api_key, clock=clock))
    else:
        unconfigured = ("CORE_API_KEY",)
    if keys.elsevier_api_key:
        elsevier_http = http("elsevier", ELSEVIER_LIMITS)
        adapters.append(
            ElsevierAdapter(
                elsevier_http, api_key=keys.elsevier_api_key, insttoken=keys.elsevier_insttoken, clock=clock
            )
        )
    if keys.springer_nature_api_key:
        springer_http = http("springer_nature", SPRINGER_NATURE_LIMITS)
        adapters.append(
            SpringerNatureAdapter(springer_http, api_key=keys.springer_nature_api_key, clock=clock)
        )
    return adapters, unconfigured


def _publisher(keys: ScholarlyKeys, http: HttpFactory, locator: OpenCopyLocator) -> PublisherFullText | None:
    readers: list[PublisherReader] = []
    if keys.elsevier_api_key and keys.elsevier_insttoken:
        readers.append(
            ElsevierFullText(
                http("elsevier", ELSEVIER_LIMITS),
                api_key=keys.elsevier_api_key,
                insttoken=keys.elsevier_insttoken,
            )
        )
    if keys.springer_nature_api_key:
        readers.append(
            SpringerNatureFullText(
                http("springer_nature", SPRINGER_NATURE_LIMITS), api_key=keys.springer_nature_api_key
            )
        )
    return PublisherFullText(locator, readers) if readers else None


def _http_factory(client: httpx.AsyncClient, pacing: ScholarlyPacing) -> HttpFactory:
    def build(service: str, limits: ServiceLimits) -> PacedHttp:
        return PacedHttp(
            client=client,
            service=service,
            policy=SPACED_BY_LIMITS,
            cache=pacing.cache(service),
            limits=limits,
            pacing=pacing,
        )

    return build
