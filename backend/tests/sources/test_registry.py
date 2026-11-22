import re

import pytest

from app.core.errors import ExternalFailure, InvalidInput, NotConfigured
from app.research.evidence import ADAPTER_NAME_PATTERN, OpenAccessLocator
from app.services import managed_secrets, scholarly_keys
from app.sources.scholarly.registry import SCHOLARLY_KEY_NAMES, ScholarlyKeys, scholarly_sources
from app.sources.scholarly.unpaywall import UnpaywallLocator

from .recorded import CONTACT, RETRIEVED, Recorder, Reply, fixed_clock, source_http

OPEN_ADAPTERS = ["openalex", "crossref", "semantic_scholar", "europe_pmc", "arxiv", "doaj", "zenodo"]


def build(keys: ScholarlyKeys):
    return scholarly_sources(keys, Recorder({}).client(), clock=fixed_clock())


def test_without_keys_the_open_services_run_and_core_is_reported() -> None:
    sources = build(ScholarlyKeys(contact_email=CONTACT))
    assert [adapter.name for adapter in sources.adapters] == OPEN_ADAPTERS
    assert sources.unconfigured == ("CORE_API_KEY",)
    assert isinstance(sources.locator, OpenAccessLocator)


def test_keys_switch_on_core_and_the_dormant_publishers() -> None:
    keys = ScholarlyKeys(
        contact_email=CONTACT, core_api_key="c", elsevier_api_key="e", springer_nature_api_key="s"
    )
    sources = build(keys)
    assert [adapter.name for adapter in sources.adapters] == [
        *OPEN_ADAPTERS,
        "core",
        "elsevier",
        "springer_nature",
    ]
    assert sources.unconfigured == ()


def test_each_adapter_is_paced_under_its_published_limit() -> None:
    sources = build(ScholarlyKeys(contact_email=CONTACT, core_api_key="c"))
    intervals = {adapter.name: adapter.http.limits.search.interval for adapter in sources.adapters}
    assert intervals == pytest.approx(
        {
            "openalex": 0.125,
            "crossref": 5 / 12,
            "semantic_scholar": 1.25,
            "europe_pmc": 0.25,
            "arxiv": 3.75,
            "doaj": 0.625,
            "zenodo": 2.5,
            "core": 7.5,
        }
    )
    assert {adapter.name: adapter.http.policy.min_interval for adapter in sources.adapters} == dict.fromkeys(
        intervals, 0.0
    )
    services = [adapter.http.service for adapter in sources.adapters]
    assert services == [adapter.name for adapter in sources.adapters]
    assert all(re.fullmatch(ADAPTER_NAME_PATTERN, name) for name in services)


def test_a_contact_email_is_required() -> None:
    with pytest.raises(NotConfigured) as missing:
        build(ScholarlyKeys(contact_email=""))
    assert missing.value.name == "RESEARCH_CONTACT_EMAIL"


def test_keys_never_appear_in_their_repr() -> None:
    text = repr(ScholarlyKeys(contact_email=CONTACT, core_api_key="core-secret-value"))
    assert "core-secret-value" not in text
    assert "CORE_API_KEY" in text


def test_every_scholarly_key_is_a_managed_key() -> None:
    assert set(SCHOLARLY_KEY_NAMES) <= set(managed_secrets.MANAGED_KEYS)


async def test_keys_come_from_the_managed_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    stored = {"CORE_API_KEY": "core-from-table", "OPENALEX_API_KEY": "oa-from-env"}

    async def get_secret(session: object, key: str) -> str | None:
        return stored.get(key)

    monkeypatch.setattr(managed_secrets, "get_secret", get_secret)
    keys = await scholarly_keys.scholarly_keys(session=object())
    assert keys.core_api_key == "core-from-table"
    assert keys.openalex_api_key == "oa-from-env"
    assert keys.elsevier_api_key is None
    assert keys.contact_email == CONTACT


def locator(routes: dict) -> tuple[UnpaywallLocator, Recorder]:
    recorder = Recorder(routes)
    return UnpaywallLocator(
        source_http(recorder, "unpaywall"), contact_email=CONTACT, clock=fixed_clock()
    ), recorder


async def test_unpaywall_locates_an_open_copy() -> None:
    finder, recorder = locator(
        {"api.unpaywall.org/v2/10.1038/s41598-022-27110-0": Reply("unpaywall_open.json")}
    )
    found = await finder.locate("https://doi.org/10.1038/s41598-022-27110-0")
    assert (found.doi, found.status, found.is_open) == ("10.1038/s41598-022-27110-0", "GOLD", True)
    assert found.landing_url == "https://doi.org/10.1038/s41598-022-27110-0"
    assert found.pdf_url == "https://www.nature.com/articles/s41598-022-27110-0.pdf"
    assert (found.licence, found.version, found.host_type) == ("cc-by", "publishedVersion", "PUBLISHER")
    assert found.checked_at == RETRIEVED
    assert recorder.requests[0].url.params["email"] == CONTACT


async def test_unpaywall_reports_a_closed_work() -> None:
    finder, _ = locator({"api.unpaywall.org/v2/10.1111/cote.12288": Reply("unpaywall_closed.json")})
    found = await finder.locate("10.1111/cote.12288")
    assert (found.status, found.is_open, found.landing_url, found.pdf_url) == ("CLOSED", False, None, None)


async def test_unpaywall_refuses_a_non_doi_and_reports_a_retired_endpoint() -> None:
    finder, _ = locator({"api.unpaywall.org/v2/10.1234/x": Reply("unpaywall_search_gone.json", status=410)})
    with pytest.raises(InvalidInput):
        await finder.locate("alizarin mordant")
    with pytest.raises(ExternalFailure) as gone:
        await finder.locate("10.1234/x")
    assert gone.value.kind == "not_found"
