from dataclasses import dataclass, field
from typing import Any

import pytest

from app.api import mcp_lookup_tools
from app.core.errors import ExternalFailure
from app.core.roles import RESEARCHER
from app.models import Compound
from app.research.evidence import SourceDocument
from app.services.lookup_subjects import HeldSubject
from app.services.source_lookup_sources import LookupSources
from app.sources.reference.pubchem import PUBCHEM_LICENCE, PubChemCompound

from .lookup_fakes import (
    FakeFetcher,
    FakeSearcher,
    FakeSession,
    call,
    document,
    item,
    person,
    serve,
    tool_context,
)

INDIGO = PubChemCompound(
    cid=10215,
    title="Indigo",
    formula="C16H10N2O2",
    molecular_weight="262.26",
    iupac_name=None,
    inchikey=None,
    smiles=None,
)
HAZARD_URL = "https://echa.europa.eu/information-on-chemicals/cl-inventory-database"
HAZARD_TEXT = "Indigo (PubChem CID 10215): GHS classification\nReported by ECHA:\nGHS Hazard Statements: H315"
ENTITY_TEXT = (
    "Indigofera tinctoria (Q2085556)\nspecies of plant\ntaxon name: Indigofera tinctoria\ntaxon rank: species"
)
ENTITY_URL = "https://www.wikidata.org/wiki/Q2085556"


@dataclass
class FakeCompounds:
    found: list[PubChemCompound]
    hazards: dict[str, SourceDocument | Exception] = field(default_factory=dict)
    name: str = "pubchem"
    asked: list[Any] = field(default_factory=list)

    async def compounds(self, text: str, k: int) -> list[PubChemCompound]:
        self.asked.append(text)
        return self.found[:k]

    async def compound(self, cid: int) -> PubChemCompound | None:
        self.asked.append(cid)
        return next((found for found in self.found if found.cid == cid), None)

    async def fetch(self, item_id: str) -> SourceDocument:
        found = self.hazards.get(item_id)
        if found is None:
            raise ExternalFailure("no hazards", kind="not_found", service=self.name)
        if isinstance(found, Exception):
            raise found
        return found


def hazards() -> SourceDocument:
    reported = item(
        "pubchem",
        HAZARD_URL,
        native="10215:ghs",
        source_type="COMPOUND_RECORD",
        title="Indigo: GHS classification",
        licence="https://echa.europa.eu/web/guest/legal-notice",
    )
    return document(reported, HAZARD_TEXT)


def looked_up(compounds: FakeCompounds | None = None, entities: FakeSearcher | None = None) -> LookupSources:
    return LookupSources(fetcher=FakeFetcher({}), compounds=compounds, entities=entities)


def content(result: dict[str, Any]) -> dict[str, Any]:
    assert result["isError"] is False, result
    return result["structuredContent"]


async def test_a_compound_comes_with_its_record_hazards_and_the_synonyms_kalavigyan_holds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    compounds = FakeCompounds([INDIGO], {"pubchem:10215:ghs": hazards()})
    serve(monkeypatch, looked_up(compounds))
    held = Compound(name="indigo", pubchemCid=10215, synonyms=["indigotin", "C.I. Vat Blue 1"])
    context = tool_context(None, FakeSession(scalar=held))
    result = content(await call("lookup", {"kind": "compound", "name": "indigo"}, context))
    [record] = result["compounds"]
    assert (record["cid"], record["formula"], record["url"]) == (
        10215,
        "C16H10N2O2",
        "https://pubchem.ncbi.nlm.nih.gov/compound/10215",
    )
    assert (record["licence"], record["grade"], record["held"], record["heldName"]) == (
        PUBCHEM_LICENCE,
        "A",
        True,
        "indigo",
    )
    assert record["synonyms"] == ["indigotin", "C.I. Vat Blue 1"]
    assert record["hazards"]["lines"] == HAZARD_TEXT.split("\n")
    assert (record["hazards"]["url"], record["hazards"]["openLicence"]) == (HAZARD_URL, False)
    assert result["notices"] == [] and compounds.asked == ["indigo"]


async def test_a_cid_is_looked_up_alone_and_an_unknown_one_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    down = ExternalFailure("pubchem answered 503", kind="unavailable", service="pubchem")
    compounds = FakeCompounds([INDIGO], {"pubchem:10215:ghs": down})
    serve(monkeypatch, looked_up(compounds))
    result = content(
        await call("lookup", {"kind": "compound", "id": 10215}, tool_context(person(RESEARCHER)))
    )
    [record] = result["compounds"]
    assert (record["held"], record["synonyms"], record["hazards"]) == (False, [], None)
    assert result["notices"] == [
        "PubChem's hazards for CID 10215 could not be read just now; ask again later."
    ]
    missing = await call("lookup", {"kind": "compound", "id": 99}, tool_context(None))
    assert missing["isError"] is True
    assert missing["content"][0]["text"].startswith("PubChem holds no compound for 99")


async def test_a_held_compound_comes_with_the_keys_a_component_proposal_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    serve(monkeypatch, looked_up(FakeCompounds([INDIGO])))
    asked: list[list[int]] = []
    key = "0d000000-0000-4000-8000-000000000001"

    async def subjects(session: Any, cids: list[int]) -> list[HeldSubject]:
        asked.append(list(cids))
        return [HeldSubject(kind="COMPOUND", key=key, name="indigo", record="10215")]

    monkeypatch.setattr(mcp_lookup_tools, "compound_subjects", subjects)
    held = Compound(name="indigo", pubchemCid=10215, synonyms=[])
    context = tool_context(None, FakeSession(scalar=held))
    result = content(await call("lookup", {"kind": "compound", "id": 10215}, context))
    assert asked == [[10215]]
    assert result["subjects"] == [{"kind": "COMPOUND", "key": key, "name": "indigo", "record": "10215"}]
    unheld = content(await call("lookup", {"kind": "compound", "id": 10215}, tool_context(None)))
    assert unheld["compounds"][0]["held"] is False and asked[-1] == []


async def test_a_lookup_needs_one_key_of_its_kind() -> None:
    from_both = await call("lookup", {"kind": "compound", "name": "indigo", "id": 10215}, tool_context(None))
    assert from_both["isError"] is True and "one of them" in from_both["content"][0]["text"]
    neither = await call("lookup", {"kind": "entity"}, tool_context(None))
    assert neither["isError"] is True and "Wikidata qid as id, one of them" in neither["content"][0]["text"]
    qid_for_a_compound = await call("lookup", {"kind": "compound", "id": "Q2085556"}, tool_context(None))
    assert "PubChem CID, a whole number" in qid_for_a_compound["content"][0]["text"]
    cid_for_an_entity = await call("lookup", {"kind": "entity", "id": 10215}, tool_context(None))
    assert "Wikidata qid, such as Q12345" in cid_for_an_entity["content"][0]["text"]
    unknown = await call("lookup", {"kind": "mineral", "name": "alum"}, tool_context(None))
    assert unknown["isError"] is True and "kind" in unknown["content"][0]["text"]


async def test_a_plant_comes_with_its_taxon_name_and_statements(monkeypatch: pytest.MonkeyPatch) -> None:
    found = item(
        "wikidata",
        ENTITY_URL,
        native="Q2085556",
        source_type="DATASET",
        trust="B",
        licence="CC0 1.0",
        title="Indigofera tinctoria",
        external_ids={"wikidata": "Q2085556"},
    )
    entities = FakeSearcher(
        "wikidata", [found], documents={"wikidata:Q2085556": document(found, ENTITY_TEXT)}
    )
    serve(monkeypatch, looked_up(entities=entities))
    result = content(await call("lookup", {"kind": "entity", "name": "true indigo"}, tool_context(None)))
    [entity] = result["entities"]
    assert (entity["qid"], entity["label"], entity["taxonName"]) == (
        "Q2085556",
        "Indigofera tinctoria",
        "Indigofera tinctoria",
    )
    assert (entity["licence"], entity["openLicence"], entity["grade"]) == ("CC0 1.0", True, "B")
    assert entity["lines"] == ENTITY_TEXT.split("\n") and entities.asked == ["true indigo"]
    by_qid = content(await call("lookup", {"kind": "entity", "id": "Q2085556"}, tool_context(None)))
    assert [entity["qid"] for entity in by_qid["entities"]] == ["Q2085556"]
    missing = await call("lookup", {"kind": "entity", "id": "Q999"}, tool_context(None))
    assert missing["content"][0]["text"].startswith("Wikidata holds no item for Q999")
