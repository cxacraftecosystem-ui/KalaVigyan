from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest

from app.services import live_sources as live_sources_module, source_lookup_store
from app.services.live_sources import LiveSourcesStore
from app.services.source_lookup_reference import compound_lookup
from app.services.source_lookup_sources import CachedFetcher
from app.services.source_lookup_store import LookupStore
from app.sources.reference.pubchem import PubChemAdapter
from app.sources.reference.wikidata import WikidataAdapter
from app.sources.scholarly.registry import ScholarlyKeys
from app.sources.web.registry import WebSearchConfig

from ..sources.recorded import Recorder, Reply
from .lookup_fakes import FakeSession

PUG = "pubchem.ncbi.nlm.nih.gov/rest/pug"
VIEW = "pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound"
PROPERTIES = "property/Title,MolecularFormula,MolecularWeight,IUPACName,InChIKey,SMILES/JSON"
CIDS = (6293, 3955344, 20431)


def recorded_pubchem() -> Recorder:
    routes: dict[str, Reply | list[Reply]] = {
        f"{PUG}/compound/name/alizarin/cids/JSON": [
            Reply("pubchem_name_cids.json"),
            Reply("pubchem_word_cids.json"),
        ],
        f"{PUG}/compound/cid/6293,3955344,20431/{PROPERTIES}": Reply("pubchem_properties.json"),
        f"{PUG}/compound/cid/6293/synonyms/JSON": Reply("pubchem_synonyms.json"),
        f"{VIEW}/6293/JSON": Reply("pubchem_ghs.json"),
    }
    for cid in CIDS[1:]:
        routes[f"{PUG}/compound/cid/{cid}/synonyms/JSON"] = Reply("pubchem_not_found.json", status=404)
        routes[f"{VIEW}/{cid}/JSON"] = Reply("pubchem_ghs_missing.json", status=404)
    return Recorder(routes)


@asynccontextmanager
async def no_database() -> AsyncIterator[object]:
    yield object()


@pytest.fixture
def live_store(monkeypatch: pytest.MonkeyPatch) -> tuple[LookupStore, Recorder]:
    async def keys(session: object) -> ScholarlyKeys:
        return ScholarlyKeys(contact_email="research@example.org")

    async def web_config(session: object) -> WebSearchConfig:
        return WebSearchConfig(searxng_url="http://127.0.0.1:8888")

    monkeypatch.setattr(live_sources_module, "scholarly_keys", keys)
    monkeypatch.setattr(live_sources_module, "web_search_config", web_config)
    monkeypatch.setattr(source_lookup_store, "sessionmaker", lambda: no_database)
    recorder = recorded_pubchem()
    return LookupStore(LiveSourcesStore(client_factory=recorder.client)), recorder


async def test_the_production_store_joins_the_live_adapters_the_source_tools_use(
    live_store: tuple[LookupStore, Recorder],
) -> None:
    store, _ = live_store
    sources = await store.sources()
    assert isinstance(sources.compounds, PubChemAdapter)
    assert isinstance(sources.entities, WikidataAdapter)
    assert [adapter.name for adapter in sources.reference] == ["wikipedia", "wikidata"]
    assert {adapter.name for adapter in sources.scholarly} >= {"openalex", "crossref"}
    assert not {"wikipedia", "wikidata", "pubchem", "wikimedia_commons", "web"} & {
        adapter.name for adapter in sources.scholarly
    }
    assert sources.web is not None and sources.web.name == "web"
    assert {source.name for source in sources.pictures} <= {"wikimedia_commons", "openverse"}
    assert isinstance(sources.fetcher, CachedFetcher) and sources.locator is not None
    assert sources.archiver is not None and sources.snapshots is not None
    assert (await store.sources()).compounds is sources.compounds


async def test_a_compound_lookup_through_the_production_store_reads_pubchem_as_recorded(
    live_store: tuple[LookupStore, Recorder],
) -> None:
    store, recorder = live_store
    sources = await store.sources()
    assert sources.compounds is not None
    found = await compound_lookup(FakeSession(scalar=None), sources.compounds, name="alizarin", cid=None)
    assert [record.cid for record in found.compounds] == list(CIDS)
    alizarin = found.compounds[0]
    assert (alizarin.title, alizarin.formula, alizarin.held) == ("Alizarin", "C14H8O4", False)
    assert alizarin.pubchem_synonyms[:3] == ["Alizarin", "72-48-0", "1,2-dihydroxyanthracene-9,10-dione"]
    assert alizarin.hazards is not None and found.compounds[1].hazards is None
    assert found.notices == []
    asked = {request.url.path for request in recorder.requests}
    assert "/rest/pug/compound/cid/6293/synonyms/JSON" in asked
