from __future__ import annotations

import uuid
from typing import Any

from app.curation.entities import Reaction, Species
from app.services.answer_events import CitedClaims
from app.services.curation_claims import StoredClaim, claim_writes, kept_differences, superseded_claims
from app.services.curation_keys import curated_id
from app.services.curation_overview import overview_pieces
from app.services.curation_structure import reaction_label

from .import_support import AJRAKH, checked, plan_of
from .test_craft_page import ajrakh_records

NOTE = "curation import test v2"
SUBJECT = uuid.UUID(int=7)


def planned(claim_id: uuid.UUID, **changes: Any) -> dict[str, Any]:
    row = {
        "id": claim_id,
        "subjectType": "CONCEPT",
        "subjectId": SUBJECT,
        "predicate": "states",
        "text": "Ajrakh is printed on both sides of the cloth in the old way.",
        "textLang": "en",
        "evidenceLevel": "PROVISIONAL",
        "levelReason": "every quote re-found verbatim",
        "origin": "IMPORT",
        "status": "APPROVED",
        "version": 2,
        "createdByKind": "SYSTEM",
        "sensitivity": "OPEN",
        "sourcesDiffer": False,
        "differsOn": None,
        "field": "PROCESS",
    }
    return row | changes


def stored(claim_id: uuid.UUID, **changes: Any) -> StoredClaim:
    row = planned(claim_id, **changes)
    return StoredClaim(
        id=claim_id,
        subject_id=row["subjectId"],
        text=row["text"],
        level=row["evidenceLevel"],
        level_reason=row["levelReason"],
        status=row["status"],
        sensitivity=row["sensitivity"],
        sources_differ=row["sourcesDiffer"],
        field=row["field"],
        differs_on=row["differsOn"],
    )


def test_a_new_claim_is_inserted_with_its_review_event() -> None:
    claim = uuid.UUID(int=1)
    written = claim_writes([planned(claim)], {}, NOTE)
    assert [row["id"] for row in written.inserts] == [claim]
    assert written.updates == ()
    (event,) = written.events
    assert (event["systemActor"], event["toStatus"], event["toLevel"]) == (
        "curation",
        "APPROVED",
        "PROVISIONAL",
    )


def test_an_unchanged_claim_writes_nothing() -> None:
    claim = uuid.UUID(int=2)
    assert claim_writes([planned(claim)], {claim: stored(claim)}, NOTE).events == ()


def test_a_changed_text_updates_the_row_and_its_version() -> None:
    claim = uuid.UUID(int=3)
    written = claim_writes(
        [planned(claim, text="A new sentence about the cloth in Kutch.")], {claim: stored(claim)}, NOTE
    )
    (update,) = written.updates
    assert (update["text"], update["version"]) == ("A new sentence about the cloth in Kutch.", 2)


def test_a_conflict_s_subject_is_stored_with_the_flag_and_the_first_conflict_names_a_claim() -> None:
    rows = {row["id"]: row for row in plan_of(AJRAKH).part("claims")}

    def flag(key: str) -> tuple[bool, str | None]:
        row = rows[curated_id(AJRAKH, key)]
        return row["sourcesDiffer"], row["differsOn"]

    assert flag("C064") == (True, "How many times the saaj soaking is repeated")
    assert flag("C076") == (True, "How long the iron mixture for kut ferments")
    assert flag("C090") == (True, "How long the red dye bath lasts")
    assert flag("C001") == (False, None)


def test_a_named_conflict_updates_the_stored_claim_that_was_only_flagged() -> None:
    claim = uuid.UUID(int=11)
    about = "How long the red dye bath lasts"
    written = claim_writes(
        [planned(claim, sourcesDiffer=True, differsOn=about)],
        {claim: stored(claim, sourcesDiffer=True)},
        NOTE,
    )
    (update,) = written.updates
    assert (update["sourcesDiffer"], update["differsOn"]) == (True, about)


def test_a_flag_a_live_differing_fact_holds_is_kept_with_what_it_differs_on() -> None:
    flagged, plain = uuid.UUID(int=21), uuid.UUID(int=22)
    about = "How many sides of the cloth are printed"
    current = {flagged: stored(flagged, sourcesDiffer=True, differsOn=about), plain: stored(plain)}
    rows = kept_differences([planned(flagged), planned(plain)], current, {flagged}, set())
    assert [(row["sourcesDiffer"], row["differsOn"]) for row in rows] == [(True, about), (False, None)]
    assert claim_writes(rows, current, NOTE).updates == ()


def test_a_claim_its_dossier_puts_in_a_conflict_keeps_the_dossier_s_wording() -> None:
    claim = uuid.UUID(int=23)
    row = planned(claim, sourcesDiffer=True, differsOn="How long the red dye bath lasts")
    current = {claim: stored(claim, sourcesDiffer=True, differsOn="How many dips the cloth takes")}
    (kept,) = kept_differences([row], current, {claim}, set())
    assert (kept["sourcesDiffer"], kept["differsOn"]) == (True, "How long the red dye bath lasts")


def test_a_flag_a_person_cleared_stays_cleared_against_the_dossier_s_conflict() -> None:
    claim = uuid.UUID(int=24)
    row = planned(claim, sourcesDiffer=True, differsOn="How long the red dye bath lasts")
    current = {claim: stored(claim)}
    (kept,) = kept_differences([row], current, set(), {claim})
    assert (kept["sourcesDiffer"], kept["differsOn"]) == (False, None)
    assert claim_writes([kept], current, NOTE).updates == ()


def test_a_level_people_raised_and_a_retraction_are_never_undone() -> None:
    raised, retracted = uuid.UUID(int=4), uuid.UUID(int=5)
    current = {
        raised: stored(raised, evidenceLevel="REVIEWED", levelReason="a professor read the GI journal"),
        retracted: stored(retracted, status="RETRACTED"),
    }
    written = claim_writes([planned(raised), planned(retracted)], current, NOTE)
    assert written.updates == ()


def test_a_superseded_claim_that_returns_is_shown_again() -> None:
    claim = uuid.UUID(int=6)
    written = claim_writes([planned(claim)], {claim: stored(claim, status="SUPERSEDED")}, NOTE)
    (update,) = written.updates
    assert update["status"] == "APPROVED"
    assert (written.events[0]["fromStatus"], written.events[0]["toStatus"]) == ("SUPERSEDED", "APPROVED")


def test_claims_missing_from_a_new_version_are_superseded_not_deleted() -> None:
    kept, dropped, retracted = uuid.UUID(int=8), uuid.UUID(int=9), uuid.UUID(int=10)
    current = {kept: stored(kept), dropped: stored(dropped), retracted: stored(retracted, status="RETRACTED")}
    written = superseded_claims(current, {kept}, NOTE)
    assert written.updates == ({"id": dropped, "status": "SUPERSEDED"},)
    assert written.inserts == ()
    assert [event["toStatus"] for event in written.events] == ["SUPERSEDED"]


def test_a_reaction_label_falls_back_to_its_products_then_its_kind() -> None:
    long_name = "x" * 195
    reaction = Reaction(
        id="R01",
        kind="REDOX",
        reactants=[Species(name=long_name)],
        products=[Species(name="blue indigo")],
        claim_ids=["C001"],
    )
    assert reaction_label(reaction) == "blue indigo"
    wide = reaction.model_copy(update={"products": [Species(name=long_name), Species(name=long_name)]})
    assert reaction_label(wide) == "Redox reaction"


def test_an_overview_sentence_the_prose_validator_refuses_is_dropped() -> None:
    records = ajrakh_records()
    plan = plan_of(AJRAKH)
    dossier = checked(AJRAKH).dossier
    assert dossier is not None
    first = dossier.overview.lede[0]
    padded = first.model_copy(update={"text": first.text.removesuffix(".") + " since 1634."})
    changed = dossier.model_copy(
        update={
            "overview": dossier.overview.model_copy(update={"lede": [padded, *dossier.overview.lede[1:]]})
        }
    )
    cited = CitedClaims(views={view.id: view for view in records.views}, sources={})
    pieces = overview_pieces(changed, cited, craft_id=plan.craft.id, districts=[])
    assert any(line.startswith("overview.lede.0") and "1634" in line for line in pieces.dropped)
    lede = next(piece for piece in pieces.pieces if piece.facet == "OVERVIEW")
    assert all("1634" not in sentence.text for sentence in lede.payload.cited_sentences())
    assert len(list(lede.payload.cited_sentences())) == len(dossier.overview.lede) - 1


def test_a_claim_whose_field_changed_is_updated_with_the_new_field() -> None:
    claim = uuid.UUID(int=21)
    written = claim_writes([planned(claim, field="CHEMISTRY")], {claim: stored(claim)}, NOTE)
    (update,) = written.updates
    assert (update["id"], update["field"]) == (claim, "CHEMISTRY")
    assert written.inserts == ()
