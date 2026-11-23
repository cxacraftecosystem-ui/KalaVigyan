import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import pytest

from app.core.errors import InvalidInput
from app.services.compound_lookup import find_compound, link_compounds
from app.sources.reference.pubchem import PubChemAdapter, PubChemCompound

from ..sources.recorded import Recorder, Reply, fixed_clock, source_http

PUG = "pubchem.ncbi.nlm.nih.gov/rest/pug"
PROPERTIES = "property/Title,MolecularFormula,MolecularWeight,IUPACName,InChIKey,SMILES/JSON"


def compound(cid: int, title: str, formula: str) -> PubChemCompound:
    return PubChemCompound(cid, title, formula, None, None, None, None)


class FakeFinder:
    def __init__(
        self, answers: dict[str, list[PubChemCompound]], records: dict[int, PubChemCompound] | None = None
    ) -> None:
        self.answers = answers
        self.records = records or {}
        self.asked: list[str] = []

    async def compounds(self, text: str, k: int) -> list[PubChemCompound]:
        self.asked.append(text)
        return self.answers.get(text, [])[:k]

    async def compound(self, cid: int) -> PubChemCompound | None:
        self.asked.append(f"cid:{cid}")
        return self.records.get(cid)


def pubchem(routes: dict) -> PubChemAdapter:
    return PubChemAdapter(source_http(Recorder(routes), "pubchem"), clock=fixed_clock())


async def test_a_name_match_with_another_composition_falls_back_to_the_formula() -> None:
    finder = FakeFinder(
        {
            "Potassium alum": [compound(24856, "Aluminum potassium sulfate", "AlKO8S2")],
            "AlH24KO20S2": [compound(62667, "Potassium alum dodecahydrate", "AlH24KO20S2")],
        }
    )
    found = await find_compound(finder, name="Potassium alum", formula="KAl(SO4)2·12H2O")
    assert (found.cid, finder.asked) == (62667, ["Potassium alum", "AlH24KO20S2"])


async def test_no_candidate_of_the_same_composition_is_not_found() -> None:
    finder = FakeFinder({"Iron(II) acetate": [compound(10, "Iron(III) acetate", "C6H9FeO6")]})
    assert await find_compound(finder, name="Iron(II) acetate", formula="Fe(CH3COO)2") is None


async def test_an_ion_is_not_looked_up() -> None:
    with pytest.raises(InvalidInput, match="ion"):
        await find_compound(FakeFinder({}), name="Aluminium", formula="Al^3+")


async def test_alizarin_is_found_by_name_through_the_pubchem_adapter() -> None:
    adapter = pubchem(
        {
            f"{PUG}/compound/name/alizarin/cids/JSON": [
                Reply("pubchem_name_cids.json"),
                Reply("pubchem_word_cids.json"),
            ],
            f"{PUG}/compound/cid/6293,3955344,20431/{PROPERTIES}": Reply("pubchem_properties.json"),
        }
    )
    found = await find_compound(adapter, name="alizarin", formula="C14H8O4")
    assert (found.cid, found.title, found.inchikey) == (6293, "Alizarin", "RGCKGOZRHPZPFP-UHFFFAOYSA-N")
    assert found.url == "https://pubchem.ncbi.nlm.nih.gov/compound/6293"


async def test_an_unknown_name_is_found_by_its_hill_formula_through_the_pubchem_adapter() -> None:
    adapter = pubchem(
        {
            f"{PUG}/compound/name/madder%20red/cids/JSON": [
                Reply("pubchem_not_found.json", status=404),
                Reply("pubchem_not_found.json", status=404),
            ],
            f"{PUG}/compound/fastformula/C14H8O4/cids/JSON": Reply("pubchem_formula_cids.json"),
            f"{PUG}/compound/cid/6293,2950/{PROPERTIES}": Reply("pubchem_formula_properties.json"),
        }
    )
    found = await find_compound(adapter, name="madder red", formula="C14H8O4")
    assert (found.cid, found.formula) == (6293, "C14H8O4")


async def test_a_known_record_is_read_by_its_cid_through_the_pubchem_adapter() -> None:
    adapter = pubchem({f"{PUG}/compound/cid/6293/{PROPERTIES}": Reply("pubchem_properties.json")})
    found = await adapter.compound(6293)
    assert (found.cid, found.title, found.formula) == (6293, "Alizarin", "C14H8O4")


async def test_a_record_pubchem_does_not_hold_is_none() -> None:
    adapter = pubchem({f"{PUG}/compound/cid/9/{PROPERTIES}": Reply("pubchem_not_found.json", status=404)})
    assert await adapter.compound(9) is None


NOW = datetime(2026, 11, 23, 9, 0, tzinfo=UTC)
ALIZARIN_ID = uuid.UUID(int=1)
INDIGO_ID = uuid.UUID(int=2)
LEUCOINDIGO_ID = uuid.UUID(int=3)
STORED_ROWS = [
    (ALIZARIN_ID, "Alizarin", "C14H8O4", None, None),
    (INDIGO_ID, "Indigo", "C16H10N2O2", 10215, uuid.UUID(int=9)),
    (LEUCOINDIGO_ID, "Leucoindigo", "C16H12N2O2", 23035, None),
]


@dataclass
class CountedSessions:
    rows: list[tuple[Any, ...]]
    events: list[str] = field(default_factory=list)
    open: int = 0

    def __call__(self) -> CountedSession:
        return CountedSession(self)


@dataclass
class StoredRows:
    rows: list[tuple[Any, ...]]

    def all(self) -> list[tuple[Any, ...]]:
        return self.rows


@dataclass
class CountedSession:
    sessions: CountedSessions

    async def __aenter__(self) -> CountedSession:
        self.sessions.open += 1
        self.sessions.events.append("open")
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        self.sessions.open -= 1
        self.sessions.events.append("close")

    async def execute(self, statement: object) -> StoredRows:
        return StoredRows(self.sessions.rows)

    async def get(self, entity: object, ident: uuid.UUID, **options: object) -> None:
        self.sessions.events.append(f"get {ident.int}")

    async def commit(self) -> None:
        self.sessions.events.append("commit")


class AskedWithNoSessionOpen(FakeFinder):
    def __init__(
        self,
        sessions: CountedSessions,
        answers: dict[str, list[PubChemCompound]],
        records: dict[int, PubChemCompound],
    ) -> None:
        super().__init__(answers, records)
        self.sessions = sessions

    async def compounds(self, text: str, k: int) -> list[PubChemCompound]:
        assert self.sessions.open == 0
        self.sessions.events.append(f"ask {text}")
        return await super().compounds(text, k)

    async def compound(self, cid: int) -> PubChemCompound | None:
        assert self.sessions.open == 0
        self.sessions.events.append(f"ask cid:{cid}")
        return await super().compound(cid)


async def test_pubchem_is_asked_with_no_session_open_and_a_compound_gone_meanwhile_is_left() -> None:
    sessions = CountedSessions(STORED_ROWS)
    finder = AskedWithNoSessionOpen(
        sessions,
        {"Alizarin": [compound(6293, "Alizarin", "C14H8O4")]},
        {23035: compound(23035, "Leucoindigo", "C16H12N2O2")},
    )
    report = await link_compounds(sessions, finder, now=NOW)
    assert sessions.events == [
        "open",
        "close",
        "ask Alizarin",
        "ask cid:23035",
        "open",
        "get 1",
        "get 3",
        "commit",
        "close",
    ]
    assert report.as_dict() == {"linked": [], "filled": [], "notFound": [], "failed": [], "ok": True}


async def test_nothing_found_opens_no_second_session() -> None:
    sessions = CountedSessions(STORED_ROWS)
    report = await link_compounds(sessions, AskedWithNoSessionOpen(sessions, {}, {}), now=NOW)
    assert sessions.events == ["open", "close", "ask Alizarin", "ask C14H8O4", "ask cid:23035"]
    assert report.not_found == ["Alizarin", "Leucoindigo"]
