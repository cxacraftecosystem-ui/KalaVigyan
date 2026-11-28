import uuid
from collections.abc import Mapping, Sequence
from typing import Any

from app.core.errors import ExternalFailure
from app.services.compose_components import ComposeDeps, compose_component
from app.services.compose_held import About, CraftHeld, HeldFact
from app.services.compose_molecule import molecule_3d
from app.services.compose_named import (
    NO_RECORD,
    RECORD_UNREAD,
    UNNAMED,
    fact_named_compound,
    facts_naming,
    held_by_material,
)
from app.sources.reference.pubchem import PubChemCompound

from .held import BAGRU, CONFORMER_SDF, FACTS, cited_claims, claim, delivery_problems

CURCUMIN_CID = 969516
NAMED = uuid.UUID("ba900000-0000-4000-8000-000000000201")
CURCUMINOIDS = uuid.UUID("ba900000-0000-4000-8000-000000000202")
HALDI = uuid.UUID("ba900000-0000-4000-8000-000000000203")
NAMED_TEXT = "Curcumin, the yellow colorant of turmeric, binds metal ions to form complexes."
PAGE = {
    **{claim_id: HeldFact(claim_id, text) for claim_id, text in FACTS.items()},
    NAMED: HeldFact(NAMED, NAMED_TEXT),
    CURCUMINOIDS: HeldFact(CURCUMINOIDS, "Turmeric holds curcuminoids that dye cotton yellow."),
    HALDI: HeldFact(HALDI, "Diferuloylmethane is the dye of haldi."),
}
CURCUMIN = PubChemCompound(CURCUMIN_CID, "Curcumin", "C21H20O6", "368.4", None, None, None)


class Records:
    def __init__(self, synonyms: Sequence[str] = (), *, down: bool = False) -> None:
        self.held = {CURCUMIN_CID: CURCUMIN}
        self.listed = list(synonyms)
        self.down = down
        self.asked: list[str] = []

    async def compound(self, cid: int) -> PubChemCompound | None:
        self.asked.append(f"compound {cid}")
        if self.down:
            raise ExternalFailure("PubChem timed out", kind="unavailable", service="pubchem")
        return self.held.get(cid)

    async def synonyms(self, cid: int) -> list[str]:
        self.asked.append(f"synonyms {cid}")
        return self.listed


def test_a_fact_names_a_compound_by_the_whole_word_in_any_case() -> None:
    assert facts_naming(["curcumin"], PAGE) == (NAMED,)
    assert facts_naming(["Alizarin"], PAGE) == (claim(4), claim(9), claim(10))
    assert facts_naming(["Turmeric", "curcumin"], PAGE) == (claim(13), claim(14), NAMED, CURCUMINOIDS)
    assert facts_naming(["Indigotin", " "], PAGE) == ()


async def test_a_compound_the_page_s_facts_name_is_found_by_pubchem_s_name_and_composed() -> None:
    records = Records()
    naming = await fact_named_compound(BAGRU, CURCUMIN_CID, records, PAGE)
    assert naming.problem is None and records.asked == [f"compound {CURCUMIN_CID}"]
    (named,) = naming.compounds
    assert (named.compound.cid, named.compound.name, named.compound.formula) == (
        CURCUMIN_CID,
        "Curcumin",
        "C21H20O6",
    )
    assert named.claim_ids == (NAMED,)
    assert naming.craft.facts[NAMED].text == NAMED_TEXT
    result = molecule_3d(
        naming.craft, About(compound=CURCUMIN_CID), {CURCUMIN_CID: CONFORMER_SDF}, naming.compounds
    )
    assert result.composed, result.missing
    (component,) = result.components
    spec = component.proposal.spec
    assert spec is not None
    assert [(model["cid"], model["name"]) for model in spec["molecules"]] == [(CURCUMIN_CID, "Curcumin")]
    assert cited_claims(component) == {NAMED}
    assert component.proposal.units[spec["side"][0]["unit"]].text == NAMED_TEXT
    assert delivery_problems(result.components, naming.craft) == []


async def test_a_synonym_is_read_only_when_pubchem_s_name_is_named_by_no_fact() -> None:
    records = Records(["Natural yellow 3", "Diferuloylmethane"])
    page = {claim_id: fact for claim_id, fact in PAGE.items() if claim_id != NAMED}
    naming = await fact_named_compound(BAGRU, CURCUMIN_CID, records, page)
    assert records.asked == [f"compound {CURCUMIN_CID}", f"synonyms {CURCUMIN_CID}"]
    assert [named.claim_ids for named in naming.compounds] == [(HALDI,)]


async def test_a_compound_no_fact_names_is_refused_saying_what_to_propose() -> None:
    page = {claim_id: fact for claim_id, fact in PAGE.items() if claim_id not in (NAMED, HALDI)}
    naming = await fact_named_compound(BAGRU, CURCUMIN_CID, Records(["Natural yellow 3"]), page)
    assert naming.compounds == ()
    assert naming.problem == UNNAMED.format(craft="Bagru Print", name="Curcumin", cid=CURCUMIN_CID)
    assert "propose_facts" in naming.problem


async def test_a_cid_pubchem_does_not_hold_or_cannot_be_read_just_now_is_refused_by_name() -> None:
    unknown = await fact_named_compound(BAGRU, 123456789, Records(), PAGE)
    assert unknown.problem == NO_RECORD.format(cid=123456789)
    down = await fact_named_compound(BAGRU, CURCUMIN_CID, Records(down=True), PAGE)
    assert down.problem == RECORD_UNREAD.format(cid=CURCUMIN_CID)


def test_a_compound_a_material_holds_is_composed_from_the_material_and_not_looked_up() -> None:
    assert held_by_material(BAGRU, 6293)
    assert not held_by_material(BAGRU, CURCUMIN_CID)


class Conformers:
    async def conformer(self, cid: int) -> str | None:
        return CONFORMER_SDF


def page_deps(records: Records) -> ComposeDeps:
    async def read(_session: Any, slug: str) -> CraftHeld:
        assert slug == BAGRU.slug
        return BAGRU

    async def opened() -> Conformers:
        return Conformers()

    async def listed() -> Records:
        return records

    async def facts(_session: Any, slug: str) -> Mapping[uuid.UUID, HeldFact]:
        assert slug == BAGRU.slug
        return PAGE

    return ComposeDeps(held=read, conformers=opened, records=listed, facts=facts)


async def test_compose_component_reads_the_record_and_the_page_s_facts_only_for_a_compound_no_material_holds() -> (
    None
):
    records = Records()
    deps = page_deps(records)
    composed = await compose_component(None, deps, BAGRU.slug, "molecule_3d", About(compound=CURCUMIN_CID))  # type: ignore[arg-type]
    assert composed.composed, composed.missing
    held = await compose_component(None, deps, BAGRU.slug, "molecule_3d", About(compound=6293))  # type: ignore[arg-type]
    assert held.composed and records.asked == [f"compound {CURCUMIN_CID}"]
    refused = await compose_component(None, deps, BAGRU.slug, "molecule_3d", About(compound=123456789))  # type: ignore[arg-type]
    assert refused.components == () and refused.missing == (NO_RECORD.format(cid=123456789),)
